import re
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


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("rules_clean.txt")

    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = re.match(r"^(\S+)\s+(.+)$", line)
        if not m:
            continue
        rows.append((m.group(1), m.group(2).split(".")))

    ing_words = [(w, s) for w, s in rows if w.endswith("ing")]
    bad = [(w, s) for w, s in ing_words if not conforms(w, s)]

    print(f"ing-ending words: {len(ing_words)}")
    print(f"conform: {len(ing_words) - len(bad)}")
    print(f"VIOLATE: {len(bad)}")
    print()
    print("=== VIOLATIONS (word | segments | type) ===")
    for w, s in bad:
        tag = "doubled" if doubled(w) else "normal"
        print(f"{w:<24} {'.'.join(s):<34} {tag}")


if __name__ == "__main__":
    main()
