import json


def load_ety_dictionary(path="data/etym-dictionary.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_gre_words(path="tests/GRE-words.txt"):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_roots(roots_str):
    """Parse a roots field like 'pugn, -a, -ac, =ax' into clean root forms."""
    parts = [r.strip() for r in roots_str.split(",")]
    forms = set()
    for p in parts:
        if p.startswith("="):
            forms.add(p[1:])
        elif p.startswith("-") or p.startswith("*"):
            forms.add(p[1:])
        else:
            forms.add(p)
    return forms


def build_root_index(entries):
    """Build a length-sorted index of all root forms from the dictionary."""
    root_map = {}  # root_text -> (root_text, langCode, meaning, raw)
    for e in entries:
        forms = parse_roots(e["roots"])
        for f in forms:
            if len(f) >= 2 and f not in root_map:
                root_map[f] = (f, e["langCode"], e["meaning"], e["roots"])
    by_length = sorted(root_map.values(), key=lambda x: -len(x[0]))
    return by_length


def can_match_short_root(pos, segments, word_len, root_len):
    """A 2-char root is valid only at word start or adjacent to a matched root (not residue)."""
    if root_len > 2:
        return True
    if pos == 0:
        return True
    for seg in segments:
        if seg["meaning"] is None:
            continue
        seg_end = seg["pos"] + len(seg["text"])
        if seg_end == pos:
            return True
    return False


def segment_word(word, root_index):
    """Segment a word using greedy longest-match from the root index."""
    w = word.lower()
    segments = []  # list of {text, pos, lang, meaning, raw}
    i = 0

    while i < len(w):
        best = None
        for r in root_index:
            rtext = r[0]
            rlen = len(rtext)
            if i + rlen > len(w):
                continue
            if w[i:i+rlen] != rtext:
                continue
            if not can_match_short_root(i, segments, len(w), rlen):
                continue
            if best is None or rlen > len(best[0]):
                best = r

        if best:
            segments.append({
                "text": word[i:i+len(best[0])],
                "pos": i,
                "lang": best[1],
                "meaning": best[2],
                "raw": best[3]
            })
            i += len(best[0])
        else:
            # Skip one unmatched char as residue
            segments.append({
                "text": word[i],
                "pos": i,
                "lang": "",
                "meaning": None,
                "raw": ""
            })
            i += 1

    # Merge consecutive unmatched segments
    merged = []
    for s in segments:
        if s["meaning"] is None and merged and merged[-1]["meaning"] is None:
            merged[-1]["text"] += s["text"]
        else:
            merged.append(dict(s))

    # Remove "pos" from output, not needed
    for m in merged:
        del m["pos"]
    return merged


def format_seg(segments):
    parts = []
    for s in segments:
        if s["meaning"]:
            parts.append(s["text"])
        else:
            parts.append(f"[{s['text']}]")
    return ".".join(parts)


# Main
print("Loading etym-dictionary.json ...")
data = load_ety_dictionary()
entries = data["entries"]
root_index = build_root_index(entries)
print(f"Root entries: {len(entries)}")
print(f"Unique root forms: {len(root_index)}")
print()

words = load_gre_words()
print(f"{'Word':<20} {'Segmentation':<55} {'#Roots':>6}")
print("-" * 85)

found_any = 0
for w in words:
    segs = segment_word(w, root_index)
    seg_str = format_seg(segs)
    root_count = sum(1 for s in segs if s["meaning"])
    if root_count > 0:
        found_any += 1
    print(f"{w:<20} {seg_str:<55} {root_count:>6}")

print(f"\n总计: {len(words)}  |  命中词根: {found_any}")
