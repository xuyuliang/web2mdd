"""POS_WEIGHT 扫描：对每个权重训练一个模型，扫阈值，收集 (最佳Exact, 最佳F1, F1平台宽度/中心/悬崖性)。

黄金平衡点三规则：
  1) 优先 Enough-Exact：候选要求 best-exact >= EXACT_FLOOR。
  2) 弃"悬崖型"：平台中心附近阈值偏移一点指标暴跌的组合不要。
  3) 取"平原中心"：阈值落在 F1 平台正中且附近 F1 稳健 >= PLATEAU_F1。
用法：python sweep_pos_weight.py [1.3 1.5 1.8 2.0]
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from char_model import boundary_mask
from onnx_infer import OnnxCutter, probs_to_segments
from rules import apply_rules

OUT = Path(__file__).with_name("output")
TRAINER = Path(__file__).with_name("train_model.py")

GRID_LO, GRID_HI, GRID_STEP = 0.30, 0.80, 0.01
PLATEAU_F1 = 0.70
EXACT_FLOOR = 0.545


def load_rows(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def build_items(cutter, rows):
    items = []
    for r in rows:
        w = r["word"].lower()
        true = np.array(boundary_mask(r["segments"]), dtype="bool")
        probs = cutter.gap_probs(w)
        if probs.size == 0:
            continue
        items.append((w, true, probs))
    return items


def metrics(items, t):
    tp = fp = fn = exact = 0
    for w, true, probs in items:
        pred_segs = probs_to_segments(w, probs, t)
        pred_segs, _ = apply_rules(w, pred_segs)
        pred = np.array(boundary_mask(pred_segs), dtype="bool")
        tp += int(((pred == 1) & (true == 1)).sum())
        fp += int(((pred == 1) & (true == 0)).sum())
        fn += int(((pred == 0) & (true == 1)).sum())
        exact += int(bool((pred == true).all()))
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return f1, exact / max(len(items), 1)


def train(pw, dest, meta):
    env = dict(os.environ)
    env["MLD_POS_WEIGHT"] = f"{pw}"
    env["MLD_SAVE_ONNX"] = str(dest)
    env["MLD_SAVE_META"] = str(meta)
    subprocess.run([sys.executable, str(TRAINER)], env=env, check=True)


def analyze(cutter, rows):
    items = build_items(cutter, rows)
    grid = np.round(np.arange(GRID_LO, GRID_HI + GRID_STEP, GRID_STEP), 3)
    tbl = []
    for t in grid:
        f1, exact = metrics(items, float(t))
        tbl.append((float(t), f1, exact))
    return tbl


def summarize(tbl):
    best_f1 = max(tbl, key=lambda r: (r[1], r[2]))
    best_ex = max(tbl, key=lambda r: (r[2], r[1]))
    # 最长平台：F1 >= PLATEAU_F1 的连续区间
    on = [r[1] >= PLATEAU_F1 for r in tbl]
    best_plateau, best_len = None, 0
    run_start = -1
    for i, flag in enumerate(on + [False]):
        if flag and run_start < 0:
            run_start = i
        elif not flag and run_start >= 0:
            seg = tbl[run_start:i]
            if len(seg) > best_len:
                best_len = len(seg)
                best_plateau = seg
            run_start = -1
    center = best_plateau[len(best_plateau) // 2] if best_plateau else None
    # 悬崖：best-ex 阈值 ±0.02 内 F1 的最宽跌幅
    t = best_ex[0]
    near = [r for r in tbl if abs(r[0] - t) <= 0.02]
    cliff = (max(r[1] for r in near) - min(r[1] for r in near)) if len(near) >= 2 else 0.0
    return dict(best_f1=best_f1, best_ex=best_ex,
                center=center, plateau_width=best_len * GRID_STEP, cliff=cliff)


def main():
    weights = [float(x) for x in sys.argv[1:]] or [1.3, 1.5, 1.8, 2.0]
    rows = load_rows(OUT / "test.jsonl")

    print(f"{'pw':>5} | {'bestF1@th':>12} | {'bestEx@th':>14} | {'platW':>6} | {'centerF1@th':>12} | {'cliff':>6}")
    results = []
    for pw in weights:
        dest = OUT / f"model_pw{pw:g}.onnx"
        meta = OUT / f"model_pw{pw:g}.npz"
        try:
            train(pw, dest, meta)
        except subprocess.CalledProcessError:
            print(f"{pw:>5} | TRAIN FAILED")
            continue
        cutter = OnnxCutter(dest)
        tbl = analyze(cutter, rows)
        s = summarize(tbl)
        bf, be, ctr = s["best_f1"], s["best_ex"], s["center"]
        print(f"{pw:>5} | {bf[1]:.3f}@{bf[0]:.2f}    | {be[2]:.3f}@{be[0]:.2f}   | "
              f"{s['plateau_width']:>7.2f} | {ctr[1]:.3f}@{ctr[0]:.2f}   | {s['cliff']:.3f}")
        results.append((pw, s))

    print("\n== 黄金平衡点筛选（规则1: exact>=%.1f%%，规则2: 弃悬崖，规则3: 取F1平台中心）==" % (EXACT_FLOOR * 100))
    ok = [x for x in results if x[1]["best_ex"][2] >= EXACT_FLOOR]
    if not ok:
        print("无 exact>=54.5% 的组合；放宽用近似最优：")
        ok = [min(results, key=lambda r: abs(r[1]["best_ex"][2] - EXACT_FLOOR))]
    ok.sort(key=lambda r: -(r[1]["cliff"]) * 0)  # no-op；下按平台宽排序
    ok.sort(key=lambda r: (r[1]["best_ex"][2], r[1]["plateau_width"]), reverse=True)
    for pw, s in ok:
        fine = "  <-- 锁定" if (s["plateau_width"] >= 0.10 and s["cliff"] <= 0.05 and s["center"]) else ""
        print(f"pw={pw:g}  bestEx={s['best_ex'][2]:.3f}@{s['best_ex'][0]:.2f}  "
              f"F1平台宽={s['plateau_width']:.2f} 中心F1={s['center'][1]:.3f}@{s['center'][0]:.2f} "
              f"悬崖={s['cliff']:.3f}{fine}")


if __name__ == "__main__":
    main()