import argparse
import collections
import json

from config import OUT_DIR
from postprocess import consistency_stats
from rules import apply_rules, tiled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="input repaired.jsonl")
    ap.add_argument("--out", default=str(OUT_DIR / "rules_clean.jsonl"))
    ap.add_argument("--report", default=str(OUT_DIR / "rules_report.txt"))
    ap.add_argument("--changelog", default=str(OUT_DIR / "rules_changelog.txt"))
    args = ap.parse_args()

    records = []
    with open(args.raw, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    out_records = []
    changes = []  # (word, rule_names, before, after)
    per_rule = collections.Counter()
    notiled = []
    for rec in records:
        if not rec["ok"]:
            continue
        w = rec["word"].lower()
        segs = [s.lower() for s in rec["segments"]]
        new_segs, changed = apply_rules(w, segs)
        if not tiled(w, new_segs):
            notiled.append((w, segs, new_segs))
            continue
        out_records.append({"word": w, "segments": new_segs})
        if changed:
            changes.append((w, changed, segs, new_segs))
            for name in changed:
                per_rule[name] += 1

    with open(args.out, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(args.changelog, "w", encoding="utf-8") as f:
        f.write(f"# changed words: {len(changes)}\n")
        for w, names, before, after in changes:
            f.write(f"{w}\t{'+'.join(names)}\t{'.'.join(before)} -> {'.'.join(after)}\n")

    ok_records = [r for r in records if r["ok"]]
    before_cons = consistency_stats(ok_records)
    after_cons = consistency_stats(out_records)

    lines = []
    lines.append(f"total records: {len(records)}  usable: {len(out_records)}")
    lines.append(f"changed words: {len(changes)} ({len(changes) / max(len(out_records), 1):.1%})")
    lines.append(f"tiling failures: {len(notiled)}")
    lines.append("per-rule changed: " + ", ".join(f"{k}:{v}" for k, v in per_rule.most_common()))
    lines.append(f"consistency before: {before_cons:.1%}  after: {after_cons:.1%}")
    if notiled:
        lines.append("tiling failure samples:")
        for w, b, a in notiled[:5]:
            lines.append(f"  {w}: {'.'.join(b)} -> {'.'.join(a)}")
    text = "\n".join(lines)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)

    print("\n--- samples per rule (first 3) ---")
    per_rule_counts_shown = {}
    shown = 0
    for w, names, before, after in changes:
        name = names[0]
        if per_rule_counts_shown.get(name, 0) >= 3:
            continue
        per_rule_counts_shown[name] = per_rule_counts_shown.get(name, 0) + 1
        print(f"[{name}] {w}: {'.'.join(before)} -> {'.'.join(after)}")
        shown += 1
        if shown >= 48:
            break


if __name__ == "__main__":
    main()
