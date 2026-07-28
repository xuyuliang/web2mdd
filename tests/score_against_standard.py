"""Compare current algorithm output against gre_standard.json and score."""

import json
import sys
sys.path.insert(0, '.')

from app.word_cutter import WordCutter

SRC_LABEL = {"dict": "d", "affix": "a"}


def format_parts(parts):
    pieces = []
    for p in parts:
        text = p["text"]
        src = SRC_LABEL.get(p.get("source", ""), "")
        if p.get("meaning"):
            if src:
                pieces.append(f"{text}{{{src}}}")
            else:
                pieces.append(text)
        else:
            pieces.append(f"[{text}]")
    return ".".join(pieces)


def load_standard(path="tests/gre_standard.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


wc = WordCutter()
standard = load_standard()
total = len(standard)

exact_match = 0
parts_mismatch = 0
stage1_mismatch = 0
both_mismatch = 0
diff_words = []

for ref in standard:
    word = ref["word"]
    cur = wc.segment(word)

    cur_parts = format_parts(cur["parts"])
    cur_stage1 = cur.get("stage1")
    ref_parts = ref["parts"]
    ref_stage1 = ref["stage1"]

    parts_ok = cur_parts == ref_parts
    stage1_ok = cur_stage1 == ref_stage1

    if parts_ok and stage1_ok:
        exact_match += 1
    else:
        if not parts_ok and not stage1_ok:
            both_mismatch += 1
            diff_words.append((word, "BOTH", ref_parts, cur_parts, ref_stage1, cur_stage1))
        elif not parts_ok:
            parts_mismatch += 1
            diff_words.append((word, "PARTS", ref_parts, cur_parts, ref_stage1, cur_stage1))
        else:
            stage1_mismatch += 1
            diff_words.append((word, "STAGE1", ref_parts, cur_parts, ref_stage1, cur_stage1))

# Report
print(f"{'='*60}")
print(f"  Score: {exact_match}/{total} exact match ({100*exact_match/total:.1f}%)")
print(f"{'='*60}")
print(f"  Parts diff:   {parts_mismatch}")
print(f"  Stage1 diff:  {stage1_mismatch}")
print(f"  Both diff:    {both_mismatch}")
print(f"  Total diff:   {total - exact_match}")
print()

if diff_words:
    print(f"{'Word':<20} {'Type':<8} {'Reference':<50} {'Current'}")
    print("-" * 120)
    for w, typ, rp, cp, rs, cs in diff_words:
        ref_display = rp
        cur_display = cp
        if typ == "STAGE1":
            ref_display = f"{rp} (s1={rs})"
            cur_display = f"{cp} (s1={cs})"
        elif typ == "BOTH":
            ref_display = f"{rp} (s1={rs})"
            cur_display = f"{cp} (s1={cs})"
        print(f"{w:<20} {typ:<8} {ref_display:<50} {cur_display}")

print()
