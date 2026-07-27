"""
基于 eng_derivations.json 和 eng_inflections.json 的词根词缀分析器
"""
import json
import os
import re
from typing import Optional


class AffixAnalyzer:
    def __init__(self, derivations_path=None, inflections_path=None):
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.deriv_path = derivations_path or os.path.join(BASE_DIR, "data", "eng_derivations.json")
        self.infl_path = inflections_path or os.path.join(BASE_DIR, "data", "eng_inflections.json")

        self.deriv_reverse = {}
        self.deriv_forward = {}
        self.infl_reverse = {}
        self._word_set = set()
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

        self._word_set = set(self.deriv_forward.keys())

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

        self._loaded = True
        print(f"[AffixAnalyzer] 加载完成: {len(self.deriv_forward)} 基词, "
              f"{len(self.deriv_reverse)} 可溯源派生词, "
              f"{len(self.infl_reverse)} 屈折形式, "
              f"{len(self._prefixes)} 前缀规则, {len(self._suffixes)} 后缀规则")

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

    def _analyze_one_hop(self, word):
        """一层派生分析: 返回 (base, affix, affix_type) 或 None"""
        entries = self.deriv_reverse.get(word)
        if entries:
            return self._pick_best(entries, word)
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
        if hop1:
            base1, affix1, type1 = hop1
            s1 = self._build_strategy(word, base1, affix1, type1, depth=0)
            strategies.append(s1)

            hop2 = self._analyze_one_hop(base1)
            if hop2:
                base2, affix2, type2 = hop2
                s2 = self._build_strategy(base1, base2, affix2, type2, depth=1)
                strategies.append(s2)

                combined = self._combine_strategies(word, s1, s2)

                # Use combined as primary only when both prefix AND suffix are present
                # (avoids ugly concatenation like "iblely" or "yation")
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
                if rule_result:
                    primary = rule_result
                    strategies = [primary]
                else:
                    primary = {
                        "prefix": "",
                        "suffix": "",
                        "stem": word,
                        "final_stem": word,
                        "result": word,
                        "parts": [{"type": "stem", "text": word}],
                        "score": 0.0,
                        "scheme": "none"
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
