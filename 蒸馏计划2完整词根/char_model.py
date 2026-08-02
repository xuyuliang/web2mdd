"""CharBiLSTM 分词模型（torch 版，替换原 numpy 窗口 MLP）。

语义与旧接口一致：对每个单词的每一个 gap（字符间缝隙）输出切分概率。
本模型按"字符位输出边界概率"实现，取 `probs[:, :n-1]` 即每个 gap 的概率。
"""

import torch
import torch.nn as nn

VOCAB = {chr(c + 97): c + 1 for c in range(26)}
PAD = 0
UNK = 27
VOCAB_SIZE = 28

EMBED_DIM = 16
HIDDEN_DIM = 32


def char_id(ch):
    return VOCAB.get(ch, PAD)


def tokenize(word):
    return [char_id(c) for c in word]


class CharBiLSTMTokenizer(nn.Module):
    """26 字母 + PAD(0) + UNK(27) = 28。输出逐字符概率，`[.., :n-1]` 为 gap 概率。"""

    def __init__(self, vocab_size=VOCAB_SIZE, embed_dim=EMBED_DIM, hidden_dim=HIDDEN_DIM):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=PAD)
        self.lstm = nn.LSTM(
            embed_dim, hidden_dim, num_layers=1, batch_first=True, bidirectional=True
        )
        self.fc = nn.Linear(hidden_dim * 2, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        embeds = self.embedding(x)
        lstm_out, _ = self.lstm(embeds)
        logits = self.fc(lstm_out)
        probs = self.sigmoid(logits).squeeze(-1)
        return probs


def boundary_mask(segs):
    mask = []
    for s in segs:
        for _ in range(len(s) - 1):
            mask.append(False)
        mask.append(True)
    return mask[:-1]


def collate(rows):
    """把 (word, segments) 列表打包成 (ids, valid_mask, targets)。

    ids:  LongTensor [B, L]，右填充 PAD。
    mask: FloatTensor [B, L-1]，1 表示该 gap 有效（非填充）。
    tgt:  FloatTensor [B, L-1]，0/1 边界标注（无效位取 0，训练时被 mask 屏蔽）。
    """
    words = [r["word"] for r in rows]
    n = max(len(w) for w in words)
    ids = torch.zeros(len(words), n, dtype=torch.long)
    mask = torch.zeros(len(words), n - 1, dtype=torch.float32)
    tgt = torch.zeros(len(words), n - 1, dtype=torch.float32)
    for i, r in enumerate(rows):
        w = r["word"].lower()
        ids[i, : len(w)] = torch.tensor(tokenize(w), dtype=torch.long)
        bm = boundary_mask(r["segments"])
        L = len(bm)
        mask[i, :L] = 1.0
        tgt[i, :L] = torch.tensor(bm, dtype=torch.float32)
    return ids, mask, tgt


def masked_bce(probs, tgt, mask, pos_weight=1.0):
    """按 mask 屏蔽填充位后的加权二元交叉熵。

    `pos_weight > 1` 时对正割点（tgt=1）梯度放大，逼迫模型对割点输出更高概率，
    更正的样本占比过低（本例仅 ~17%）导致的"保守低分"。
    """
    eps = 1e-7
    loss = -(pos_weight * tgt * torch.log(probs + eps) + (1 - tgt) * torch.log(1 - probs + eps))
    return (loss * mask).sum() / mask.sum().clamp(min=1.0)


def gap_probs(model, ids):
    """模型输出全字符概率，取 [:.., :n-1] 当 gap 概率。n = ids 列数。"""
    L = ids.shape[1]
    probs = model(ids)             # [B, L]
    return probs[:, :L - 1]


def export_to_onnx(model, save_path):
    """用 torch.onnx 导出，batch/seq 双动态轴，输入为 int64 token 序列。"""
    model.eval()
    dummy = torch.randint(1, 26, (1, 10), dtype=torch.long)
    torch.onnx.export(
        model,
        dummy,
        save_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size", 1: "seq_len"},
            "output": {0: "batch_size", 1: "seq_len"},
        },
        opset_version=14,
        dynamo=False,
    )
    print(f"模型已导出至 {save_path}")