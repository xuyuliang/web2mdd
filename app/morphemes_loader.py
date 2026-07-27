"""
词根词缀加载器 - 从 morphemes.json 加载前缀、后缀和词根数据
支持三种拆分策略，自动选择最优结果
"""
import json
import os
from typing import Dict, List, Tuple, Optional


class MorphPart:
    """匹配部分的数据结构"""
    def __init__(self, part_type: str, text: str, key: str = None, meaning: List = None):
        self.type = part_type  # "prefix", "suffix", "root", "stem"
        self.text = text
        self.key = key
        self.meaning = meaning or []
    
    def __repr__(self):
        return f"[{self.type}] '{self.text}' <- {self.key or 'N/A'}"


class MorphemesLoader:
    """加载并管理 morphemes.json 数据，提供单词拆分功能"""
    
    def __init__(self, filepath: str = None):
        self.prefixes: List[Tuple[str, str, str, List]] = []
        self.suffixes: List[Tuple[str, str, str, List]] = []
        self.roots: List[Tuple[str, str, str, List]] = []
        self._known_set: set = set()
        self._loaded = False
        
        if filepath:
            self.filepath = filepath
        else:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.filepath = os.path.join(BASE_DIR, "数据资料", "morphemes.json")
        
        self._load()
    
    def _load(self):
        """加载 morphemes.json 并提取匹配单元"""
        if not os.path.exists(self.filepath):
            print(f"[MorphemesLoader] 警告: 文件不存在 {self.filepath}")
            return
        
        with open(self.filepath, "r", encoding="utf-8") as f:
            morphemes = json.load(f)
        
        prefixes = []
        suffixes = []
        roots = []
        known_set = set()
        
        for key, value in morphemes.items():
            meaning = value.get("meaning", [])
            for form in value.get("forms", []):
                loc = form.get("loc", "")
                root = form.get("root", "")
                match_str = root.strip("-").lower()
                if match_str:
                    known_set.add(match_str)
                if match_str and loc == "prefix":
                    prefixes.append((match_str, root, key, meaning))
                elif match_str and loc == "suffix":
                    suffixes.append((match_str, root, key, meaning))
                elif match_str and loc == "embedded":
                    roots.append((match_str, root, key, meaning))
        
        # 按长度降序排列，确保最长匹配优先
        self.prefixes = sorted(prefixes, key=lambda x: len(x[0]), reverse=True)
        self.suffixes = sorted(suffixes, key=lambda x: len(x[0]), reverse=True)
        self.roots = sorted(roots, key=lambda x: len(x[0]), reverse=True)
        self._known_set = known_set
        
        self._loaded = True
        print(f"[MorphemesLoader] 加载完成: {len(prefixes)} 前缀, {len(suffixes)} 后缀, {len(roots)} 词根, {len(known_set)} 条目")
    
    def _find_next_prefix(self, text: str) -> Optional[MorphPart]:
        """在文本开头查找最长匹配的前缀"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.prefixes:
            if len(match_str) >= 2 and text.startswith(match_str):
                if len(match_str) > best_len:
                    best_len = len(match_str)
                    best_match = MorphPart("prefix", match_str, key, meaning)
        return best_match

    def _find_next_suffix(self, text: str) -> Optional[MorphPart]:
        """在文本末尾查找最长匹配的后缀"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.suffixes:
            if len(match_str) >= 2 and text.endswith(match_str):
                if len(match_str) > best_len:
                    best_len = len(match_str)
                    best_match = MorphPart("suffix", match_str, key, meaning)
        return best_match

    def _find_root(self, text: str) -> Optional[MorphPart]:
        """在文本中查找最长匹配的词根"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.roots:
            if len(match_str) < 3:
                continue
            pos = text.find(match_str)
            if pos != -1:
                if len(match_str) > best_len:
                    best_len = len(match_str)
                    best_match = MorphPart("root", match_str, key, meaning)
        return best_match

    def _reclassify_parts(self, parts: List[MorphPart]) -> None:
        if not parts:
            return
        last = parts[-1]
        if last.type == "stem" and len(last.text) >= 2:
            s = self._find_next_suffix(last.text)
            if s and s.text == last.text:
                parts[-1] = MorphPart("suffix", last.text, s.key, s.meaning)
        first = parts[0]
        if first.type == "stem" and len(first.text) >= 2:
            pfx = self._find_next_prefix(first.text)
            if pfx and pfx.text == first.text:
                parts[0] = MorphPart("prefix", first.text, pfx.key, pfx.meaning)

    def _score_parts(self, parts: List[MorphPart]) -> float:
        score = 0.0

        prefix_count = 0
        suffix_count = 0
        root_count = 0

        for p in parts:
            if p.type in ("prefix", "suffix", "root"):
                score += 2.0 + len(p.text) * 0.3
            if p.type == "prefix":
                prefix_count += 1
            elif p.type == "suffix":
                suffix_count += 1
            elif p.type == "root":
                root_count += 1

        # 词干在已知表中 → 加分
        for p in parts:
            if p.type == "stem" and len(p.text) >= 2 and p.text in self._known_set:
                score += 5.0

        # 碎片惩罚
        for p in parts:
            if p.type == "stem" and len(p.text) == 1:
                score -= 1.0

        # 超出有意义匹配数量的分块惩罚
        meaningful_count = prefix_count + suffix_count + root_count
        if meaningful_count > 0:
            excess_parts = max(0, len(parts) - meaningful_count)
            score -= excess_parts * 3.0

        # 完全未切分
        if len(parts) == 1 and parts[0].type == "stem":
            score -= 5.0

        return score

    def _build_result(self, parts: List[MorphPart], word: str) -> dict:
        result_str = ".".join(p.text for p in parts)
        return {
            "prefix": parts[0].text if parts and parts[0].type == "prefix" else "",
            "suffix": parts[-1].text if parts and parts[-1].type == "suffix" else "",
            "stem": ".".join(p.text for p in parts if p.type in ("stem", "root")),
            "result": result_str,
            "parts": parts,
            "score": self._score_parts(parts)
        }

    def _split(self, word: str) -> dict:
        """
        统一拆分算法：
        遍历 0..N 个前缀 × 0..M 个后缀的组合，剥离后剩余 ≥3 字符且非全词缀，评分选最优。
        找到的词根会从词干中分离出来。
        """
        candidates = []
        max_affixes = min(len(word) // 2, 15)

        for p_count in range(0, max_affixes + 1):
            mid = word
            prefixes = []
            ok = True
            for _ in range(p_count):
                p = self._find_next_prefix(mid)
                if not p:
                    ok = False
                    break
                prefixes.append(p)
                mid = mid[len(p.text):]
            if not ok:
                break

            for s_count in range(0, max_affixes + 1):
                stem = mid
                suffixes = []
                ok = True
                for _ in range(s_count):
                    s = self._find_next_suffix(stem)
                    if not s:
                        ok = False
                        break
                    suffixes.insert(0, s)
                    stem = stem[:-len(s.text)]
                if not ok:
                    break

                # 词干必须 ≥ 3
                if len(stem) < 3:
                    continue

                # 构建基础 parts
                parts = list(prefixes) + [MorphPart("stem", stem)] + list(suffixes)

                # 尝试在词干中找词根
                root_match = self._find_root(stem)
                if root_match:
                    root_pos = stem.find(root_match.text)
                    before = stem[:root_pos]
                    after = stem[root_pos + len(root_match.text):]
                    middle = []
                    if before:
                        middle.append(MorphPart("stem", before))
                    middle.append(root_match)
                    if after:
                        middle.append(MorphPart("stem", after))
                    parts = list(prefixes) + middle + list(suffixes)

                self._reclassify_parts(parts)

                # 拒绝不合理组合：要么有非词缀词干，要么有词根，要么前缀后缀都有
                has_prefix = any(p.type == "prefix" for p in parts)
                has_suffix = any(p.type == "suffix" for p in parts)
                has_root = any(p.type == "root" for p in parts)
                has_real_stem = any(p.type == "stem" and p.text not in self._known_set for p in parts)
                if not (has_root or has_real_stem or (has_prefix and has_suffix)):
                    continue

                candidates.append(self._build_result(parts, word))

        if not candidates:
            return self._build_result([MorphPart("stem", word)], word)

        candidates.sort(key=lambda x: -x["score"])
        return candidates[0]

    def analyze(self, word: str, is_valid_word=None) -> dict:
        """
        分析单词的词根词缀

        返回:
            {
                "word": 原词,
                "primary": {最佳拆分结果},
                "all_strategies": [{拆分结果}]
            }
        """
        word = word.strip().lower()
        if not word:
            return None

        primary = self._split(word)
        primary["scheme"] = "A"

        return {
            "word": word,
            "primary": primary,
            "all_strategies": [primary]
        }


# 全局单例
_loader: Optional[MorphemesLoader] = None


def get_morphemes_loader() -> MorphemesLoader:
    """获取全局 MorphemesLoader 实例（延迟加载）"""
    global _loader
    if _loader is None:
        _loader = MorphemesLoader()
    return _loader


if __name__ == "__main__":
    loader = MorphemesLoader()
    
    test_words = [
        "childishness",
        "helpfulness",
        "carelessness",
        "antidisestablishment",
        "reliability",
        "preliminary",
        "cuteness",
        "unhappiness",
        "indonesia",
        "application",
        "biology",
        "cat",
        "previously",
        "impossible",
        "acceptable",
        "education",
        "dialogue",
        "complicated",
    ]
    
    print("=" * 60)
    print("MorphemesLoader 测试")
    print("=" * 60)
    
    for word in test_words:
        result = loader.analyze(word)
        if result:
            primary = result["primary"]
            print(f"\n单词: {word}")
            print(f"  拆分: {primary['result']} (得分: {primary['score']:.1f})")
            for p in primary['parts']:
                print(f"    -> {p}")
