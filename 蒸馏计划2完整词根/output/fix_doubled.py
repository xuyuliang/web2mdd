import json
import sys
from pathlib import Path

CONS = set("bcdfghjklmnpqrstvwxyz")


def doubled(word):
    return (len(word) >= 5 and word[-5] == word[-4] and word[-5] in CONS
            and word[-3:] == "ing")


def conforms(word, segs):
    last = segs[-1]
    if doubled(word):
        return last == word[-4:]
    return last == "ing"


def fix_doubled(word, segs):
    k = len(word) - 4
    newsegs = []
    pos = 0
    for s in segs:
        if pos + len(s) <= k:
            newsegs.append(s)
            pos += len(s)
        else:
            left = word[pos:k]
            right = word[k:]
            if left:
                newsegs.append(left)
            newsegs.append(right)
            break
    return newsegs


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("rules_clean.jsonl")

    lines = src.read_text(encoding="utf-8").splitlines()
    fixed = 0
    out = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        try:
            rec = json.loads(line)
        except Exception:
            out.append(line)
            continue
        word = rec["word"]
        segs = rec["segments"]
        if word.endswith("ing") and doubled(word) and not conforms(word, segs):
            rec["segments"] = fix_doubled(word, segs)
            fixed += 1
        out.append(json.dumps(rec, ensure_ascii=False))

    src.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    print(f"fixed {fixed} doubled violations -> {src}")


if __name__ == "__main__":
    main()
