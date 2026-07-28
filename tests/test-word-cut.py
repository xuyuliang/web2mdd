import json
import sys


def load_gre_words(path="tests/GRE-words.txt"):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ── Stage 1: 派生追溯 ────────────────────────────────────────

print("Loading word_derivations.json ...", file=sys.stderr)
with open("data/word_derivations.json", encoding="utf-8") as f:
    wd = json.load(f)
rev_index = {}
for i in range(len(wd["w"])):
    rev_index[wd["w"][i]] = {
        "base": wd["b"][i],
        "affix": wd["a"][i],
        "affix_type": "suffix" if wd["t"][i] == "s" else "prefix"
    }
print(f"Loaded: {len(rev_index)} reverse index entries", file=sys.stderr)


def trace_derivation(word, rev_index, depth=0, max_depth=10):
    if depth >= max_depth:
        return None
    info = rev_index.get(word)
    if info is None:
        return None
    base_word = info["base"]
    inner = trace_derivation(base_word, rev_index, depth + 1, max_depth)
    affix = info["affix"]
    affix_type = info["affix_type"]
    if affix_type == "suffix":
        if inner:
            return inner + [affix]
        return [base_word, affix]
    else:
        if inner:
            return [affix] + inner
        return [affix, base_word]


# ── Stage 2: 词根贪心匹配 ───────────────────────────────────

def parse_roots(roots_str):
    # Strip leading bullet mark (•) which is not part of the root
    roots_str = roots_str.lstrip("\u2022")
    parts = [r.strip() for r in roots_str.split(",")]
    if not parts:
        return set()
    # First item is the main root (strip leading -/* which are metadata)
    main = parts[0].lstrip("-*")
    forms = {main}
    for p in parts[1:]:
        if p.startswith("="):
            # Inseparable: 必须与主根结合
            forms.add(main + p[1:])
        elif p.startswith("-") or p.startswith("*"):
            # Optional: 只与主根结合，不加独立形式（避免误匹配）
            opt = p[1:]
            forms.add(main + opt)
        else:
            forms.add(p.lstrip("-*"))
    return forms


def load_entries(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["entries"]


def build_root_index(entries):
    root_map = {}
    for e in entries:
        forms = parse_roots(e["roots"])
        src = e.get("source", "")
        for f in forms:
            if len(f) >= 2:
                if f not in root_map or src == "affix":
                    root_map[f] = (f, e.get("langCode", ""), e["meaning"], e["roots"], src)
    by_length = sorted(root_map.values(), key=lambda x: -len(x[0]))
    return by_length


VOWELS = set("aeiouy")


def count_syllables(text):
    count = 0
    in_vowel = False
    for ch in text.lower():
        if ch in VOWELS:
            if not in_vowel:
                count += 1
                in_vowel = True
        else:
            in_vowel = False
    return count


def can_match_short_root(pos, segments, word_len, root_len):
    if root_len > 2:
        return True
    if pos == 0:
        return True
    for seg in segments:
        if seg["meaning"] is None:
            continue
        if seg["pos"] + len(seg["text"]) == pos:
            return True
    return False


def can_match_short_root_rtl(end_pos, segments, segment_len, root_len):
    if root_len > 2:
        return True
    if end_pos == segment_len - 1:
        return True
    for seg in segments:
        if seg["meaning"] is None:
            continue
        if end_pos + 1 == seg["pos"]:
            return True
    return False


def _best_next_info(pos, w, root_index):
    best_len = 0
    best_src = ""
    for r in root_index:
        rlen = len(r[0])
        if pos + rlen > len(w):
            continue
        if w[pos:pos + rlen] == r[0]:
            if rlen > best_len:
                best_len = rlen
                best_src = r[4] if len(r) > 4 else ""
    return best_len, best_src


def _best_prev_info(pos, w, root_index):
    best_len = 0
    best_src = ""
    for r in root_index:
        rlen = len(r[0])
        start = pos - rlen + 1
        if start < 0:
            continue
        if w[start:pos + 1] == r[0]:
            if rlen > best_len:
                best_len = rlen
                best_src = r[4] if len(r) > 4 else ""
    return best_len, best_src


def _find_candidates_ltr(pos, w, root_index, segments):
    candidates = []
    for r in root_index:
        rtext = r[0]
        rlen = len(rtext)
        if pos + rlen > len(w):
            continue
        if w[pos:pos + rlen] != rtext:
            continue
        if not can_match_short_root(pos, segments, len(w), rlen):
            continue
        candidates.append(r)
    return candidates


def _find_candidates_rtl(end_pos, w, root_index, segments):
    candidates = []
    for r in root_index:
        rtext = r[0]
        rlen = len(rtext)
        start = end_pos - rlen + 1
        if start < 0:
            continue
        if w[start:end_pos + 1] != rtext:
            continue
        if not can_match_short_root_rtl(end_pos, segments, len(w), rlen):
            continue
        candidates.append(r)
    return candidates


def _select_best_ltr(pos, w, root_index, candidates):
    best = candidates[0]
    best_src = best[4] if len(best) > 4 else ""
    best_next_len, best_next_src = _best_next_info(pos + len(best[0]), w, root_index)
    best_score = len(best[0]) + best_next_len + (0.5 if best_src == "affix" else 0) + (0.3 if best_next_src == "affix" else 0)
    for c in candidates[1:]:
        c_src = c[4] if len(c) > 4 else ""
        c_next_len, c_next_src = _best_next_info(pos + len(c[0]), w, root_index)
        c_score = len(c[0]) + c_next_len + (0.5 if c_src == "affix" else 0) + (0.3 if c_next_src == "affix" else 0)
        if c_score > best_score or (c_score == best_score and len(c[0]) < len(best[0])):
            best = c
            best_score = c_score
    return best


def _select_best_rtl(end_pos, w, root_index, candidates):
    best = candidates[0]
    best_src = best[4] if len(best) > 4 else ""
    best_prev_len, best_prev_src = _best_prev_info(end_pos - len(best[0]), w, root_index)
    best_score = len(best[0]) + best_prev_len + (0.5 if best_src == "affix" else 0) + (0.3 if best_prev_src == "affix" else 0)
    for c in candidates[1:]:
        c_src = c[4] if len(c) > 4 else ""
        c_prev_len, c_prev_src = _best_prev_info(end_pos - len(c[0]), w, root_index)
        c_score = len(c[0]) + c_prev_len + (0.5 if c_src == "affix" else 0) + (0.3 if c_prev_src == "affix" else 0)
        if c_score > best_score or (c_score == best_score and len(c[0]) < len(best[0])):
            best = c
            best_score = c_score
    return best


def match_one_pass(text, pos_offset, root_index, direction):
    w = text.lower()
    L = len(w)
    segments = []

    if direction == "ltr":
        i = 0
        while i < L:
            candidates = _find_candidates_ltr(i, w, root_index, segments)
            if candidates:
                best = _select_best_ltr(i, w, root_index, candidates)
                segments.append({
                    "text": text[i:i + len(best[0])],
                    "pos": pos_offset + i,
                    "meaning": best[2],
                    "source": best[4] if len(best) > 4 else "",
                })
                i += len(best[0])
            else:
                remaining = text[i:]
                if count_syllables(remaining) <= 1:
                    segments.append({"text": remaining, "pos": pos_offset + i, "meaning": None, "source": ""})
                    break
                segments.append({"text": text[i], "pos": pos_offset + i, "meaning": None, "source": ""})
                i += 1
    else:
        i = L - 1
        while i >= 0:
            candidates = _find_candidates_rtl(i, w, root_index, segments)
            if candidates:
                best = _select_best_rtl(i, w, root_index, candidates)
                start = i - len(best[0]) + 1
                segments.insert(0, {
                    "text": text[start:i + 1],
                    "pos": pos_offset + start,
                    "meaning": best[2],
                    "source": best[4] if len(best) > 4 else "",
                })
                i = start - 1
                if i >= 0:
                    remaining = text[:i + 1]
                    if count_syllables(remaining) <= 1:
                        segments.insert(0, {"text": remaining, "pos": pos_offset, "meaning": None, "source": ""})
                        break
            else:
                remaining = text[:i]
                if count_syllables(remaining) <= 1:
                    segments.insert(0, {"text": text[:i + 1], "pos": pos_offset, "meaning": None, "source": ""})
                    break
                segments.insert(0, {"text": text[i], "pos": pos_offset + i, "meaning": None, "source": ""})
                i -= 1

    return segments


def merge_unknowns(segments):
    merged = []
    for s in segments:
        if s["meaning"] is None and merged and merged[-1]["meaning"] is None:
            merged[-1]["text"] += s["text"]
        else:
            merged.append(dict(s))
    return merged


def segment_word(word, root_index):
    if count_syllables(word) <= 1:
        for r in root_index:
            if r[0] == word.lower():
                return [{"text": word, "meaning": r[2], "source": r[4] if len(r) > 4 else ""}]
        return [{"text": word, "meaning": None, "source": ""}]

    chunks = match_one_pass(word, 0, root_index, "rtl")
    segments = merge_unknowns(chunks)

    has_match = any(s["meaning"] is not None for s in segments)
    if not has_match:
        for seg in segments:
            del seg["pos"]
        return segments

    direction = "ltr"
    while True:
        any_new_match = False
        new_segments = []

        for seg in segments:
            if seg["meaning"] is not None:
                new_segments.append(seg)
                continue
            if count_syllables(seg["text"]) <= 1 and seg["text"].lower() not in ROOT_TEXTS:
                new_segments.append(seg)
                continue

            chunks = match_one_pass(seg["text"], seg["pos"], root_index, direction)
            for c in chunks:
                if c["meaning"] is not None:
                    any_new_match = True
                    break
            new_segments.extend(chunks)

        segments = merge_unknowns(new_segments)

        if not any_new_match:
            break

        direction = "ltr" if direction == "rtl" else "rtl"

    for seg in segments:
        del seg["pos"]

    return segments


SRC_LABEL = {"dict": "d", "affix": "a"}
ROOT_TEXTS = set()

def format_seg(segments):
    parts = []
    for s in segments:
        text = s["text"]
        if s["meaning"]:
            src = SRC_LABEL.get(s.get("source", ""), "")
            if src:
                parts.append(f"{text}{{{src}}}")
            else:
                parts.append(text)
        else:
            parts.append(f"[{text}]")
    return ".".join(parts)


# ── 加载词根 & affixes & 短单词 ──────────────────────────────

print("Loading etym-dictionary.json ...", file=sys.stderr)
ety_entries = load_entries("data/etym-dictionary.json")
for e in ety_entries:
    e["source"] = "dict"
print(f"Etym entries: {len(ety_entries)}", file=sys.stderr)

print("Loading affixes.json ...", file=sys.stderr)
affix_entries = load_entries("data/affixes.json")
for e in affix_entries:
    e["source"] = "affix"
print(f"Affix entries: {len(affix_entries)}", file=sys.stderr)

all_entries = ety_entries + affix_entries
root_index = build_root_index(all_entries)
ROOT_TEXTS.update(r[0] for r in root_index)
print(f"Unique root forms (etym + affixes): {len(root_index)}", file=sys.stderr)




# ── 流水线 ──────────────────────────────────────────────────

def apply_stage1_split(parts, word):
    """Find Stage1 parts that fully match as substrings to split the word.
    Non-matching parts are dropped; matching parts determine split positions."""
    intervals = []
    for part in parts:
        pos = word.find(part)
        if pos != -1:
            intervals.append((pos, pos + len(part)))
    if not intervals:
        return [word]
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces = []
    prev_end = 0
    for start, end in merged:
        if start > prev_end:
            pieces.append(word[prev_end:start])
        pieces.append(word[start:end])
        prev_end = end
    if prev_end < len(word):
        pieces.append(word[prev_end:])
    return pieces


def pipeline_segment(word):
    parts = trace_derivation(word, rev_index)
    if parts:
        aligned = apply_stage1_split(parts, word)
        final_segs = []
        for p in aligned:
            sub = segment_word(p, root_index)
            final_segs.extend(sub)
        return parts, final_segs
    else:
        return None, segment_word(word, root_index)


# ── 输出 ────────────────────────────────────────────────────

words = load_gre_words()
print()
print(f"{'Word':<20} {'Stage1 Crosstem':<48} {'Stage2 Pipeline  {d}=dict {a}=affix'}")
print("-" * 125)

pipeline_found = 0
for w in words:
    crosstem_parts, final_segs = pipeline_segment(w)
    if crosstem_parts:
        crosstem_str = ".".join(crosstem_parts)
    else:
        crosstem_str = "(not found)"
    pipeline_str = format_seg(final_segs)
    has_roots = any(s["meaning"] for s in final_segs)
    if has_roots:
        pipeline_found += 1
    print(f"{w:<20} {crosstem_str:<48} {pipeline_str}")

print(f"\n总计: {len(words)}  |  Stage2 命中词根: {pipeline_found}")
