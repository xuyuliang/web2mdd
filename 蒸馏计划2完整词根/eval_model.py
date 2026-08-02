import json

import numpy as np

from config import TEST_JSONL, MODEL_ONNX, EVAL_REPORT
from rules import apply_rules
from char_model import boundary_mask
from onnx_infer import OnnxCutter, probs_to_segments

THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def metrics(rows_items, threshold):
    """给定阈值，套规则后统计全体测试词的 tp/fp/fn 与词级 exact。"""
    tp = fp = fn = 0
    exact = 0
    for w, true, probs in rows_items:
        if probs.size == 0:
            continue
        pred_segs = probs_to_segments(w, probs, threshold)
        pred_segs, _ = apply_rules(w, pred_segs)
        pred = np.array(boundary_mask(pred_segs), dtype=np.float32)
        tp += int(((pred == 1) & (true == 1)).sum())
        fp += int(((pred == 1) & (true == 0)).sum())
        fn += int(((pred == 0) & (true == 1)).sum())
        if np.array_equal(pred, true):
            exact += 1
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return dict(tp=tp, fp=fp, fn=fn, prec=prec, rec=rec, f1=f1, exact=exact)


def main():
    cutter = OnnxCutter(MODEL_ONNX)

    rows = []
    with open(TEST_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # 每个测试词只推理一次 gap 概率；阈值在概率上再选。
    items = []
    pos = neg = 0
    for r in rows:
        w = r["word"].lower()
        true = np.array(boundary_mask(r["segments"]), dtype="bool")
        probs = cutter.gap_probs(w)
        if probs.size == 0:
            continue
        pos += int(true.sum())
        neg += int((~true).sum())
        items.append((w, true, probs))

    lines = []
    lines.append(f"test words: {len(items)}")
    lines.append(f"gap ratio  positive(cut)={pos}  negative(non-cut)={neg}  (pos:{pos+neg} = {pos/(pos+neg):.2%})")
    lines.append(f"{'thr':>5} {'P':>6} {'R':>6} {'F1':>6} {'exact':>9}")
    best = None
    for t in THRESHOLDS:
        m = metrics(items, t)
        lines.append(f"{t:6.2f} {m['prec']:6.3f} {m['rec']:6.3f} {m['f1']:6.3f} {m['exact']/len(items):9.1%}")
        if best is None or (m["exact"], m["f1"]) > (best["exact"], best["f1"]):
            best = {"thr": t, **m}

    lines.append("")
    lines.append(f"== best: threshold={best['thr']:.2f}  F1={best['f1']:.3f}  exact={best['exact']/len(items):.1%}  "
                 f"(tp={best['tp']} fp={best['fp']} fn={best['fn']})")

    # 用最优阈值出一组样例。
    samples = []
    for r in rows:
        w = r["word"].lower()
        true = np.array(boundary_mask(r["segments"]), dtype="bool")
        probs = cutter.gap_probs(w)
        if probs.size == 0:
            continue
        pred_segs = probs_to_segments(w, probs, best["thr"])
        pred_segs, _ = apply_rules(w, pred_segs)
        pred = np.array(boundary_mask(pred_segs), dtype="bool")
        flag = "OK " if np.array_equal(pred, true) else "DIFF"
        samples.append((flag, w, r["segments"], pred_segs, [round(float(x), 2) for x in probs]))
        if len(samples) >= 12:
            break
    lines.append("--- samples (OK=matches teacher, DIFF=diffs) ---")
    for s in samples:
        lines.append(f"  {s[0]} {s[1]}")
        lines.append(f"       teacher: {' . '.join(s[2])}")
        lines.append(f"       model  : {' . '.join(s[3])}")

    text = "\n".join(lines)
    EVAL_REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()