import json
import os


class WordCutter:
    """Two-stage word segmentation pipeline.

    Stage 1: crosstem derivation tracing (word_derivations.json)
    Stage 2: greedy root matching (data/roots.json)

    roots.json 是统一词根结构：以基础根为键，每个条目持有 ety 的扩展标示
    （ext，含 - 可选 / = 固有）与 affix 的位置信息（forms[form].pos）。
    加载时展平为 form -> [interpretation, ...] 的 dict，O(1) 前缀探测。
    """

    SRC_LABEL = {"dict": "d", "affix": "a"}
    VOWELS = set("aeiouy")
    OPT_PENALTY = 0.5
    debug = False

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.rev_index = self._load_rev_index(base_dir)
        self.root_index, self.max_root_len = self._load_unified_index(base_dir)
        self.high_freq_pos = self._load_high_freq(base_dir)
        self.high_freq = set(self.high_freq_pos)
        WordCutter.hf_pos_map = self.high_freq_pos

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

    def _load_unified_index(self, base_dir):
        path = os.path.join(base_dir, "data", "roots.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        root_index = {}
        max_len = 0
        for base, entry in data["entries"].items():
            src = "dict" if entry.get("ety_meaning") else "affix"
            if src == "dict":
                ety_m = entry.get("ety_meaning") or ""
                if "see also" in ety_m.lower() or ";;" in ety_m:
                    meaning = entry.get("meaning") or ""
                    lang = entry.get("lang") or ""
                else:
                    meaning = ety_m
                    lang = entry.get("ety_lang") or entry.get("lang") or ""
            else:
                meaning = entry.get("meaning") or ""
                lang = entry.get("lang") or ""
            for raw_form, meta in entry["forms"].items():
                form = raw_form.lower()
                if not form or len(form) < 2:
                    continue
                interp = {
                    "base": base,
                    "opt": bool(meta.get("opt", False)),
                    "pos": frozenset(meta.get("pos", [])),
                    "meaning": meaning,
                    "lang": lang,
                    "src": src,
                }
                root_index.setdefault(form, []).append(interp)
                if len(form) > max_len:
                    max_len = len(form)
        for form, interps in root_index.items():
            root_index[form] = sorted(interps, key=lambda i: i["base"].lower() != form)
        return root_index, max_len

    def _load_high_freq(self, base_dir):
        path = os.path.join(base_dir, "data", "high-freq-affixes.json")
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
        pos_map = {}
        for e in entries:
            form = (e.get("affix") or "").strip("-").strip().lower()
            if len(form) < 2:
                continue
            pos_map.setdefault(form, set()).add(e.get("type", ""))
        return {f: frozenset(t) for f, t in pos_map.items()}

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
            return [(word, 0)]
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
                pieces.append((word[prev_end:start], prev_end))
            pieces.append((word[start:end], start))
            prev_end = end
        if prev_end < len(word):
            pieces.append((word[prev_end:], prev_end))
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
    def _pos_allowed(interp, abs_pos, rlen, word_len):
        """位置约束：纯前缀不能在词尾，纯后缀不能在词首；其余位置不限。"""
        p = interp["pos"]
        if not p:
            return True
        if p == frozenset({"prefix"}) and abs_pos + rlen == word_len:
            return False
        if p == frozenset({"suffix"}) and abs_pos == 0:
            return False
        return True

    @staticmethod
    def _find_candidates_ltr(pos, w, root_index, segments, abs_off, word_len, max_len, relax_short=False):
        candidates = []
        limit = min(max_len, len(w) - pos)
        for L in range(1, limit + 1):
            form = w[pos:pos + L]
            interps = root_index.get(form)
            if not interps:
                continue
            for interp in interps:
                if not WordCutter._pos_allowed(interp, abs_off + pos, L, word_len):
                    continue
                if not WordCutter._hf_pos_allowed(form, abs_off + pos, L, word_len):
                    continue
                if not relax_short and not WordCutter._can_match_short_root(pos, segments, len(w), L):
                    continue
                candidates.append((w[pos:pos + L], interp))
        return candidates

    @staticmethod
    def _find_candidates_rtl(end_pos, w, root_index, segments, abs_off, word_len, max_len, relax_short=False):
        candidates = []
        limit = min(max_len, end_pos + 1)
        for L in range(1, limit + 1):
            start = end_pos - L + 1
            form = w[start:end_pos + 1]
            interps = root_index.get(form)
            if not interps:
                continue
            for interp in interps:
                if not WordCutter._pos_allowed(interp, abs_off + start, L, word_len):
                    continue
                if not WordCutter._hf_pos_allowed(form, abs_off + start, L, word_len):
                    continue
                if not relax_short and not WordCutter._can_match_short_root_rtl(end_pos, segments, len(w), L):
                    continue
                candidates.append((w[start:end_pos + 1], interp))
        return candidates

    @staticmethod
    def _best_path_ltr(pos, w, root_index, abs_off, word_len, max_len, memo=None):
        if memo is None:
            memo = {}
        if pos in memo:
            return memo[pos]
        candidates = WordCutter._find_candidates_ltr(
            pos, w, root_index, [], abs_off, word_len, max_len, relax_short=True
        )
        if candidates:
            best_cov = -1
            best_segs = float("inf")
            best_edge = False
            best_len = 0
            substr_len = len(w)
            for c in candidates:
                cov, segs, edge = WordCutter._best_path_ltr(
                    pos + len(c[0]), w, root_index, abs_off, word_len, max_len, memo
                )
                total = len(c[0]) + cov
                this_edge = (len(c[0]) == 2 and pos + len(c[0]) == substr_len) or edge
                if (
                    total > best_cov
                    or (total == best_cov and 1 + segs < best_segs)
                    or (total == best_cov and 1 + segs == best_segs and not this_edge and best_edge)
                    or (total == best_cov and 1 + segs == best_segs and this_edge == best_edge and len(c[0]) > best_len)
                ):
                    best_cov = total
                    best_segs = 1 + segs
                    best_edge = this_edge
                    best_len = len(c[0])
            memo[pos] = (best_cov, best_segs, best_edge)
            return memo[pos]
        remaining = w[pos:]
        if WordCutter._count_syllables(remaining) <= 1:
            memo[pos] = (0, 0, False)
            return memo[pos]
        memo[pos] = WordCutter._best_path_ltr(
            pos + 1, w, root_index, abs_off, word_len, max_len, memo
        )
        return memo[pos]

    @staticmethod
    def _best_path_rtl(end_pos, w, root_index, abs_off, word_len, max_len, memo=None):
        if memo is None:
            memo = {}
        if end_pos in memo:
            return memo[end_pos]
        candidates = WordCutter._find_candidates_rtl(
            end_pos, w, root_index, [], abs_off, word_len, max_len, relax_short=True
        )
        if candidates:
            best_cov = -1
            best_segs = float("inf")
            best_edge = False
            best_len = 0
            substr_len = len(w)
            for c in candidates:
                start = end_pos - len(c[0]) + 1
                cov, segs, edge = WordCutter._best_path_rtl(
                    start - 1, w, root_index, abs_off, word_len, max_len, memo
                )
                total = len(c[0]) + cov
                this_edge = (len(c[0]) == 2 and start == 0) or edge
                if (
                    total > best_cov
                    or (total == best_cov and 1 + segs < best_segs)
                    or (total == best_cov and 1 + segs == best_segs and not this_edge and best_edge)
                    or (total == best_cov and 1 + segs == best_segs and this_edge == best_edge and len(c[0]) > best_len)
                ):
                    best_cov = total
                    best_segs = 1 + segs
                    best_edge = this_edge
                    best_len = len(c[0])
            memo[end_pos] = (best_cov, best_segs, best_edge)
            return memo[end_pos]
        remaining = w[:end_pos + 1]
        if WordCutter._count_syllables(remaining) <= 1:
            memo[end_pos] = (0, 0, False)
            return memo[end_pos]
        memo[end_pos] = WordCutter._best_path_rtl(
            end_pos - 1, w, root_index, abs_off, word_len, max_len, memo
        )
        return memo[end_pos]

    @staticmethod
    def _candidate_score(text, cov, high_freq, opt=False):
        penalty = WordCutter.OPT_PENALTY if opt else 0
        return len(text) + cov + (0.5 if text in high_freq else 0) - penalty

    @staticmethod
    def _hf_pos_allowed(form, abs_pos, rlen, word_len):
        """高频位置约束：高频纯前缀只能在词首，纯后缀只能在词尾。"""
        types = WordCutter.hf_pos_map.get(form)
        if not types:
            return True
        if types == frozenset({"prefix"}):
            return abs_pos == 0
        if types == frozenset({"suffix"}):
            return abs_pos + rlen == word_len
        return True

    @staticmethod
    def _select_best_ltr(pos, w, root_index, candidates, abs_off, word_len, max_len, high_freq):
        best = candidates[0]
        best_cov, best_segs, best_edge = WordCutter._best_path_ltr(
            pos + len(best[0]), w, root_index, abs_off, word_len, max_len
        )
        best_segs += 1
        best_score = WordCutter._candidate_score(best[0], best_cov, high_freq, best[1]["opt"])
        second_score = None
        if WordCutter.debug:
            print(f"  LTR pos={pos}: [{best[0]}]({best_score:.1f})", end="")
        for c in candidates[1:]:
            cov, segs, edge = WordCutter._best_path_ltr(
                pos + len(c[0]), w, root_index, abs_off, word_len, max_len
            )
            c_score = WordCutter._candidate_score(c[0], cov, high_freq, c[1]["opt"])
            c_segs = 1 + segs
            if WordCutter.debug:
                print(f" [{c[0]}]({c_score:.1f})", end="")
            if (
                c_score > best_score
                or (c_score == best_score and c_segs < best_segs)
                or (c_score == best_score and c_segs == best_segs and not edge and best_edge)
                or (c_score == best_score and c_segs == best_segs and edge == best_edge and len(c[0]) > len(best[0]))
            ):
                second_score = best_score
                best = c
                best_score = c_score
                best_segs = c_segs
                best_edge = edge
            elif second_score is None:
                second_score = c_score
        if WordCutter.debug:
            hf = second_score is not None and best_score == second_score
            print(f" → winner: [{best[0]}] hf_decided={hf and best[1]['src'] == 'affix'}")
        return best, second_score is not None and best_score == second_score

    @staticmethod
    def _select_best_rtl(end_pos, w, root_index, candidates, abs_off, word_len, max_len, high_freq):
        best = candidates[0]
        best_cov, best_segs, best_edge = WordCutter._best_path_rtl(
            end_pos - len(best[0]), w, root_index, abs_off, word_len, max_len
        )
        best_segs += 1
        best_score = WordCutter._candidate_score(best[0], best_cov, high_freq, best[1]["opt"])
        second_score = None
        if WordCutter.debug:
            print(f"  RTL end={end_pos}: [{best[0]}]({best_score:.1f})", end="")
        for c in candidates[1:]:
            cov, segs, edge = WordCutter._best_path_rtl(
                end_pos - len(c[0]), w, root_index, abs_off, word_len, max_len
            )
            c_score = WordCutter._candidate_score(c[0], cov, high_freq, c[1]["opt"])
            c_segs = 1 + segs
            if WordCutter.debug:
                print(f" [{c[0]}]({c_score:.1f})", end="")
            if (
                c_score > best_score
                or (c_score == best_score and c_segs < best_segs)
                or (c_score == best_score and c_segs == best_segs and not edge and best_edge)
                or (c_score == best_score and c_segs == best_segs and edge == best_edge and len(c[0]) > len(best[0]))
            ):
                second_score = best_score
                best = c
                best_score = c_score
                best_segs = c_segs
                best_edge = edge
            elif second_score is None:
                second_score = c_score
        if WordCutter.debug:
            hf = second_score is not None and best_score == second_score
            print(f" → winner: [{best[0]}] hf_decided={hf and best[1]['src'] == 'affix'}")
        return best, second_score is not None and best_score == second_score

    @staticmethod
    def _match_one_pass(text, pos_offset, root_index, direction, word_len, max_len, high_freq):
        w = text.lower()
        L = len(w)
        segments = []

        if WordCutter.debug:
            print(f"\n  [{direction}] pass on '{text}':")

        if direction == "ltr":
            i = 0
            while i < L:
                candidates = WordCutter._find_candidates_ltr(
                    i, w, root_index, segments, pos_offset, word_len, max_len
                )
                if candidates:
                    best, tied = WordCutter._select_best_ltr(
                        i, w, root_index, candidates, pos_offset, word_len, max_len, high_freq
                    )
                    segments.append({
                        "text": text[i:i + len(best[0])],
                        "pos": pos_offset + i,
                        "meaning": best[1]["meaning"],
                        "source": best[1]["src"],
                        "langCode": best[1]["lang"],
                        "hf_decided": tied and best[1]["src"] == "affix",
                    })
                    if WordCutter.debug:
                        print(f"    LTR match at {i}: [{best[0]}] ({best[1]['meaning']}) hf_decided={tied and best[1]['src'] == 'affix'}")
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
                candidates = WordCutter._find_candidates_rtl(
                    i, w, root_index, segments, pos_offset, word_len, max_len
                )
                if candidates:
                    best, tied = WordCutter._select_best_rtl(
                        i, w, root_index, candidates, pos_offset, word_len, max_len, high_freq
                    )
                    start = i - len(best[0]) + 1
                    segments.insert(0, {
                        "text": text[start:i + 1],
                        "pos": pos_offset + start,
                        "meaning": best[1]["meaning"],
                        "source": best[1]["src"],
                        "langCode": best[1]["lang"],
                        "hf_decided": tied and best[1]["src"] == "affix",
                    })
                    if WordCutter.debug:
                        print(f"    RTL match end={i}: [{best[0]}] ({best[1]['meaning']}) hf_decided={tied and best[1]['src'] == 'affix'}")
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
        return text.lower() in root_index

    def _segment_word(self, word, root_index, max_len, abs_base, word_len, high_freq):
        if self._count_syllables(word) <= 1:
            interps = root_index.get(word.lower())
            if interps:
                interp = interps[0]
                return [{
                    "text": word,
                    "meaning": interp["meaning"],
                    "source": interp["src"],
                    "langCode": interp["lang"],
                }]
            return [{"text": word, "meaning": None, "source": "", "langCode": ""}]

        chunks = self._match_one_pass(word, abs_base, root_index, "rtl", word_len, max_len, high_freq)
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

                chunks = self._match_one_pass(seg["text"], seg["pos"], root_index, direction, word_len, max_len, high_freq)
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
            for p, off in aligned:
                sub = self._segment_word(p, self.root_index, self.max_root_len, off, len(word), self.high_freq)
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
            segs = self._segment_word(word, self.root_index, self.max_root_len, 0, len(word), self.high_freq)
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
