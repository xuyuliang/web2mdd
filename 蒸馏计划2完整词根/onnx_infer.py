"""共享的 ONNX 推理封装：distill_cutter.py / segment.py / eval_model.py 共用。

模型输出逐字符概率 [B, L]，取 [:, :n-1] 作为 gap 概率。
"""

import numpy as np
import onnxruntime as ort

from char_model import tokenize


class OnnxCutter:
    """封装 onnxruntime 的切分器，`gap_probs(word)` 返回一维 gap 概率。"""

    def __init__(self, model_path):
        self.sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        self.output_name = self.sess.get_outputs()[0].name

    def gap_probs(self, word):
        ids = np.array([tokenize(word)], dtype=np.int64)
        probs = self.sess.run([self.output_name], {self.input_name: ids})[0][0]
        return probs[: len(word) - 1]

    def close(self):
        if self.sess is not None:
            self.sess = None


def probs_to_segments(word, probs, threshold):
    segs = []
    start = 0
    for i, p in enumerate(probs):
        if p >= threshold:
            segs.append(word[start:i + 1])
            start = i + 1
    segs.append(word[start:])
    return segs