import json

import numpy as np

from config import TEST_JSONL, MODEL_NPZ, EVAL_REPORT
from rules import apply_rules
from train_model import char_id, features, predict_batch

THRESHOLD = 0.39


def boundary_mask(segs):
    mask = []
    for s in segs:
        for _ in range(len(s) - 1):
            mask.append(False)
        mask.append(True)
    return mask[:-1]


def main():
    z = np.load(MODEL_NPZ)
    W1, b1, W2, b2 = z["W1"], z["b1"], z["W2"], z["b2"]

    rows = []
    with open(TEST_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    tp = fp = fn = 0
    exact = 0
    samples = []
    for r in rows:
        w = r["word"]
        true = np.array(boundary_mask(r["segments"]), dtype=np.float32)
        xs, _ = features(w, true)
        if not xs:
            continue
        X = np.stack(xs)
        p = predict_batch(W1, b1, W2, b2, X).ravel()
        pred = (p >= THRESHOLD).astype(np.float32)
        pred_segs = []
        start = 0
        for i, b in enumerate(pred):
            if b:
                pred_segs.append(w[start:i + 1])
                start = i + 1
        pred_segs.append(w[start:])
        pred_segs, _ = apply_rules(w, pred_segs)
        pred = np.array(boundary_mask(pred_segs), dtype=np.float32)
        tp += int(((pred == 1) & (true == 1)).sum())
        fp += int(((pred == 1) & (true == 0)).sum())
        fn += int(((pred == 0) & (true == 1)).sum())
        if np.array_equal(pred, true):
            exact += 1
            flag = "OK "
        else:
            flag = "DIFF"
        if len(samples) < 12:
            samples.append((flag, w, r["segments"], pred_segs, [round(float(x), 2) for x in p]))

    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    lines = []
    lines.append(f"test words: {len(rows)}")
    lines.append(f"gap-level  P={prec:.3f} R={rec:.3f} F1={f1:.3f}   (tp={tp} fp={fp} fn={fn})")
    lines.append(f"word exact-match: {exact}/{len(rows)} = {exact / max(len(rows), 1):.1%}")
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
