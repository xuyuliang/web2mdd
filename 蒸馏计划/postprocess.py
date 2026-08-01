import argparse
import collections
import json
import sys

from config import CLEAN, INVALID, REPORT


def segments_ok(word, segs):
    if not segs:
        return False
    if any(not s or not s.isalpha() for s in segs):
        return False
    return "".join(segs).lower() == word


def boundary_mask(segs):
    mask = []
    pos = 0
    for s in segs:
        for _ in range(len(s) - 1):
            mask.append(False)
        mask.append(True)
        pos += len(s)
    mask = mask[:-1]
    return mask


def mask_to_segments(word, mask):
    segs = []
    start = 0
    for i, b in enumerate(mask):
        if b:
            segs.append(word[start:i + 1])
            start = i + 1
    segs.append(word[start:])
    return segs


def validate(records):
    clean = []
    invalid = []
    for rec in records:
        w = rec["word"].lower()
        if not rec["ok"]:
            invalid.append({"word": w, "reason": "unparsed", "raw": rec.get("raw")})
            continue
        segs = rec["segments"]
        if not segments_ok(w, segs):
            invalid.append({"word": w, "reason": "bad_segments", "raw": rec.get("raw"),
                            "segments": segs})
            continue
        clean.append({"word": w, "segments": [s.lower() for s in segs]})
    return clean, invalid


def consistency_stats(clean):
    groups = collections.defaultdict(list)
    for rec in clean:
        w = rec["word"]
        mask = boundary_mask(rec["segments"])
        for i in range(len(w) - 3):
            sub = w[i:i + 4]
            if not sub.isalpha():
                continue
            pat = tuple(mask[i + k] for k in range(3))
            groups[sub].append((rec, i, pat))
    total = 0
    match = 0
    for sub, occs in groups.items():
        if len(occs) < 2:
            continue
        counter = collections.Counter(o[2] for o in occs)
        maj, cnt = counter.most_common(1)[0]
        total += len(occs)
        match += cnt
    if total == 0:
        return 0.0
    return match / total


def repair(clean, min_occ=3, ratio=2.0):
    groups = collections.defaultdict(list)
    for rec in clean:
        w = rec["word"]
        mask = boundary_mask(rec["segments"])
        for i in range(len(w) - 3):
            sub = w[i:i + 4]
            if not sub.isalpha():
                continue
            pat = tuple(mask[i + k] for k in range(3))
            groups[sub].append((rec, i, pat))
    changed = 0
    for sub, occs in groups.items():
        if len(occs) < min_occ:
            continue
        counter = collections.Counter(o[2] for o in occs)
        maj, cnt = counter.most_common(1)[0]
        if len(counter) < 2:
            continue
        if cnt < len(occs) - cnt * ratio:
            continue
        for rec, i, pat in occs:
            if pat == maj:
                continue
            mask = boundary_mask(rec["segments"])
            for k, b in enumerate(maj):
                if mask[i + k] != b:
                    mask[i + k] = b
            rec["segments"] = mask_to_segments(rec["word"], mask)
            changed += 1
    return changed


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def report_stats(clean, invalid, before, after, repaired, label):
    lines = []
    lines.append(f"===== {label} =====")
    lines.append(f"total records: {len(clean) + len(invalid)}")
    lines.append(f"valid: {len(clean)}  invalid: {len(invalid)}  "
                 f"valid_rate: {len(clean) / (len(clean) + len(invalid)):.1%}")
    reasons = collections.Counter(r["reason"] for r in invalid)
    for k, v in reasons.items():
        lines.append(f"  invalid[{k}]: {v}")
    segs = [len(r["segments"]) for r in clean]
    if segs:
        lines.append(f"avg segments/word: {sum(segs) / len(segs):.2f}")
        lines.append(f"multi-segment words: {sum(1 for n in segs if n >= 2)}/{len(segs)}")
        lens = [len(s) for r in clean for s in r["segments"]]
        hist = collections.Counter(lens)
        top = hist.most_common(8)
        lines.append("segment length top: " + ", ".join(f"{k}->{v}" for k, v in top))
    lines.append(f"consistency(before): {before:.1%}  after: {after:.1%}  repaired: {repaired}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--label", default="report")
    ap.add_argument("--no-repair", action="store_true")
    args = ap.parse_args()

    records = []
    with open(args.raw, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    clean, invalid = validate(records)
    before = consistency_stats(clean)
    repaired = 0
    if not args.no_repair:
        repaired = repair(clean)
        clean = [r for r in clean if r["segments"]]
    after = consistency_stats(clean)

    write_jsonl(CLEAN, clean)
    write_jsonl(INVALID, invalid)
    text = report_stats(clean, invalid, before, after, repaired, args.label)
    REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
