"""Score algorithm output against human-curated standard."""

import sys, re
sys.path.insert(0, '.')
from app.word_cutter import WordCutter

SRC_LABEL = {"dict": "d", "affix": "a"}


def load_human_standard(path="tests/human_standard.txt"):
    ref = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            word, segs = line.split(":", 1)
            ref[word.strip()] = segs.strip()
    return ref


def algo_format(word, wc):
    r = wc.segment(word)
    pieces = []
    for p in r["parts"]:
        text = p["text"]
        src = SRC_LABEL.get(p.get("source", ""), "")
        if p.get("meaning"):
            pieces.append(f"{text}{{{src}}}" if src else text)
        else:
            pieces.append(f"[{text}]")
    return ".".join(pieces)


def strip_sources(s):
    return re.sub(r"\{[a-z]+\}", "", s)


def parse_segments(s):
    parts = re.split(r"\.(?![^\[]*\])", s)
    result = []
    for p in parts:
        is_unk = p.startswith("[") and p.endswith("]")
        text = p.strip("[]")
        result.append((text, is_unk))
    return result


def compare_seg_lists(std_segs, algo_segs):
    if len(std_segs) != len(algo_segs):
        return False
    for (st, su), (at, au) in zip(std_segs, algo_segs):
        if st != at:
            return False
    return True


wc = WordCutter()
standard = load_human_standard()
total = len(standard)
exact = 0
details = []

for word, std_seg_str in sorted(standard.items()):
    cur_seg_str = algo_format(word, wc)
    std_segs = parse_segments(std_seg_str)
    cur_segs = parse_segments(strip_sources(cur_seg_str))

    is_match = compare_seg_lists(std_segs, cur_segs)
    if is_match:
        exact += 1

    details.append((word, is_match, std_seg_str, cur_seg_str))

# Report
exact_pct = 100 * exact / total
wrong = total - exact

print(f"Score: {exact}/{total} = {exact_pct:.1f}%")
print(f"Mismatches: {wrong}")
print()

if wrong:
    print(f"{'Word':<20} {'Expected':<40} {'Got'}")
    print("-" * 100)
    for word, ok, exp, got in details:
        if not ok:
            print(f"{word:<20} {exp:<40} {got}")
    print()
print(f"Details written to: tests/human_score_details.txt")

# Write detailed results
with open("tests/human_score_details.txt", "w", encoding="utf-8") as f:
    f.write(f"Score: {exact}/{total} = {exact_pct:.1f}%\n")
    f.write(f"Mismatches: {wrong}\n\n")
    f.write(f"{'Word':<20} {'Expected':<40} {'Got':<40} {'OK'}\n")
    f.write("-" * 105 + "\n")
    for word, ok, exp, got in details:
        f.write(f"{word:<20} {exp:<40} {got:<40} {'✓' if ok else '✗'}\n")
