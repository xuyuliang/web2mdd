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
    out = Path(args.out) if args.out else src.with_suffix(".txt")

    word_re = re.compile(r'"word"\s*:\s*"([^"]*)"')

    lines = []
    bad = 0
    with open(src, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                bad += 1
                m = word_re.search(line)
                word = m.group(1) if m else "<unknown>"
                print(f"line {n}: word={word!r}  bad JSON, skipped", file=sys.stderr)
                continue
            word = rec.get("word", "")
            segs = rec.get("segments") or []
            lines.append(f"{word}    {'.'.join(segs)}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} records -> {out}  (skipped {bad})")


if __name__ == "__main__":
    main()
