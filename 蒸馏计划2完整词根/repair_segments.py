import argparse
import collections
import json
from pathlib import Path


def align(w, c):
    n, m = len(w), len(c)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bt = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best = INF
            op = None
            if i > 0 and j > 0:
                cost = 0 if w[i - 1] == c[j - 1] else 1
                v = dp[i - 1][j - 1] + cost
                if v < best:
                    best = v
                    op = ("diag", cost)
            if i > 0:
                v = dp[i - 1][j] + 1
                if v < best:
                    best = v
                    op = ("del_w",)
            if j > 0:
                v = dp[i][j - 1] + 1
                if v < best:
                    best = v
                    op = ("ins_w",)
            dp[i][j] = best
            bt[i][j] = op
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        op = bt[i][j]
        if op[0] == "diag":
            ops.append(("diag", w[i - 1], c[j - 1]))
            i -= 1
            j -= 1
        elif op[0] == "del_w":
            ops.append(("del_w", w[i - 1]))
            i -= 1
        else:
            ops.append(("ins_w", c[j - 1]))
            j -= 1
    ops.reverse()
    return ops


def repair(word, segments):
    c = "".join(segments)
    seg_idx = []
    for k, s in enumerate(segments):
        seg_idx.extend([k] * len(s))
    ops = align(word, c)
    m = len(c)
    pos_c = 0
    buckets = [[] for _ in range(len(segments))]
    for op in ops:
        if op[0] == "diag":
            buckets[seg_idx[pos_c]].append(op[1])
            pos_c += 1
        elif op[0] == "del_w":
            if pos_c < m:
                idx = seg_idx[pos_c]
            elif pos_c > 0:
                idx = seg_idx[pos_c - 1]
            else:
                idx = 0
            buckets[idx].append(op[1])
        else:
            pos_c += 1
    repaired = ["".join(b) for b in buckets if b]
    if "".join(repaired) == word:
        return repaired, True
    return segments, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--out", default=None)
    ap.add_argument("--unfixed", default=None)
    args = ap.parse_args()

    records = []
    with open(args.raw, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    direct = repaired = unfixable = unparsed = 0
    out_records = []
    unfixed_records = []
    edits = collections.Counter()
    examples = []
    for rec in records:
        w = rec["word"]
        segs = rec["segments"]
        if not rec["ok"]:
            unparsed += 1
            continue
        if "".join(segs) == w:
            direct += 1
            rec = dict(rec)
            rec["status"] = "direct"
            out_records.append(rec)
            continue
        fixed_segs, ok = repair(w, segs)
        if ok:
            repaired += 1
            for op in align(w, "".join(segs)):
                edits[op[0]] += 1
            rec = dict(rec)
            rec["segments"] = fixed_segs
            rec["status"] = "repaired"
            out_records.append(rec)
            if len(examples) < 8:
                examples.append((w, segs, fixed_segs))
        else:
            unfixable += 1
            rec = dict(rec)
            rec["status"] = "unfixable"
            unfixed_records.append(rec)

    out_path = args.out or str(Path(args.raw).with_name("repaired.jsonl"))
    unfix_path = args.unfixed or str(Path(args.raw).with_name("unfixed.jsonl"))
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(unfix_path, "w", encoding="utf-8") as f:
        for r in unfixed_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(records)
    print(f"total {total}  direct {direct}  repaired {repaired}  unfixable {unfixable}  unparsed {unparsed}")
    print(f"usable (direct+repaired): {direct + repaired} = {(direct + repaired) / max(total, 1):.1%}")
    print("edit types:", dict(edits))
    for w, before, after in examples:
        print(f"  {w}")
        print(f"    before: {' . '.join(before)}")
        print(f"    after : {' . '.join(after)}")


if __name__ == "__main__":
    main()
