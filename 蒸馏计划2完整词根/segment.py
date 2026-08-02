import sys

from config import MODEL_ONNX, THRESHOLD
from rules import apply_rules
from onnx_infer import OnnxCutter, probs_to_segments


def segment(word, cutter, threshold=THRESHOLD):
    word = word.lower()
    if not word.isalpha() or len(word) < 2:
        return [word]
    probs = cutter.gap_probs(word)
    if probs.size == 0:
        return [word]
    segs = probs_to_segments(word, probs, threshold)
    segs, _ = apply_rules(word, segs)
    return segs


def main():
    cutter = OnnxCutter(MODEL_ONNX)
    words = sys.argv[1:] or ["unbelievable", "pediatrician", "subordinate", "generalizability",
                             "sander", "titillation", "hillbilly", "consecrate"]
    for w in words:
        print(f"{w:16s} -> {' . '.join(segment(w, cutter))}")


if __name__ == "__main__":
    main()