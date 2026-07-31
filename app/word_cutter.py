import json
import os


class WordCutter:
    """Two-stage word segmentation pipeline.

    Stage 1: crosstem derivation tracing (word_derivations.json)
    Stage 2: greedy root matching (etym-dictionary + affixes)
    """

    SRC_LABEL = {"dict": "d", "affix": "a"}
    VOWELS = set("aeiouy")
    debug = False

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.rev_index = self._load_rev_index(base_dir)
        self.root_index = self._build_combined_index(base_dir)

    # ── data loading ────────────────────────────────────────────

    def _load_rev_index(self, base_dir):
        path = os.path.join(base_dir, "data", "word_derivations.json")
        with open(path, encoding="utf-8") as f:
            wd = json.load(f)
        rev = {}
        for i in range(len(wd["w"])):
            rev[wd["w"][i]] = {
                "base": wd["b"][i],
                "affix": wd["a"][i],
                "affix_type": "suffix" if wd["t"][i] == "s" else "prefix",
            }
        return rev

    def _parse_roots(self, roots_str):
        roots_str = roots_str.lstrip("\u2022")
        parts = [r.strip() for r in roots_str.split(",")]
        if not parts:
            return set()
        main = parts[0].strip("-*")
        forms = {main}
        for p in parts[1:]:
            if p.startswith("="):
                forms.add(main + p[1:])
            elif p.startswith("-") or p.startswith("*"):
                forms.add(main + p[1:])
            else:
                forms.add(p.strip("-*"))
        return forms

    def _load_entries(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data["entries"]

    def _build_root_index(self, entries):
        root_map = {}
        for e in entries:
            forms = self._parse_roots(e["roots"])
            src = e.get("source", "")
            for f in forms:
                if len(f) >= 2:
                    if f not in root_map or src == "affix":
                        root_map[f] = (
                            f,
                            e.get("langCode", ""),
                            e["meaning"],
                            e["roots"],
                            src,
                        )
        by_length = sorted(root_map.values(), key=lambda x: -len(x[0]))
        return by_length

    def _build_combined_index(self, base_dir):
        ety_path = os.path.join(base_dir, "data", "etym-dictionary.json")
        affix_path = os.path.join(base_dir, "data", "affixes.json")

        ety_entries = self._load_entries(ety_path)
        for e in ety_entries:
            e["source"] = "dict"

        affix_entries = self._load_entries(affix_path)
        for e in affix_entries:
            e["source"] = "affix"

        all_entries = ety_entries + affix_entries
        return self._build_root_index(all_entries)

    # ── Stage 1: derivation tracing ─────────────────────────────

    def _trace_derivation(self, word, rev_index, depth=0, max_depth=10):
        if depth >= max_depth:
            return None
        info = rev_index.get(word)
        if info is None:
            return None
        base_word = info["base"]
        inner = self._trace_derivation(base_word, rev_index, depth + 1, max_depth)
        affix = info["affix"]
        if info["affix_type"] == "suffix":
            if inner:
                return inner + [affix]
            return [base_word, affix]
        else:
            if inner:
                return [affix] + inner
            return [affix, base_word]

    def _apply_stage1_split(self, parts, word):
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

    # ── Stage 2: alternating-direction greedy root matching ────

    @staticmethod
    def _count_syllables(text):
        count = 0
        in_vowel = False
        for i, ch in enumerate(text.lower()):
            if ch in WordCutter.VOWELS and not (i == 0 and ch == 'y'):
                if not in_vowel:
                    count += 1
                    in_vowel = True
            else:
                in_vowel = False
        return count

    @staticmethod
    def _can_match_short_root(pos, segments, word_len, root_len):
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

    @staticmethod
    def _can_match_short_root_rtl(end_pos, segments, segment_len, root_len):
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _best_path_ltr(pos, w, root_index, memo=None):
        if memo is None:
            memo = {}
        if pos in memo:
            return memo[pos]
        candidates = WordCutter._find_candidates_ltr(pos, w, root_index, [])
        if candidates:
            best = 0
            for c in candidates:
                total = len(c[0]) + WordCutter._best_path_ltr(pos + len(c[0]), w, root_index, memo)
                if total > best:
                    best = total
            memo[pos] = best
            return best
        remaining = w[pos:]
        if WordCutter._count_syllables(remaining) <= 1:
            memo[pos] = 0
            return 0
        memo[pos] = WordCutter._best_path_ltr(pos + 1, w, root_index, memo)
        return memo[pos]

    @staticmethod
    def _best_path_rtl(end_pos, w, root_index, memo=None):
        if memo is None:
            memo = {}
        if end_pos in memo:
            return memo[end_pos]
        candidates = WordCutter._find_candidates_rtl(end_pos, w, root_index, [])
        if candidates:
            best = 0
            for c in candidates:
                start = end_pos - len(c[0]) + 1
                total = len(c[0]) + WordCutter._best_path_rtl(start - 1, w, root_index, memo)
                if total > best:
                    best = total
            memo[end_pos] = best
            return best
        remaining = w[:end_pos + 1]
        if WordCutter._count_syllables(remaining) <= 1:
            memo[end_pos] = 0
            return 0
        memo[end_pos] = WordCutter._best_path_rtl(end_pos - 1, w, root_index, memo)
        return memo[end_pos]

    @staticmethod
    def _find_candidates_ltr(pos, w, root_index, segments):
        candidates = []
        for r in root_index:
            rtext = r[0]
            rlen = len(rtext)
            if pos + rlen > len(w):
                continue
            if w[pos:pos + rlen] != rtext:
                continue
            if not WordCutter._can_match_short_root(pos, segments, len(w), rlen):
                continue
            candidates.append(r)
        return candidates

    @staticmethod
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
            if not WordCutter._can_match_short_root_rtl(end_pos, segments, len(w), rlen):
                continue
            candidates.append(r)
        return candidates

    @staticmethod
    def _select_best_ltr(pos, w, root_index, candidates):
        best = candidates[0]
        best_score = len(best[0]) + WordCutter._best_path_ltr(pos + len(best[0]), w, root_index)
        second_score = None
        if WordCutter.debug:
            print(f"  LTR pos={pos}: [{best[0]}]({best_score:.1f})", end="")
        for c in candidates[1:]:
            c_score = len(c[0]) + WordCutter._best_path_ltr(pos + len(c[0]), w, root_index)
            if WordCutter.debug:
                print(f" [{c[0]}]({c_score:.1f})", end="")
            if c_score > best_score or (
                c_score == best_score and len(c[0]) > len(best[0])
            ):
                second_score = best_score
                best = c
                best_score = c_score
            elif second_score is None:
                second_score = c_score
        if WordCutter.debug:
            hf = second_score is not None and best_score == second_score
            print(f" → winner: [{best[0]}] hf_decided={hf and best[4] == 'affix'}")
        return best, second_score is not None and best_score == second_score

    @staticmethod
    def _select_best_rtl(end_pos, w, root_index, candidates):
        best = candidates[0]
        best_score = len(best[0]) + WordCutter._best_path_rtl(end_pos - len(best[0]), w, root_index)
        second_score = None
        if WordCutter.debug:
            print(f"  RTL end={end_pos}: [{best[0]}]({best_score:.1f})", end="")
        for c in candidates[1:]:
            c_score = len(c[0]) + WordCutter._best_path_rtl(end_pos - len(c[0]), w, root_index)
            if WordCutter.debug:
                print(f" [{c[0]}]({c_score:.1f})", end="")
            if c_score > best_score or (
                c_score == best_score and len(c[0]) > len(best[0])
            ):
                second_score = best_score
                best = c
                best_score = c_score
            elif second_score is None:
                second_score = c_score
        if WordCutter.debug:
            hf = second_score is not None and best_score == second_score
            print(f" → winner: [{best[0]}] hf_decided={hf and best[4] == 'affix'}")
        return best, second_score is not None and best_score == second_score

    @staticmethod
    def _match_one_pass(text, pos_offset, root_index, direction):
        w = text.lower()
        L = len(w)
        segments = []

        if WordCutter.debug:
            print(f"\n  [{direction}] pass on '{text}':")

        if direction == "ltr":
            i = 0
            while i < L:
                candidates = WordCutter._find_candidates_ltr(i, w, root_index, segments)
                if candidates:
                    best, tied = WordCutter._select_best_ltr(i, w, root_index, candidates)
                    segments.append({
                        "text": text[i:i + len(best[0])],
                        "pos": pos_offset + i,
                        "meaning": best[2],
                        "source": best[4] if len(best) > 4 else "",
                        "langCode": best[1],
                        "hf_decided": tied and best[4] == "affix",
                    })
                    if WordCutter.debug:
                        print(f"    LTR match at {i}: [{best[0]}] ({best[2]}) hf_decided={tied and best[4] == 'affix'}")
                    i += len(best[0])
                else:
                    remaining = text[i:]
                    if WordCutter._count_syllables(remaining) <= 1:
                        if WordCutter.debug:
                            print(f"    LTR no-candidate at {i}, remaining '{remaining}' ≤1 syll → stop")
                        segments.append({
                            "text": remaining,
                            "pos": pos_offset + i,
                            "meaning": None,
                            "source": "",
                            "langCode": "",
                        })
                        break
                    if WordCutter.debug:
                        print(f"    LTR no-candidate at {i}, skip 1 char '{text[i]}'")
                    segments.append({
                        "text": text[i],
                        "pos": pos_offset + i,
                        "meaning": None,
                        "source": "",
                        "langCode": "",
                    })
                    i += 1
        else:
            i = L - 1
            while i >= 0:
                candidates = WordCutter._find_candidates_rtl(i, w, root_index, segments)
                if candidates:
                    best, tied = WordCutter._select_best_rtl(i, w, root_index, candidates)
                    start = i - len(best[0]) + 1
                    segments.insert(0, {
                        "text": text[start:i + 1],
                        "pos": pos_offset + start,
                        "meaning": best[2],
                        "source": best[4] if len(best) > 4 else "",
                        "langCode": best[1],
                        "hf_decided": tied and best[4] == "affix",
                    })
                    if WordCutter.debug:
                        print(f"    RTL match end={i}: [{best[0]}] ({best[2]}) hf_decided={tied and best[4] == 'affix'}")
                    i = start - 1
                    if i >= 0:
                        remaining = text[:i + 1]
                        if WordCutter.debug:
                            print(f"    RTL leftover: '{remaining}' marked as unknown")
                        segments.insert(0, {
                            "text": remaining,
                            "pos": pos_offset,
                            "meaning": None,
                            "source": "",
                            "langCode": "",
                        })
                    break
                else:
                    remaining = text[:i]
                    if WordCutter._count_syllables(remaining) <= 1:
                        if WordCutter.debug:
                            print(f"    RTL no-candidate at {i}, remaining '{remaining}' ≤1 syll → stop")
                        segments.insert(0, {
                            "text": text[:i + 1],
                            "pos": pos_offset,
                            "meaning": None,
                            "source": "",
                            "langCode": "",
                        })
                        break
                    if WordCutter.debug:
                        print(f"    RTL no-candidate at {i}, skip 1 char '{text[i]}'")
                    segments.insert(0, {
                        "text": text[i],
                        "pos": pos_offset + i,
                        "meaning": None,
                        "source": "",
                        "langCode": "",
                    })
                    i -= 1

        return segments

    @staticmethod
    def _merge_unknowns(segments):
        merged = []
        for s in segments:
            if s["meaning"] is None and merged and merged[-1]["meaning"] is None:
                merged[-1]["text"] += s["text"]
            else:
                merged.append(dict(s))
        return merged

    def _has_exact_root(self, text, root_index):
        w = text.lower()
        for r in root_index:
            if r[0] == w:
                return True
        return False

    @staticmethod
    def _resolve_overlaps(segments, root_index):
        resolved = [dict(seg) for seg in segments]
        root_src = {}
        for r in root_index:
            root_src.setdefault(r[0], r[4])
        i = 0
        changed = False
        while i < len(resolved) - 1:
            left = resolved[i]
            right = resolved[i + 1]
            if left["meaning"] is not None and right["meaning"] is not None:
                right_text = right["text"].lower()
                overlap = left["text"][-1].lower() + right_text
                orig_src = root_src.get(right_text)
                ov_src = root_src.get(overlap)
                if orig_src == "dict" and ov_src == "affix":
                    left["text"] = left["text"][:-1]
                    right["text"] = overlap
                    changed = True
            i += 1
        if changed:
            return resolved
        return segments

    def _segment_word(self, word, root_index):
        if self._count_syllables(word) <= 1:
            for r in root_index:
                if r[0] == word.lower():
                    return [{
                        "text": word,
                        "meaning": r[2],
                        "source": r[4] if len(r) > 4 else "",
                        "langCode": r[1],
                    }]
            return [{"text": word, "meaning": None, "source": "", "langCode": ""}]

        chunks = self._match_one_pass(word, 0, root_index, "rtl")
        segments = self._merge_unknowns(chunks)

        has_match = any(s["meaning"] is not None for s in segments)
        if not has_match:
            if WordCutter.debug:
                print(f"  No match found, return as-is")
            for seg in segments:
                seg.pop("pos", None)
            return segments

        if WordCutter.debug:
            print(f"\n  After RTL: {[s['text'] for s in segments]}")

        direction = "ltr"
        loop_n = 0
        while True:
            loop_n += 1
            any_new_match = False
            new_segments = []

            for seg in segments:
                if seg["meaning"] is not None:
                    new_segments.append(seg)
                    continue
                if self._count_syllables(seg["text"]) <= 1 and not self._has_exact_root(seg["text"], root_index):
                    if WordCutter.debug:
                        print(f"  Loop#{loop_n} {direction}: skip '{seg['text']}' (≤1 syll, not in index)")
                    new_segments.append(seg)
                    continue

                chunks = self._match_one_pass(seg["text"], seg["pos"], root_index, direction)
                for c in chunks:
                    if c["meaning"] is not None:
                        any_new_match = True
                        break
                new_segments.extend(chunks)

            segments = self._merge_unknowns(new_segments)

            if WordCutter.debug:
                print(f"  Loop#{loop_n} {direction} result: {[s['text'] for s in segments]}")

            if not any_new_match:
                if WordCutter.debug:
                    print(f"  No new matches, done")
                break

            direction = "ltr" if direction == "rtl" else "rtl"

        segments = self._resolve_overlaps(segments, root_index)

        for seg in segments:
            seg.pop("pos", None)

        return segments

    # ── public API ──────────────────────────────────────────────

    def segment(self, word):
        if self._count_syllables(word) <= 1:
            return {
                "word": word,
                "stage1": None,
                "parts": [
                    {
                        "text": word,
                        "source": "",
                        "meaning": None,
                        "langCode": "",
                    }
                ],
            }
        parts = self._trace_derivation(word, self.rev_index)
        if parts:
            aligned = self._apply_stage1_split(parts, word)
            final_segs = []
            for p in aligned:
                sub = self._segment_word(p, self.root_index)
                final_segs.extend(sub)
            return {
                "word": word,
                "stage1": ".".join(parts),
                "parts": [
                    {
                        "text": s["text"],
                        "source": "h" if s.get("hf_decided") else self.SRC_LABEL.get(s.get("source", ""), ""),
                        "meaning": s.get("meaning"),
                        "langCode": s.get("langCode", ""),
                    }
                    for s in final_segs
                ],
            }
        else:
            segs = self._segment_word(word, self.root_index)
            return {
                "word": word,
                "stage1": None,
                "parts": [
                    {
                        "text": s["text"],
                        "source": "h" if s.get("hf_decided") else self.SRC_LABEL.get(s.get("source", ""), ""),
                        "meaning": s.get("meaning"),
                        "langCode": s.get("langCode", ""),
                    }
                    for s in segs
                ],
            }
