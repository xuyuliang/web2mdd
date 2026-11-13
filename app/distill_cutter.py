"""蒸馏模型2 - 词根切分（torch→ONNX 的 CharBiLSTM + 规则后处理）

模型来自 蒸馏计划2完整词根/output/model.onnx（训练端导出），
后处理规则单一来源是 蒸馏计划2完整词根/rules.py（与训练/推理端共用）。
使用 onnxruntime 加载，方便部署到低配服务器。
"""

import importlib.util
import sys

import numpy as np
import onnxruntime as ort

THRESHOLD = 0.44

_MISSING = object()


def _load_module_from_path(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_module_without_torch(path, name):
    """加载模块，但让其中的 `import torch` 失败。

    char_model.py 顶部的 `try: import torch` 只有训练/导出时才需要；
    线上推理只用它的 tokenize/char_id 等纯 Python 常量。
    torch 一旦被导入会多占约 160MB 内存、多花约 1 秒启动时间，
    在 500MB 的小机器上不能接受。
    """
    saved = sys.modules.get("torch", _MISSING)
    sys.modules["torch"] = None  # Python 里置为 None 会让 import 抛 ImportError
    try:
        return _load_module_from_path(path, name)
    finally:
        if saved is _MISSING:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = saved


class DistillCutter:
    """蒸馏模型2 切分器。segment(word) -> [seg1, seg2, ...]"""

    def __init__(self, model_path, rules_path, char_model_path=None):
        # char_model.py 与 rules.py 同目录（蒸馏计划2完整词根），单一来源导入。
        rules_mod = _load_module_from_path(rules_path, "distill_rules")
        if char_model_path is None:
            import pathlib
            char_model_path = str(pathlib.Path(rules_path).with_name("char_model.py"))
        char_mod = _load_module_without_torch(char_model_path, "distill_char_model")

        self.sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        self.output_name = self.sess.get_outputs()[0].name
        self.rules = rules_mod
        self.tokenize = char_mod.tokenize

    def gap_probs(self, word):
        ids = np.array([self.tokenize(word)], dtype=np.int64)
        probs = self.sess.run([self.output_name], {self.input_name: ids})[0][0]
        return probs[: len(word) - 1]

    def segment(self, word):
        word = word.lower()
        n = len(word)
        if not word.isalpha() or n < 2:
            return [word]
        probs = self.gap_probs(word)
        if probs.size == 0:
            return [word]
        segs = []
        start = 0
        for i, p in enumerate(probs):
            if p >= THRESHOLD:
                segs.append(word[start:i + 1])
                start = i + 1
        segs.append(word[start:])
        segs, _ = self.rules.apply_rules(word, segs)
        return segs