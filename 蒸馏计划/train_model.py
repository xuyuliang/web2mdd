import json
import time

import numpy as np

from config import TRAIN_JSONL, VAL_JSONL, MODEL_NPZ

VOCAB = {chr(c + 97): c + 1 for c in range(26)}
PAD = 0
WINDOW = 6
HALF = WINDOW // 2
FEAT_DIM = 27 * WINDOW
HIDDEN = 128
LR = 1e-3
EPOCHS = 30
PATIENCE = 4
BATCH = 512


def char_id(ch):
    return VOCAB.get(ch, PAD)


def load_data(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def boundary_mask(segs):
    mask = []
    for s in segs:
        for _ in range(len(s) - 1):
            mask.append(False)
        mask.append(True)
    return mask[:-1]


def features(word, mask):
    ids = [char_id(c) for c in word]
    n = len(ids)
    xs = []
    ys = []
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
        ys.append(1.0 if mask[g] else 0.0)
    return xs, ys


def build_dataset(rows):
    X = []
    Y = []
    for r in rows:
        xs, ys = features(r["word"], boundary_mask(r["segments"]))
        X.extend(xs)
        Y.extend(ys)
    return np.stack(X), np.array(Y, dtype=np.float32)


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def predict_batch(W1, b1, W2, b2, X):
    h = np.maximum(X @ W1 + b1, 0)
    return sigmoid(h @ W2 + b2)


def main():
    train = build_dataset(load_data(TRAIN_JSONL))
    val = build_dataset(load_data(VAL_JSONL))
    print(f"train gaps {train[0].shape[0]}  val gaps {val[0].shape[0]}")

    rng = np.random.default_rng(0)
    W1 = rng.normal(0, 0.08, size=(FEAT_DIM, HIDDEN)).astype(np.float32)
    b1 = np.zeros(HIDDEN, dtype=np.float32)
    W2 = rng.normal(0, 0.08, size=(HIDDEN, 1)).astype(np.float32)
    b2 = np.zeros(1, dtype=np.float32)

    m1 = np.zeros_like(W1); v1 = np.zeros_like(W1)
    mb1 = np.zeros_like(b1); vb1 = np.zeros_like(b1)
    m2 = np.zeros_like(W2); v2 = np.zeros_like(W2)
    mb2 = np.zeros_like(b2); vb2 = np.zeros_like(b2)

    best = None
    best_val = float("inf")
    patience = 0
    t0 = time.time()

    def bce(p, y):
        p = np.asarray(p).reshape(-1)
        y = np.asarray(y).reshape(-1)
        eps = 1e-7
        return -(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)).mean()

    Xtr, Ytr = train
    Xva, Yva = val
    n = Xtr.shape[0]
    for epoch in range(1, EPOCHS + 1):
        order = rng.permutation(n)
        for start in range(0, n, BATCH):
            idx = order[start:start + BATCH]
            Xb = Xtr[idx]; Yb = Ytr[idx]
            h = np.maximum(Xb @ W1 + b1, 0)
            p = sigmoid(h @ W2 + b2)
            dp = (p - Yb[:, None]) / len(idx)
            grad_h = dp @ W2.T
            grad_h = grad_h * (h > 0)
            grad_W2 = h.T @ dp
            grad_b2 = dp.sum(axis=0, keepdims=True)
            grad_W1 = Xb.T @ grad_h
            grad_b1 = grad_h.sum(axis=0)

            t = (epoch - 1) * (n // BATCH + 1) + start // BATCH + 1
            for p_, g_, m_, v_ in ((W1, grad_W1, m1, v1), (b1, grad_b1, mb1, vb1),
                                   (W2, grad_W2, m2, v2), (b2, grad_b2, mb2, vb2)):
                m_[:] = 0.9 * m_ + 0.1 * g_
                v_[:] = 0.999 * v_ + 0.001 * g_ * g_
                mc = m_ / (1 - 0.9 ** t)
                vc = v_ / (1 - 0.999 ** t)
                p_[:] -= LR * mc / (np.sqrt(vc) + 1e-8)

        va = bce(predict_batch(W1, b1, W2, b2, Xva), Yva)
        tr = bce(predict_batch(W1, b1, W2, b2, Xtr), Ytr)
        print(f"epoch {epoch:2d}  train_bce {tr:.4f}  val_bce {va:.4f}  {time.time()-t0:.0f}s")
        if va < best_val - 1e-4:
            best_val = va
            best = (W1.copy(), b1.copy(), W2.copy(), b2.copy())
            patience = 0
        else:
            patience += 1
            if patience >= PATIENCE:
                print("early stop")
                break

    if best is None:
        best = (W1, b1, W2, b2)
    np.savez(MODEL_NPZ, W1=best[0], b1=best[1], W2=best[2], b2=best[3])
    print(f"saved {MODEL_NPZ}  best_val_bce {best_val:.4f}")


if __name__ == "__main__":
    main()
