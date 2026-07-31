"""Score algorithm output against newGREwords_standard.json and write details."""

import json, sys
sys.path.insert(0, '.')
from app.word_cutter import WordCutter

SRC_LABEL = {"dict": "d", "affix": "a"}


def format_parts(parts):
    pieces = []
    for p in parts:
        text = p["text"]
        src = SRC_LABEL.get(p.get("source", ""), "")
        if p.get("meaning"):
            pieces.append(f"{text}{{{src}}}" if src else text)
        else:
            pieces.append(f"[{text}]")
    return ".".join(pieces)


wc = WordCutter()
standard = json.load(open("tests/newGREwords_standard.json", encoding="utf-8"))
total = len(standard)
exact = 0
details = []

for ref in standard:
    word = ref["word"]
    cur = wc.segment(word)
    cur_parts = format_parts(cur["parts"])
    ok = cur_parts == ref["parts"]
    if ok:
        exact += 1
    details.append((word, ok, ref["parts"], cur_parts))

exact_pct = 100 * exact / total
wrong = total - exact

print(f"Score: {exact}/{total} = {exact_pct:.1f}%")
print(f"Mismatches: {wrong}")
print()
print(f"{'Word':<20} {'Expected':<40} {'Got'}")
print("-" * 100)
for word, ok, exp, got in details:
    if not ok:
        print(f"{word:<20} {exp:<40} {got}")
print()
print("Details written to: tests/newGRE_score_details.txt")

with open("tests/newGRE_score_details.txt", "w", encoding="utf-8") as f:
    f.write(f"Score: {exact}/{total} = {exact_pct:.1f}%\n")
    f.write(f"Mismatches: {wrong}\n\n")
    f.write(f"{'Word':<20} {'Expected':<40} {'Got':<40} {'OK'}\n")
    f.write("-" * 105 + "\n")
    for word, ok, exp, got in details:
        f.write(f"{word:<20} {exp:<40} {got:<40} {'✓' if ok else '✗'}\n")
