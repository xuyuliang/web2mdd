"""torch 训练：CharBiLSTM → 边界概率，导出 model.onnx（+ 存元数据 npz）。

训练/验证集在"套规则后"的标签（rules_clean.jsonl 拆出的 train/val）上做。
early stop 看 val masked-BCE；结束后导出 ONNX 供 app 低配部署用。
"""

import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim

from config import TRAIN_JSONL, VAL_JSONL, MODEL_ONNX, MODEL_META, THRESHOLD
from char_model import (
    CharBiLSTMTokenizer,
    collate,
    masked_bce,
    export_to_onnx,
    gap_probs,
)

EMBED_DIM = 16
HIDDEN_DIM = 32
LR = 1e-3
EPOCHS = 30
PATIENCE = 4
BATCH = 128
# 可用环境变量覆盖，便于 POS_WEIGHT 扫描 / 分模型落盘
# 值经 sweep_pos_weight.py 扫描确定：1.5 下 exact/F1 平台/抗悬崖俱佳
POS_WEIGHT = float(os.environ.get("MLD_POS_WEIGHT", "1.5"))
SAVE_ONNX = Path(os.environ.get("MLD_SAVE_ONNX", str(MODEL_ONNX)))
SAVE_META = Path(os.environ.get("MLD_SAVE_META", str(MODEL_META)))
WANDB_GROUP = "char_lstm"


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def make_batches(rows, batch_size, shuffle, rng):
    idx = list(range(len(rows)))
    if shuffle:
        rng.shuffle(idx)
    for s in range(0, len(idx), batch_size):
        yield collate([rows[i] for i in idx[s:s + batch_size]])


@torch.no_grad()
def evaluate(model, rows, batch_size=1024):
    model.eval()
    total_loss = 0.0
    total_mask = 0
    correct = 0
    n_gaps = 0
    for ids, mask, tgt in make_batches(rows, batch_size, shuffle=False, rng=None):
        p = gap_probs(model, ids)
        total_loss += (masked_bce(p, tgt, mask, pos_weight=POS_WEIGHT).item() * mask.sum().item())
        total_mask += mask.sum().item()
        for i in range(ids.shape[0]):
            L = int(tgt[i].sum().item())
            if L == 0:
                continue
            pred_gap = p[i, :L] >= 0.5
            correct += int((pred_gap.float() == tgt[i, :L]).sum().item())
            n_gaps += L
    return total_loss / max(total_mask, 1), correct / max(n_gaps, 1)


def main():
    train_rows = load_rows(TRAIN_JSONL)
    val_rows = load_rows(VAL_JSONL)
    rng = random.Random(0)
    torch.manual_seed(0)  # 固定 Embedding/LSTM 初始化，保证各权重训练可复现

    model = CharBiLSTMTokenizer(embed_dim=EMBED_DIM, hidden_dim=HIDDEN_DIM)
    opt = optim.Adam(model.parameters(), lr=LR)

    best = None
    best_acc = -1.0
    patience = 0
    t0 = time.time()
    for epoch in range(1, EPOCHS + 1):
        model.train()
        for ids, mask, tgt in make_batches(train_rows, BATCH, shuffle=True, rng=rng):
            opt.zero_grad()
            p = gap_probs(model, ids)
            loss = masked_bce(p, tgt, mask, pos_weight=POS_WEIGHT)
            loss.backward()
            opt.step()
        v_loss, v_acc = evaluate(model, val_rows)
        print(f"epoch {epoch:2d}  val_bce {v_loss:.4f}  val_acc {v_acc:.4f}  {time.time()-t0:.0f}s")
        if v_acc > best_acc + 1e-4:
            best_acc = v_acc
            patience = 0
        else:
            patience += 1
            if patience >= PATIENCE:
                print("early stop")
                break

    model.eval()
    export_to_onnx(model, str(SAVE_ONNX))
    np.savez(SAVE_META, embed_dim=EMBED_DIM, hidden_dim=HIDDEN_DIM, threshold=THRESHOLD, pos_weight=POS_WEIGHT)
    print(f"saved {SAVE_ONNX}  best_val_acc {best_acc:.4f}")


if __name__ == "__main__":
    main()