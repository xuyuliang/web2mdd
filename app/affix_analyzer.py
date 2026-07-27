"""
基于 eng_derivations.json 和 eng_inflections.json 的词根词缀分析器
"""
import json
import os
import re
from typing import Optional


class AffixAnalyzer:
    def __init__(self, derivations_path=None, inflections_path=None, etym_path=None):
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.deriv_path = derivations_path or os.path.join(BASE_DIR, "data", "eng_derivations.json")
        self.infl_path = inflections_path or os.path.join(BASE_DIR, "data", "eng_inflections.json")
        self.etym_path = etym_path or os.path.join(BASE_DIR, "data", "etym-dictionary.json")

        self.deriv_reverse = {}
        self.deriv_forward = {}
        self.infl_reverse = {}
        self.infl_forward = set()
        self._word_set = set()
        self._etym_roots = {}
        self._prefixes = []
        self._suffixes = []
        self._loaded = False
        self._load()

    def _load(self):
        if not os.path.exists(self.deriv_path):
            print(f"[AffixAnalyzer] 警告: 文件不存在 {self.deriv_path}")
            return
        if not os.path.exists(self.infl_path):
            print(f"[AffixAnalyzer] 警告: 文件不存在 {self.infl_path}")
            return

        with open(self.deriv_path, "r", encoding="utf-8") as f:
            deriv_data = json.load(f)

        for base_word, info in deriv_data.items():
            base_lower = base_word.lower()
            self.deriv_forward.setdefault(base_lower, [])
            for derived, det in info.get("derives_to", {}).items():
                derived_lower = derived.lower()
                affix = det["affix"]
                affix_type = det["affix_type"]
                self.deriv_forward[base_lower].append((derived_lower, affix, affix_type))
                if not self._check_derivation(derived_lower, base_lower, affix, affix_type):
                    continue
                self.deriv_reverse.setdefault(derived_lower, [])
                self.deriv_reverse[derived_lower].append((base_lower, affix, affix_type))

        del deriv_data

        with open(self.infl_path, "r", encoding="utf-8") as f:
            infl_data = json.load(f)

        for lemma, info in infl_data.items():
            lemma_lower = lemma.lower()
            self.infl_forward.add(lemma_lower)
            for form, entries in info.get("forms", {}).items():
                form_lower = form.lower()
                for entry in entries:
                    seg = entry.get("segmentation", "")
                    features = entry.get("features", "")
                    suffix = ""
                    if "|" in seg:
                        _, suf = seg.split("|", 1)
                        suffix = suf
                if form_lower not in self.infl_reverse:
                    self.infl_reverse[form_lower] = (lemma_lower, suffix, features)
                else:
                    existing = self.infl_reverse[form_lower]
                    # 优先保存有实际词尾的屈折变化（前缀词作为 lemma 本身时词尾为空）
                    if not existing[1] and suffix:
                        self.infl_reverse[form_lower] = (lemma_lower, suffix, features)
                    elif not existing[1] and not suffix and lemma_lower != form_lower:
                        self.infl_reverse[form_lower] = (lemma_lower, suffix, features)

        self._word_set = set(self.deriv_forward.keys()) | self.infl_forward

        affix_dir = os.path.join(os.path.dirname(self.deriv_path), "..", "数据资料")
        pf_path = os.path.join(affix_dir, "_prefixes.txt")
        sf_path = os.path.join(affix_dir, "_suffixes.txt")
        if os.path.exists(pf_path):
            with open(pf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("共"):
                        continue
                    pfx = line.rstrip("-").lower()
                    if pfx:
                        self._prefixes.append(pfx)
        if os.path.exists(sf_path):
            with open(sf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("共"):
                        continue
                    sfx = line.lstrip("-").lower()
                    if sfx:
                        self._suffixes.append(sfx)
        self._prefixes.sort(key=len, reverse=True)
        self._suffixes.sort(key=len, reverse=True)

        self._load_etym()

        self._loaded = True
        print(f"[AffixAnalyzer] 加载完成: {len(self.deriv_forward)} 基词, "
              f"{len(self.deriv_reverse)} 可溯源派生词, "
              f"{len(self.infl_reverse)} 屈折形式, "
              f"{len(self._prefixes)} 前缀规则, {len(self._suffixes)} 后缀规则"
              f"{', ' + str(len(self._etym_roots)) + ' 词根' if self._etym_roots else ''}")

    def _load_etym(self):
        if not os.path.exists(self.etym_path):
            return
        try:
            with open(self.etym_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("entries", [])
            for e in entries:
                roots_str = e.get("roots", "")
                if not roots_str:
                    continue
                parts = [p.strip() for p in roots_str.split(",")]
                base = parts[0]
                if base.startswith(("=", "-")):
                    base = base[1:]

                variants = {base} if base else set()
                for p in parts[1:]:
                    p = p.strip()
                    if not p:
                        continue
                    if p.startswith("="):
                        variants.add(base + p[1:])
                    elif p.startswith("-"):
                        variants.add(base + p[1:])
                    else:
                        variants.add(p)

                for v in variants:
                    v = v.lstrip("-=")
                    if v and len(v) >= 2:
                        key = v.lower()
                        self._etym_roots.setdefault(key, [])
                        if e not in self._etym_roots[key]:
                            self._etym_roots[key].append(e)
        except Exception as ex:
            print(f"[AffixAnalyzer] 词根词典加载失败: {ex}")

    _COMMON_ENDINGS = ('y', 'a', 'o', 'i', 'e', 's', 'n', 'm', 'us', 'um', 'on', 'is', 'os', 'es', 'as', 'ae', 'en', 'in', 'ly')

    def _etym_analyze(self, word: str) -> Optional[dict]:
        if not self._etym_roots:
            return None

        best = None
        best_score = -1.0
        wlen = len(word)
        root_set = self._etym_roots
        all_suffixes = self._suffixes + list(self._COMMON_ENDINGS)

        def append_result(parts, result_str, prefix_val, suffix_val, stem_val, score):
            nonlocal best, best_score
            if score > best_score:
                best_score = score
                best = {
                    "prefix": prefix_val,
                    "suffix": suffix_val,
                    "stem": stem_val,
                    "final_stem": stem_val,
                    "result": result_str,
                    "parts": parts,
                    "score": score,
                    "scheme": "etym"
                }

        def try_suffix(tail, min_len=1):
            if not tail:
                return True, ""
            if len(tail) < min_len:
                return False, ""
            for sfx in all_suffixes:
                if len(sfx) < min_len:
                    continue
                if tail == sfx:
                    return True, sfx
            return False, ""

        # 1) prefix + root [+ suffix]
        for pfx in self._prefixes:
            if len(pfx) < 2:
                continue
            if not word.startswith(pfx) or len(word) - len(pfx) < 2:
                continue
            after_pfx = word[len(pfx):]
            for rlen in range(min(len(after_pfx), 20), 1, -1):
                cand_root = after_pfx[:rlen]
                if cand_root not in root_set:
                    continue
                tail = after_pfx[rlen:]
                ok, suffix = try_suffix(tail)
                if ok:
                    root_info = root_set[cand_root][0]
                    meaning = root_info.get("meaning", "")[:40]
                    lang = root_info.get("langCode", "")
                    pfx_info = root_set.get(pfx)
                    pfx_meaning = pfx_info[0].get("meaning", "")[:30] if pfx_info else ""
                    pfx_lang = pfx_info[0].get("langCode", "") if pfx_info else ""
                    parts = [{"type": "prefix", "text": pfx, "meaning": pfx_meaning, "lang": pfx_lang}]
                    parts.append({"type": "root", "text": cand_root, "meaning": meaning, "lang": lang})
                    if suffix:
                        parts.append({"type": "suffix", "text": suffix})
                    result_str = ".".join(p["text"] for p in parts if p["type"] != "prefix" or True)
                    # rebuild with proper order
                    result_parts = [p["text"] for p in parts]
                    result_str = ".".join(result_parts)
                    score = len(pfx) * 2 + rlen * 3 + (len(suffix) * 2 if suffix else 0) + (10 if suffix or not tail else 0)
                    append_result(parts, result_str, pfx, suffix, cand_root, score)

        # 2) root + suffix
        for sfx in all_suffixes:
            if len(sfx) < 1:
                continue
            if not word.endswith(sfx) or len(word) - len(sfx) < 2:
                continue
            before_sfx = word[:-len(sfx)]
            for rlen in range(2, min(len(before_sfx) + 1, 21)):
                cand_root = before_sfx[-rlen:]
                if cand_root not in root_set:
                    continue
                rest = before_sfx[:-rlen]
                if rest and not any(rest == p for p in self._prefixes):
                    continue
                pfx = rest if rest else ""
                root_info = root_set[cand_root][0]
                meaning = root_info.get("meaning", "")[:40]
                lang = root_info.get("langCode", "")
                parts = []
                if pfx:
                    parts.append({"type": "prefix", "text": pfx})
                parts.append({"type": "root", "text": cand_root, "meaning": meaning, "lang": lang})
                parts.append({"type": "suffix", "text": sfx})
                result_str = ".".join(p["text"] for p in parts)
                score = (len(pfx) * 2 if pfx else 0) + rlen * 3 + max(len(sfx), 1) * 2 + 10
                append_result(parts, result_str, pfx, sfx, cand_root, score)

        # 3) two roots (compound) + optional suffix
        for r1len in range(3, min(wlen, 21)):
            r1 = word[:r1len]
            if r1 not in root_set:
                continue
            rest = word[r1len:]
            for r2len in range(3, min(len(rest) + 1, 21)):
                r2 = rest[:r2len]
                if r2 not in root_set:
                    continue
                tail = rest[r2len:]
                ok, suffix = try_suffix(tail)
                if ok:
                    r1_info = root_set[r1][0]
                    r2_info = root_set[r2][0]
                    parts = [
                        {"type": "root", "text": r1, "meaning": r1_info.get("meaning", "")[:30], "lang": r1_info.get("langCode", "")},
                        {"type": "root", "text": r2, "meaning": r2_info.get("meaning", "")[:30], "lang": r2_info.get("langCode", "")},
                    ]
                    if suffix:
                        parts.append({"type": "suffix", "text": suffix})
                    result_str = ".".join(p["text"] for p in parts)
                    score = r1len * 2 + r2len * 3 + (len(suffix) * 2 if suffix else 0) + (15 if ok and (not tail or suffix) else 0)
                    append_result(parts, result_str, "", suffix, r1 + "." + r2, score)

        # 4) single root + short ending (when nothing else works)
        if not best:
            for rlen in range(3, min(wlen, 21)):
                for start in range(0, wlen - rlen + 1):
                    cand_root = word[start:start + rlen]
                    if cand_root not in root_set:
                        continue
                    prefix_part = word[:start]
                    suffix_part = word[start + rlen:]
                    ok_pfx = not prefix_part or any(prefix_part == p for p in self._prefixes)
                    ok_sfx, matched_sfx = try_suffix(suffix_part)
                    if ok_pfx and ok_sfx:
                        root_info = root_set[cand_root][0]
                        parts = []
                        if prefix_part:
                            parts.append({"type": "prefix", "text": prefix_part})
                        parts.append({"type": "root", "text": cand_root, "meaning": root_info.get("meaning", "")[:30]})
                        if matched_sfx:
                            parts.append({"type": "suffix", "text": matched_sfx})
                        result_str = ".".join(p["text"] for p in parts)
                        score = rlen * 3 + (len(prefix_part) * 2) + (len(matched_sfx) * 2 if matched_sfx else 0)
                        append_result(parts, result_str, prefix_part, matched_sfx, cand_root, score)

        return best

    @staticmethod
    def _check_derivation(word: str, base: str, affix: str, affix_type: str) -> bool:
        """验证派生关系是否合理：剥去词缀后的剩余部分应与词基长度相近"""
        if affix_type == "prefix":
            if not word.startswith(affix):
                return False
            rest = word[len(affix):]
        else:
            if not word.endswith(affix):
                return False
            rest = word[:-len(affix)]
        # 允许最多2个字符的拼写变化（如 y↔i、e脱落/添加）
        return abs(len(rest) - len(base)) <= 2

    def _pick_best(self, entries, word):
        """从多个有效的派生路径中选择最佳的一条"""
        best = None
        best_score = -1
        for base, affix, affix_type in entries:
            if not self._check_derivation(word, base, affix, affix_type):
                continue
            score = len(affix)
            if affix_type == "prefix" and word.startswith(affix):
                score += 2
            elif affix_type == "suffix" and word.endswith(affix):
                score += 2
            if score > best_score:
                best_score = score
                best = (base, affix, affix_type)
        return best

    def _analyze_one_hop(self, word, use_rule_fallback=False):
        entries = self.deriv_reverse.get(word)
        if entries:
            return self._pick_best(entries, word)
        if use_rule_fallback:
            return self._rule_one_hop(word)
        return None

    def _rule_fallback(self, word: str) -> Optional[dict]:
        best = None
        best_score = -1.0

        # Tier 1: 带词干验证（词干必须在词典中）
        for pfx in self._prefixes:
            if len(pfx) < 2:
                continue
            if not word.startswith(pfx) or len(word) - len(pfx) < 3:
                continue
            stem = word[len(pfx):]
            if stem in self._word_set:
                s = len(pfx) * 2.0 + len(stem) * 0.2
                if s > best_score:
                    best_score = s
                    best = (stem, pfx, "")

        for sfx in self._suffixes:
            if len(sfx) < 2:
                continue
            if not word.endswith(sfx) or len(word) - len(sfx) < 3:
                continue
            stem = word[:-len(sfx)]
            if stem in self._word_set:
                s = len(sfx) * 2.0 + len(stem) * 0.2
                if s > best_score:
                    best_score = s
                    best = (stem, "", sfx)

        for pfx in self._prefixes:
            if len(pfx) < 2:
                continue
            if not word.startswith(pfx):
                continue
            for sfx in self._suffixes:
                if len(sfx) < 2:
                    continue
                if not word.endswith(sfx) or len(pfx) + len(sfx) >= len(word):
                    continue
                stem = word[len(pfx):-len(sfx)]
                if len(stem) >= 3 and stem in self._word_set and word == pfx + stem + sfx:
                    s = (len(pfx) + len(sfx)) * 2.0 + len(stem) * 0.5
                    if s > best_score:
                        best_score = s
                        best = (stem, pfx, sfx)

        # Tier 2: 无词干验证，仅剥离后缀（≥3字符），词干至少4字符
        if not best:
            for sfx in self._suffixes:
                if len(sfx) < 3:
                    continue
                if not word.endswith(sfx) or len(word) - len(sfx) < 4:
                    continue
                stem = word[:-len(sfx)]
                if len(sfx) <= len(stem):
                    s = len(sfx) * 1.5
                    if s > best_score:
                        best_score = s
                        best = (stem, "", sfx)

        if not best:
            return None

        stem, pfx, sfx = best
        parts = []
        if pfx:
            parts.append({"type": "prefix", "text": pfx})
        parts.append({"type": "stem", "text": stem})
        if sfx:
            parts.append({"type": "suffix", "text": sfx})
        result_str = ".".join(p["text"] for p in parts)
        return {
            "prefix": pfx,
            "suffix": sfx,
            "stem": stem,
            "final_stem": stem,
            "result": result_str,
            "parts": parts,
            "score": best_score,
            "scheme": "rule" if best_score >= 3 else "rule_weak"
        }

    def _rule_one_hop(self, word):
        """用规则尝试一层拆分: 返回 (base, affix, affix_type) 或 None"""
        for sfx in self._suffixes:
            if len(sfx) < 2:
                continue
            if not word.endswith(sfx) or len(word) - len(sfx) < 3:
                continue
            stem = word[:-len(sfx)]
            if stem in self._word_set:
                return (stem, sfx, "suffix")
        for pfx in self._prefixes:
            if len(pfx) < 2:
                continue
            if not word.startswith(pfx) or len(word) - len(pfx) < 3:
                continue
            stem = word[len(pfx):]
            if stem in self._word_set:
                return (stem, pfx, "prefix")
        return None

    def _build_strategy(self, word, base, affix, affix_type, depth=0):
        """构建一个分析策略"""
        if affix_type == "prefix":
            prefix = affix
            suffix = ""
            result = f"{affix}.{base}"
        else:
            prefix = ""
            suffix = affix
            result = f"{base}.{affix}"

        return {
            "prefix": prefix,
            "suffix": suffix,
            "stem": base,
            "final_stem": base,
            "result": result,
            "parts": [
                {"type": affix_type, "text": affix},
                {"type": "stem", "text": base}
            ] if depth == 0 else [],
            "score": max(3.0, len(affix) * 0.5 + 2.0),
            "scheme": "derivation"
        }

    def _combine_strategies(self, word, s1, s2=None):
        """合并两层分析成一个完整的词根词缀分解"""
        if not s2:
            return s1

        # s1 is outer (direct analysis of word), s2 is inner (analysis of s1's stem)
        # Prefixes: outer first (s1 then s2)
        # Suffixes: inner first (s2 then s1, closest to stem)
        prefixes = []
        suffixes = []
        if s1["prefix"]:
            prefixes.append(s1["prefix"])
        if s2["prefix"]:
            prefixes.append(s2["prefix"])
        if s2["suffix"]:
            suffixes.append(s2["suffix"])
        if s1["suffix"]:
            suffixes.append(s1["suffix"])
        stem = s2["stem"] if s2 and s2["stem"] else s1["stem"]

        combined = {
            "prefix": "",
            "suffix": "",
            "stem": stem,
            "final_stem": stem,
            "result": ".".join(prefixes + [stem] + suffixes),
            "parts": [],
            "score": s1["score"] + s2["score"],
            "scheme": "combined"
        }

        if prefixes:
            combined["prefix"] = "".join(prefixes)
        if suffixes:
            combined["suffix"] = "".join(suffixes)

        for p in prefixes:
            combined["parts"].append({"type": "prefix", "text": p})
        combined["parts"].append({"type": "stem", "text": stem})
        for s in suffixes:
            combined["parts"].append({"type": "suffix", "text": s})

        return combined

    def analyze(self, word: str) -> Optional[dict]:
        word = word.strip().lower()
        if not word:
            return None

        strategies = []

        hop1 = self._analyze_one_hop(word)
        derivation_found = hop1 is not None
        if hop1:
            base1, affix1, type1 = hop1
            s1 = self._build_strategy(word, base1, affix1, type1, depth=0)
            strategies.append(s1)

            hop2 = self._analyze_one_hop(base1, use_rule_fallback=True)
            if hop2:
                base2, affix2, type2 = hop2
                s2 = self._build_strategy(base1, base2, affix2, type2, depth=1)
                strategies.append(s2)

                combined = self._combine_strategies(word, s1, s2)

                if combined["prefix"] and combined["suffix"]:
                    primary = combined
                else:
                    primary = s1
            else:
                primary = s1
        else:
            is_inflected = False
            if word in self.infl_reverse:
                lemma, suffix, _ = self.infl_reverse[word]
                if suffix and suffix != lemma:
                    is_inflected = True
                    parts = [{"type": "stem", "text": lemma}]
                    if suffix:
                        parts.append({"type": "suffix", "text": suffix})
                    result_str = ".".join(p["text"] for p in parts)
                    primary = {
                        "prefix": "",
                        "suffix": suffix,
                        "stem": lemma,
                        "final_stem": lemma,
                        "result": result_str,
                        "parts": parts,
                        "score": 3.0,
                        "scheme": "inflection"
                    }
                    strategies = [primary]

            if not is_inflected:
                rule_result = self._rule_fallback(word)
                etym_result = self._etym_analyze(word)

                word_is_base = word in self._word_set

                if etym_result and rule_result:
                    if etym_result["score"] > rule_result["score"] and (not word_is_base or etym_result["score"] >= 30):
                        primary = etym_result
                        strategies = [etym_result, rule_result]
                    else:
                        primary = rule_result
                        strategies = [rule_result, etym_result]
                elif etym_result and (not word_is_base or etym_result["score"] >= 30):
                    primary = etym_result
                    strategies = [etym_result]
                elif rule_result or word_is_base:
                    if rule_result:
                        primary = rule_result
                        strategies = [rule_result]
                    else:
                        primary = {
                            "prefix": "", "suffix": "", "stem": word, "final_stem": word,
                            "result": word, "parts": [{"type": "stem", "text": word}],
                            "score": 0.0, "scheme": "none"
                        }
                        strategies = [primary]
                else:
                    primary = {
                        "prefix": "", "suffix": "", "stem": word, "final_stem": word,
                        "result": word, "parts": [{"type": "stem", "text": word}],
                        "score": 0.0, "scheme": "none"
                    }
                    strategies = [primary]

        return {
            "word": word,
            "primary": primary,
            "all_strategies": strategies
        }

    def get_derived_words(self, word: str) -> list:
        word = word.lower().strip()
        return self.deriv_forward.get(word, [])


_analyzer: Optional[AffixAnalyzer] = None


def get_affix_analyzer() -> AffixAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = AffixAnalyzer()
    return _analyzer


if __name__ == "__main__":
    analyzer = AffixAnalyzer()

    test_words = [
        "nonsense", "sensory", "unhappiness", "nonsensical",
        "multiculturalism", "sensibly", "sense",
        "microtomes", "eating", "eaten", "cats",
        "unknown", "previously", "application", "applied",
        "helpfulness", "impossible", "antidisestablishment",
    ]

    print("=" * 60)
    print("AffixAnalyzer 测试")
    print("=" * 60)

    for word in test_words:
        result = analyzer.analyze(word)
        if result:
            p = result["primary"]
            print(f"\n单词: {word}")
            print(f"  拆分: {p['result']:35s} 得分: {p['score']:.1f}  方案: {p['scheme']}")
            if p['prefix']:
                print(f"  前缀: {p['prefix']}")
            print(f"  词干: {p['stem']}")
            if p['suffix']:
                print(f"  后缀: {p['suffix']}")
            if len(result.get("all_strategies", [])) > 1:
                print(f"  中间策略: {len(result['all_strategies'])-1} 个")
