import json
import math
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
    SEG_COST = 2.0
    GAP_COST = 1.0
    debug = False

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.rev_index = self._load_rev_index(base_dir)
        self.root_index, self.max_root_len = self._load_unified_index(base_dir)
        self.high_freq, self.high_freq_pos = self._load_high_freq(base_dir)
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
        path = os.path.join(base_dir, "数据资料", "highfreq.json")
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
        freq = {}
        pos_map = {}
        for e in entries:
            form = (e.get("affix") or "").strip("-").strip().lower()
            if len(form) < 2:
                continue
            n = e.get("次数") or 0
            freq[form] = max(freq.get(form, 0), n)
            t = e.get("type", "")
            if t:
                pos_map.setdefault(form, set()).add(t)
        return freq, {f: frozenset(t) for f, t in pos_map.items()}

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

    # ── Stage 2: global optimal DAG segmentation ────────────────

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
    def _secondary_score(text, high_freq, opt=False):
        penalty = WordCutter.OPT_PENALTY if opt else 0
        bonus = 0.0
        n = high_freq.get(text)
        if n is not None and n >= 3:
            bonus = 0.5 + 0.25 * math.log2(n / 3)
        return bonus - penalty

    @staticmethod
    def _pos_allowed(pos_types, abs_pos, rlen, word_len):
        """位置约束：纯前缀不能在词尾，纯后缀不能在词首；其余位置不限。"""
        if not pos_types:
            return True
        if pos_types == frozenset({"prefix"}) and abs_pos + rlen == word_len:
            return False
        if pos_types == frozenset({"suffix"}) and abs_pos == 0:
            return False
        return True

    @staticmethod
    def _find_candidates_dp(pos, w, root_index, abs_off, word_len, max_len, prev_matched):
        candidates = []
        limit = min(max_len, len(w) - pos)
        for L in range(1, limit + 1):
            form = w[pos:pos + L]
            interps = root_index.get(form)
            if not interps:
                continue
            for interp in interps:
                if not WordCutter._pos_allowed(interp["pos"], abs_off + pos, L, word_len):
                    continue
                hf_types = WordCutter.hf_pos_map.get(form)
                if not WordCutter._pos_allowed(hf_types, abs_off + pos, L, word_len):
                    continue
                if L <= 2 and not (pos == 0 or prev_matched):
                    continue
                candidates.append((form, interp))
        return candidates

    @staticmethod
    def _segment_global(word, abs_base, root_index, word_len, max_len, high_freq):
        w = word.lower()
        L = len(w)
        memo = {}
        for pos in range(L, -1, -1):
            for prev_matched in (False, True):
                if pos == L:
                    memo[(pos, prev_matched)] = ((0.0, 0.0, 0, 0, 0), None)
                    continue
                edge_list = []
                tail = memo[(pos + 1, False)]
                t = tail[0]
                edge_list.append((
                    (t[0] - WordCutter.GAP_COST, t[1], t[2], t[3], 0),
                    ("gap", pos + 1, False, None, None, False, pos),
                ))
                for form, interp in WordCutter._find_candidates_dp(
                    pos, w, root_index, abs_base, word_len, max_len, prev_matched
                ):
                    Lm = len(form)
                    end = pos + Lm
                    sec = WordCutter._secondary_score(form, high_freq, interp["opt"])
                    tail = memo[(end, True)]
                    t = tail[0]
                    ec = 1 if (Lm == 2 and (pos == 0 or end == L)) else 0
                    edge_list.append((
                        (
                            t[0] + (Lm - WordCutter.SEG_COST),
                            t[1] + sec,
                            t[2] - 1,
                            t[3] - ec,
                            Lm,
                        ),
                        ("match", end, True, form, interp, False, pos),
                    ))
                    if end < L and w[end] in WordCutter.VOWELS and w[end - 1] not in WordCutter.VOWELS:
                        tail = memo[(end + 1, True)]
                        t = tail[0]
                        edge_list.append((
                            (
                                t[0] + (Lm - WordCutter.SEG_COST),
                                t[1] + sec,
                                t[2] - 1,
                                t[3],
                                Lm + 1,
                            ),
                            ("absorb_r", end + 1, True, form, interp, False, pos),
                        ))
                    if w[end - 1] in WordCutter.VOWELS:
                        j = end - 1
                        for Lo in range(2, min(max_len, L - j) + 1):
                            form2 = w[j:j + Lo]
                            interps2 = root_index.get(form2)
                            if not interps2:
                                continue
                            for interp2 in interps2:
                                if not WordCutter._pos_allowed(interp2["pos"], abs_base + j, Lo, word_len):
                                    continue
                                hf2 = WordCutter.hf_pos_map.get(form2)
                                if not WordCutter._pos_allowed(hf2, abs_base + j, Lo, word_len):
                                    continue
                                tail = memo[(j + Lo, True)]
                                t = tail[0]
                                ec1 = 1 if (Lm == 2 and pos == 0) else 0
                                ec2 = 1 if (Lo == 2 and j + Lo == L) else 0
                                edge_list.append((
                                    (
                                        t[0] + (Lm + Lo - 1 - 2 * WordCutter.SEG_COST),
                                        t[1] + sec + WordCutter._secondary_score(form2, high_freq, interp2["opt"]),
                                        t[2] - 2,
                                        t[3] - ec1 - ec2,
                                        Lo,
                                    ),
                                    ("elide", j + Lo, True, form, interp, False, pos, form2, interp2, j),
                                ))
                if pos + 1 < L and w[pos] not in WordCutter.VOWELS and w[pos + 1] in WordCutter.VOWELS:
                    for form2, interp2 in WordCutter._find_candidates_dp(
                        pos + 1, w, root_index, abs_base, word_len, max_len, True
                    ):
                        Lm2 = len(form2)
                        sec2 = WordCutter._secondary_score(form2, high_freq, interp2["opt"])
                        tail = memo[(pos + 1 + Lm2, True)]
                        t = tail[0]
                        edge_list.append((
                            (
                                t[0] + (Lm2 - WordCutter.SEG_COST),
                                t[1] + sec2,
                                t[2] - 1,
                                t[3],
                                Lm2 + 1,
                            ),
                            ("absorb_l", pos + 1 + Lm2, True, form2, interp2, False, pos),
                        ))
                edge_list.sort(key=lambda e: e[0], reverse=True)
                best_key, best_bp = edge_list[0]
                if (
                    best_bp[0] != "gap"
                    and best_bp[4]["src"] == "affix"
                    and sum(1 for e in edge_list if e[1][0] != "gap" and e[0] == best_key) >= 2
                ):
                    best_bp = (best_bp[0], best_bp[1], best_bp[2], best_bp[3], best_bp[4], True, best_bp[6])
                memo[(pos, prev_matched)] = (best_key, best_bp)
        segments = []
        pos, prev_matched = 0, False
        while pos < L:
            bp = memo[(pos, prev_matched)][1]
            etype, npos, nprev, form, interp, hf, seg_start = bp[:7]
            if etype == "gap":
                segments.append({
                    "text": word[pos],
                    "pos": abs_base + pos,
                    "meaning": None,
                    "source": "",
                    "langCode": "",
                    "hf_decided": False,
                })
            elif etype == "elide":
                form2, interp2, j = bp[7], bp[8], bp[9]
                segments.append({
                    "text": word[seg_start:j + 1],
                    "pos": abs_base + seg_start,
                    "meaning": interp["meaning"],
                    "source": interp["src"],
                    "langCode": interp["lang"],
                    "hf_decided": hf,
                })
                segments.append({
                    "text": word[j:npos],
                    "pos": abs_base + j,
                    "meaning": interp2["meaning"],
                    "source": interp2["src"],
                    "langCode": interp2["lang"],
                    "hf_decided": False,
                })
            else:
                segments.append({
                    "text": word[seg_start:npos],
                    "pos": abs_base + seg_start,
                    "meaning": interp["meaning"],
                    "source": interp["src"],
                    "langCode": interp["lang"],
                    "hf_decided": hf,
                })
            pos, prev_matched = npos, nprev
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

        chunks = self._segment_global(word, abs_base, root_index, word_len, max_len, high_freq)
        segments = self._merge_unknowns(chunks)

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
