import argparse
import json
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.input)
    out = Path(args.out) if args.out else src.with_suffix(".jsonl")

    records = []
    problems = []
    with open(src, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n\r")
            if not line.strip():
                continue
            parts = re.split(r"\s+", line.strip(), maxsplit=1)
            if len(parts) != 2:
                problems.append((n, line.strip(), "no word/seg split"))
                continue
            word, raw = parts[0], parts[1]
            segs = [s for s in raw.split(".") if s]
            if "".join(segs).lower() != word.lower():
                problems.append((n, word, ".".join(segs)))
            records.append({"word": word, "segments": segs})

    with open(out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} records -> {out}")
    if problems:
        print(f"=== {len(problems)} problem(s) ===", file=sys.stderr)
        for n, word, detail in problems:
            print(f"line {n}: word={word!r}  issue={detail}", file=sys.stderr)


if __name__ == "__main__":
    main()
