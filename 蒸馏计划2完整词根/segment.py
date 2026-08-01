import sys

import numpy as np

from config import MODEL_NPZ
from rules import apply_rules
from train_model import features, predict_batch, char_id


def load_model(path=MODEL_NPZ):
    z = np.load(path)
    return z["W1"], z["b1"], z["W2"], z["b2"]


def segment(word, model, threshold=0.37):
    W1, b1, W2, b2 = model
    word = word.lower()
    if not word.isalpha() or len(word) < 2:
        return [word]
    true = np.zeros(len(word) - 1, dtype=np.float32)
    xs, _ = features(word, true)
    if not xs:
        return [word]
    p = predict_batch(W1, b1, W2, b2, np.stack(xs)).ravel()
    segs = []
    start = 0
    for i, prob in enumerate(p):
        if prob >= threshold:
            segs.append(word[start:i + 1])
            start = i + 1
    segs.append(word[start:])
    segs, _ = apply_rules(word, segs)
    return segs


def main():
    model = load_model()
    words = sys.argv[1:] or ["unbelievable", "pediatrician", "subordinate", "generalizability",
                             "sander", "titillation", "hillbilly", "consecrate"]
    for w in words:
        print(f"{w:16s} -> {' . '.join(segment(w, model))}")


if __name__ == "__main__":
    main()
