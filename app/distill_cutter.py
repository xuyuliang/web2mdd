"""蒸馏模型2 - 词根切分（训练好的 numpy MLP + 规则后处理）

模型权重来自 蒸馏计划2完整词根/output/model.npz，
后处理规则单一来源是 蒸馏计划2完整词根/rules.py（与训练/推理端共用）。
"""

import importlib.util

import numpy as np

VOCAB = {chr(c + 97): c + 1 for c in range(26)}
PAD = 0
WINDOW = 6
HALF = WINDOW // 2
THRESHOLD = 0.39


def char_id(ch):
    return VOCAB.get(ch, PAD)


def _features(word, n):
    ids = [char_id(c) for c in word]
    xs = []
    for g in range(n - 1):
        ctx = []
        for k in range(-HALF, HALF):
            idx = g + k + 1
            ctx.append(ids[idx] if 0 <= idx < n else PAD)
        vec = []
        for c in ctx:
            oh = np.zeros(27, dtype=np.float32)
            if c:
                oh[c] = 1.0
            vec.append(oh)
        xs.append(np.concatenate(vec))
    return xs


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _load_rules(path):
    spec = importlib.util.spec_from_file_location("distill_rules", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DistillCutter:
    """蒸馏模型2 切分器。segment(word) -> [seg1, seg2, ...]"""

    def __init__(self, model_path, rules_path):
        z = np.load(model_path)
        self.W1 = z["W1"]
        self.b1 = z["b1"]
        self.W2 = z["W2"]
        self.b2 = z["b2"]
        self.rules = _load_rules(rules_path)
        self.threshold = THRESHOLD

    def segment(self, word):
        word = word.lower()
        n = len(word)
        if not word.isalpha() or n < 2:
            return [word]
        xs = _features(word, n)
        if not xs:
            return [word]
        X = np.stack(xs)
        h = np.maximum(X @ self.W1 + self.b1, 0)
        p = _sigmoid(h @ self.W2 + self.b2).ravel()
        segs = []
        start = 0
        for i, prob in enumerate(p):
            if prob >= self.threshold:
                segs.append(word[start:i + 1])
                start = i + 1
        segs.append(word[start:])
        segs, _ = self.rules.apply_rules(word, segs)
        return segs
