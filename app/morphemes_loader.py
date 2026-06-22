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
        
        for key, value in morphemes.items():
            meaning = value.get("meaning", [])
            for form in value.get("forms", []):
                loc = form.get("loc", "")
                root = form.get("root", "")
                match_str = root.strip("-")
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
        
        self._loaded = True
        print(f"[MorphemesLoader] 加载完成: {len(prefixes)} 前缀, {len(suffixes)} 后缀, {len(roots)} 词根")
    
    def _find_prefix(self, text: str) -> Optional[MorphPart]:
        """在文本开头查找匹配的前缀 - 返回最长匹配"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.prefixes:
            if len(match_str) >= 2 and text.startswith(match_str):
                if len(match_str) > best_len:
                    best_len = len(match_str)
                    best_match = MorphPart("prefix", match_str, key, meaning)
        return best_match
    
    def _find_suffix(self, text: str) -> Optional[MorphPart]:
        """在文本末尾查找匹配的后缀 - 返回最长匹配"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.suffixes:
            if len(match_str) >= 2 and text.endswith(match_str):
                if len(match_str) > best_len:
                    best_len = len(match_str)
                    best_match = MorphPart("suffix", match_str, key, meaning)
        return best_match
    
    def _find_root(self, text: str) -> Optional[MorphPart]:
        """在文本中间查找匹配的词根 - 返回最长匹配"""
        best_match = None
        best_len = 0
        for match_str, root, key, meaning in self.roots:
            if len(match_str) < 3:
                continue
            pos = text.find(match_str)
            if pos != -1:
                # 词根不应占据整个文本
                if pos > 0 or pos + len(match_str) < len(text):
                    if len(match_str) > best_len:
                        best_len = len(match_str)
                        best_match = MorphPart("root", match_str, key, meaning)
        return best_match
    
    def _score_parts(self, parts: List[MorphPart]) -> float:
        """
        对拆分方案进行评分
        
        评分规则:
        1. 匹配奖励：根据匹配长度加权，越长得分越高
        2. 碎片惩罚：1个字母的碎片 -1分，2个字母及以上不扣分
        3. 完全未切分惩罚：如果整个单词只有一个 stem 分块，-5分
        4. 分块数量惩罚：超出必要分块数的惩罚
        """
        score = 0.0
        
        # 统计各类型数量
        prefix_count = sum(1 for p in parts if p.type == "prefix")
        suffix_count = sum(1 for p in parts if p.type == "suffix")
        root_count = sum(1 for p in parts if p.type == "root")
        
        # 匹配奖励：基于匹配长度
        # 匹配越长，得分越高（鼓励更完整的词缀识别）
        for p in parts:
            if p.type == "prefix":
                score += 2.0 + len(p.text) * 0.3
            elif p.type == "suffix":
                score += 2.0 + len(p.text) * 0.3
            elif p.type == "root":
                score += 2.0 + len(p.text) * 0.3
        
        # 碎片惩罚
        for p in parts:
            if p.type == "uncovered" and len(p.text) == 1:
                score -= 1.0
        
        # 分块数量惩罚：超出必要分块数的惩罚
        meaningful_count = prefix_count + suffix_count + root_count
        if meaningful_count > 0:
            actual_parts = len(parts)
            # 超出有意义匹配数量的分块会受到惩罚
            excess_parts = max(0, actual_parts - meaningful_count)
            score -= excess_parts * 3.0
        
        # 完全未切分惩罚：只有一个 stem 分块
        if len(parts) == 1 and parts[0].type == "stem":
            score -= 5.0
        
        return score
    
    def _build_result(self, parts: List[MorphPart], word: str) -> dict:
        """构建结果字典"""
        # 按物理位置排序：将每个 part 映射到它在单词中的起始位置，然后排序
        # 这样可以确保显示顺序与实际单词结构一致
        positioned_parts = []
        for p in parts:
            pos = word.find(p.text)
            if pos >= 0:
                positioned_parts.append((pos, p))
        
        # 按位置排序，然后去重（保留第一个出现）
        positioned_parts.sort(key=lambda x: x[0])
        
        seen = set()
        ordered = []
        for pos, p in positioned_parts:
            if p.text not in seen:
                seen.add(p.text)
                ordered.append(p)
        
        # 处理未覆盖的部分（如 uncovered 类型）
        ordered = self._fix_uncovered_parts(word, ordered)
        
        result_str = ".".join(p.text for p in ordered)
        
        return {
            "prefix": ordered[0].text if any(p.type == "prefix" for p in ordered) else "",
            "suffix": ordered[-1].text if any(p.type == "suffix" for p in ordered) else "",
            "stem": ".".join(p.text for p in ordered if p.type in ("stem", "root", "uncovered")),
            "result": result_str,
            "parts": ordered,
            "score": self._score_parts(ordered)
        }
    
    def _fix_uncovered_parts(self, word: str, parts: List[MorphPart]) -> List[MorphPart]:
        """修复未覆盖的部分：保持未覆盖字符在原始位置"""
        if not parts:
            return [MorphPart("stem", word)]
        
        # 计算每个部分在单词中的位置覆盖
        covered = [-1] * len(word)  # -1表示未覆盖
        for idx, p in enumerate(parts):
            pos = word.find(p.text)
            if pos >= 0:
                for i in range(pos, pos + len(p.text)):
                    covered[i] = idx
        
        # 找出未覆盖的片段
        uncovered = []  # list of (start, end)
        start = None
        for i in range(len(word)):
            if covered[i] == -1:
                if start is None:
                    start = i
            else:
                if start is not None:
                    uncovered.append((start, i))
                    start = None
        if start is not None:
            uncovered.append((start, len(word)))
        
        if not uncovered:
            return parts
        
        # 按位置顺序合并 parts 和 uncovered 片段
        result = []
        word_pos = 0
        
        for p in parts:
            pos = word.find(p.text)
            if pos < 0:
                continue
            
            # 添加在这个part之前的未覆盖片段
            for u_start, u_end in uncovered:
                if u_start >= word_pos and u_end <= pos:
                    result.append(MorphPart("uncovered", word[u_start:u_end]))
            
            # 添加这个part
            result.append(p)
            word_pos = pos + len(p.text)
        
        # 添加最后的未覆盖片段
        for u_start, u_end in uncovered:
            if u_start >= word_pos:
                result.append(MorphPart("uncovered", word[u_start:u_end]))
        
        return result
    
    def _split_strategy_a(self, word: str) -> dict:
        """
        策略A: 词根 → 后缀 → 前缀
        1. 先在完整单词中查找词根
        2. 词根前面的部分查找前缀
        3. 词根后面的部分查找后缀
        """
        parts = []
        
        # 查找词根
        root_match = self._find_root(word)
        if root_match:
            root_pos = word.find(root_match.text)
            before_root = word[:root_pos]
            after_root = word[root_pos + len(root_match.text):]
            
            parts.append(root_match)
            
            # 在 before_root 中查找前缀
            if before_root:
                prefix_match = self._find_prefix(before_root)
                if prefix_match:
                    parts.insert(0, prefix_match)
                    stem_text = before_root[len(prefix_match.text):]
                else:
                    stem_text = before_root
            else:
                stem_text = ""
            
            # 在 after_root 中查找后缀
            if after_root:
                suffix_match = self._find_suffix(after_root)
                if suffix_match:
                    parts.append(suffix_match)
                    stem_text += after_root[:-len(suffix_match.text)]
                else:
                    # 不将未匹配的后缀部分追加到 stem 中
                    # stem_text 保持不变，未覆盖的部分会在 _build_result 中处理
                    pass
            
            if stem_text:
                parts.insert(1 if any(p.type == "prefix" for p in parts) else 0,
                            MorphPart("stem", stem_text))
        
        if not parts:
            parts.append(MorphPart("stem", word))
        
        return self._build_result(parts, word)
    
    def _split_strategy_b(self, word: str) -> dict:
        """
        策略B: 后缀 → 词根 → 前缀
        1. 先在完整单词中查找后缀
        2. 剩余部分中查找词根
        3. 最后查找前缀
        """
        parts = []
        remaining = word
        
        # 查找后缀
        suffix_match = self._find_suffix(remaining)
        if suffix_match:
            remaining = remaining[:-len(suffix_match.text)]
            parts.append(suffix_match)
        
        # 查找词根
        root_match = self._find_root(remaining)
        if root_match:
            root_pos = remaining.find(root_match.text)
            before_root = remaining[:root_pos]
            remaining = before_root
            parts.insert(1 if parts else 0, root_match)
        
        # 查找前缀
        if remaining:
            prefix_match = self._find_prefix(remaining)
            if prefix_match:
                parts.insert(0, prefix_match)
                remaining = remaining[len(prefix_match.text):]
        
        # 添加剩余词干
        if remaining:
            parts.insert(1 if parts else 0, MorphPart("stem", remaining))
        
        if not parts:
            parts.append(MorphPart("stem", word))
        
        return self._build_result(parts, word)
    
    def _split_strategy_c(self, word: str) -> dict:
        """
        策略C: 前缀 → 后缀 → 词根
        1. 先在完整单词中查找前缀
        2. 剩余部分中查找后缀
        3. 最后查找词根
        """
        parts = []
        remaining = word
        
        # 查找前缀
        prefix_match = self._find_prefix(remaining)
        if prefix_match:
            remaining = remaining[len(prefix_match.text):]
            parts.append(prefix_match)
        
        # 查找后缀
        suffix_match = self._find_suffix(remaining)
        if suffix_match:
            remaining = remaining[:-len(suffix_match.text)]
            parts.append(suffix_match)
        
        # 查找词根
        root_match = self._find_root(remaining)
        if root_match:
            root_pos = remaining.find(root_match.text)
            before_root = remaining[:root_pos]
            after_root = remaining[root_pos + len(root_match.text):]
            
            parts.insert(1 if parts else 0, root_match)
            
            # 添加词根前面的未匹配部分作为词干（不与 after_root 合并）
            # after_root 交由 _fix_uncovered_parts 处理，避免重复显示
            if before_root:
                parts.insert(1 if len(parts) > 1 else 0, MorphPart("stem", before_root))
        elif remaining:
            # 没有词根匹配，剩余部分作为词干
            parts.insert(1 if parts else 0, MorphPart("stem", remaining))
        
        if not parts:
            parts.append(MorphPart("stem", word))
        
        return self._build_result(parts, word)
    
    def analyze(self, word: str, is_valid_word=None) -> dict:
        """
        分析单词的词根词缀
        
        参数:
            word: 要分析的单词
            is_valid_word: 可选函数，用于验证词干是否为有效单词
        
        返回:
            {
                "word": 原词,
                "primary": {最佳拆分结果},
                "all_strategies": [{去重后的拆分结果列表，每个带"scheme"标签}]
            }
        """
        word = word.strip().lower()
        if not word:
            return None
        
        # 执行三种策略
        result_a = self._split_strategy_a(word)
        result_b = self._split_strategy_b(word)
        result_c = self._split_strategy_c(word)
        
        # 标记策略来源
        result_a["scheme"] = "A"
        result_b["scheme"] = "B"
        result_c["scheme"] = "C"
        
        # 排序：得分高的排前；得分相同时，A > B > C
        scheme_order = {"A": 0, "B": 1, "C": 2}
        all_results = [result_a, result_b, result_c]
        all_results.sort(key=lambda x: (-x["score"], scheme_order.get(x.get("scheme", "Z"), 99)))
        
        # 去重：如果两个策略的拆分结果字符串相同，只保留第一个（优先级更高的）
        seen_results = set()
        deduped = []
        for r in all_results:
            if r["result"] not in seen_results:
                seen_results.add(r["result"])
                deduped.append(r)
        
        primary = deduped[0] if deduped else result_a
        
        return {
            "word": word,
            "primary": primary,
            "all_strategies": deduped
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
        "application",
        "preliminary",
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
            all_strategies = result["all_strategies"]
            print(f"\n单词: {word}")
            print(f"  主要: {primary['result']} (得分: {primary['score']:.1f})")
            for p in primary['parts']:
                print(f"    -> {p}")
            for s in all_strategies:
                print(f"  方案{s['scheme']}: {s['result']} (得分: {s['score']:.1f})")
