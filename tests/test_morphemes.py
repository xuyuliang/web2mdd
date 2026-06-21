"""
morphemes.json 测试文件

展示如何加载和解析 morphemes.json，以及如何拆分英文单词为词素形式。
包含两种拆分策略的对比测试。
"""

import json
import os
from typing import Dict, List, Tuple, Optional


# ==================== 数据加载 ====================

def load_morphemes(filepath: str = None) -> Dict:
    """加载 morphemes.json 文件"""
    if filepath is None:
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "数据资料", "morphemes.json"
        )
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_matching_units(morphemes: Dict) -> Tuple[List, List, List]:
    """
    从 morphemes 数据中提取所有可用于匹配的单元。
    
    返回三个列表：前缀、后缀、词根（embedded）
    每个单元格式: (匹配字符串, 原始root, 词条键名, 含义)
    """
    prefixes = []
    suffixes = []
    roots = []
    
    for key, value in morphemes.items():
        meaning = value.get("meaning", [])
        for form in value.get("forms", []):
            loc = form.get("loc", "")
            root = form.get("root", "")
            # 去掉首尾连字符得到实际匹配字符串
            match_str = root.strip("-")
            if match_str and loc == "prefix":
                prefixes.append((match_str, root, key, meaning))
            elif match_str and loc == "suffix":
                suffixes.append((match_str, root, key, meaning))
            elif match_str and loc == "embedded":
                roots.append((match_str, root, key, meaning))
    
    # 按长度降序排列，确保最长匹配优先
    prefixes.sort(key=lambda x: len(x[0]), reverse=True)
    suffixes.sort(key=lambda x: len(x[0]), reverse=True)
    roots.sort(key=lambda x: len(x[0]), reverse=True)
    
    return prefixes, suffixes, roots


# ==================== 拆分策略 ====================

class MatchPart:
    """匹配部分的数据结构"""
    def __init__(self, part_type: str, text: str, key: str, meaning: List):
        self.type = part_type  # "prefix", "suffix", "root", "stem"
        self.text = text
        self.key = key
        self.meaning = meaning
    
    def __repr__(self):
        return f"[{self.type}] '{self.text}' <- {self.key}"


def _find_prefix(text: str, prefixes: List) -> Optional[MatchPart]:
    """在文本开头查找匹配的前缀"""
    for match_str, root, key, meaning in prefixes:
        if len(match_str) >= 2 and text.startswith(match_str):
            return MatchPart("prefix", match_str, key, meaning)
    return None


def _find_suffix(text: str, suffixes: List) -> Optional[MatchPart]:
    """在文本末尾查找匹配的后缀"""
    for match_str, root, key, meaning in suffixes:
        if len(match_str) >= 2 and text.endswith(match_str):
            return MatchPart("suffix", match_str, key, meaning)
    return None


def _find_root(text: str, roots: List) -> Optional[MatchPart]:
    """在文本中间查找匹配的词根"""
    for match_str, root, key, meaning in roots:
        if len(match_str) < 3:
            continue
        pos = text.find(match_str)
        if pos != -1:
            # 词根不应占据整个文本
            if pos > 0 or pos + len(match_str) < len(text):
                return MatchPart("root", match_str, key, meaning)
    return None


def split_strategy_root_first(word: str, prefixes: List, suffixes: List, roots: List) -> Tuple[str, List[MatchPart]]:
    """
    策略A: 词根 → 后缀 → 前缀
    
    1. 先在完整单词中查找词根
    2. 词根前面的部分查找前缀
    3. 词根后面的部分查找后缀
    """
    parts = []
    
    # 步骤1: 查找词根
    root_match = _find_root(word, roots)
    if root_match:
        before_root = word[:root_match.text.__len__()]  # 错误，需要修正
        # 重新计算
        root_pos = word.find(root_match.text)
        before_root = word[:root_pos]
        after_root = word[root_pos + len(root_match.text):]
        
        parts.append(root_match)
        
        # 步骤2: 在 before_root 中查找前缀
        if before_root:
            prefix_match = _find_prefix(before_root, prefixes)
            if prefix_match:
                parts.insert(0, prefix_match)
                stem_text = before_root[len(prefix_match.text):]
            else:
                stem_text = before_root
        else:
            stem_text = ""
        
        # 步骤3: 在 after_root 中查找后缀
        if after_root:
            suffix_match = _find_suffix(after_root, suffixes)
            if suffix_match:
                parts.append(suffix_match)
                stem_text += after_root[:len(after_root) - len(suffix_match.text)]
            else:
                stem_text += after_root
        
        # 添加词干
        if stem_text:
            parts.insert(1 if len([p for p in parts if p.type == "prefix"]) else 0, 
                        MatchPart("stem", stem_text, None, []))
    
    if not parts:
        # 没有找到任何匹配，整个单词作为词干
        parts.append(MatchPart("stem", word, None, []))
    
    # 重新排序 parts
    final_parts = []
    prefix_p = [p for p in parts if p.type == "prefix"]
    root_p = [p for p in parts if p.type == "root"]
    stem_p = [p for p in parts if p.type == "stem"]
    suffix_p = [p for p in parts if p.type == "suffix"]
    
    if prefix_p:
        final_parts.append(prefix_p[0])
    if stem_p:
        final_parts.append(stem_p[0])
    if root_p:
        final_parts.append(root_p[0])
    if suffix_p:
        final_parts.append(suffix_p[0])
    
    # 去重并保持顺序
    seen = set()
    ordered = []
    for p in parts:
        if p.text not in seen:
            seen.add(p.text)
            ordered.append(p)
    
    result = ".".join(p.text for p in ordered)
    return result, ordered


def split_strategy_suffix_first(word: str, prefixes: List, suffixes: List, roots: List) -> Tuple[str, List[MatchPart]]:
    """
    策略B: 后缀 → 词根 → 前缀
    
    1. 先在完整单词中查找后缀
    2. 剩余部分中查找词根
    3. 最后查找前缀
    """
    parts = []
    remaining = word
    
    # 步骤1: 查找后缀
    suffix_match = _find_suffix(remaining, suffixes)
    if suffix_match:
        remaining = remaining[:-len(suffix_match.text)]
        parts.append(suffix_match)
    
    # 步骤2: 查找词根
    root_match = _find_root(remaining, roots)
    if root_match:
        root_pos = remaining.find(root_match.text)
        before_root = remaining[:root_pos]
        remaining = before_root
        parts.insert(-1 if parts else 0, root_match)
    
    # 步骤3: 查找前缀
    if remaining:
        prefix_match = _find_prefix(remaining, prefixes)
        if prefix_match:
            parts.insert(0, prefix_match)
            remaining = remaining[len(prefix_match.text):]
    
    # 添加剩余词干
    if remaining:
        parts.insert(1 if parts else 0, MatchPart("stem", remaining, None, []))
    
    if not parts:
        parts.append(MatchPart("stem", word, None, []))
    
    result = ".".join(p.text for p in parts)
    return result, parts


# ==================== 评分机制 ====================

def score_split(word: str, parts: List[MatchPart]) -> float:
    """
    对拆分方案进行评分。
    
    评分规则:
    - 每个前缀匹配: +1分
    - 每个后缀匹配: +1分  
    - 每个词根匹配: +2分（词根更难匹配，权重更高）
    - 词干越短越好: 每少1个字符 +0.1分
    - 匹配的总部分越多越好
    
    返回分数，越高越好
    """
    score = 0.0
    
    for p in parts:
        if p.type == "prefix":
            score += 1.0
        elif p.type == "suffix":
            score += 1.0
        elif p.type == "root":
            score += 2.0
        elif p.type == "stem":
            # 词干越长，扣分越多
            score -= len(p.text) * 0.1
    
    return score


# ==================== 测试展示 ====================

def main():
    print("=" * 60)
    print("morphemes.json 测试 - 拆分策略对比")
    print("=" * 60)
    
    # 1. 加载数据
    print("\n【1】加载 morphemes.json...")
    morphemes = load_morphemes()
    print(f"    共加载 {len(morphemes)} 个词条")
    
    # 2. 提取匹配单元
    print("\n【2】提取前缀、后缀、词根...")
    prefixes, suffixes, roots = extract_matching_units(morphemes)
    print(f"    前缀单元: {len(prefixes)} 个")
    print(f"    后缀单元: {len(suffixes)} 个")
    print(f"    词根单元: {len(roots)} 个")
    
    # 3. 展示部分单元
    print("\n【3】部分前缀示例:")
    for match_str, root, key, meaning in prefixes[:10]:
        print(f"    {match_str:20s} <- {key:30s} 含义: {meaning}")
    
    print("\n【4】部分后缀示例:")
    for match_str, root, key, meaning in suffixes[:10]:
        print(f"    {match_str:20s} <- {key:30s} 含义: {meaning}")
    
    print("\n【5】部分词根示例:")
    for match_str, root, key, meaning in roots[:10]:
        print(f"    {match_str:20s} <- {key:30s} 含义: {meaning}")
    
    # 4. 单词拆分测试 - 策略对比
    print("\n【6】单词拆分策略对比:")
    print("    策略A: 词根 → 后缀 → 前缀")
    print("    策略B: 后缀 → 词根 → 前缀")
    
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
    
    for word in test_words:
        result_a, parts_a = split_strategy_root_first(word, prefixes, suffixes, roots)
        score_a = score_split(word, parts_a)
        
        result_b, parts_b = split_strategy_suffix_first(word, prefixes, suffixes, roots)
        score_b = score_split(word, parts_b)
        
        winner = "A" if score_a > score_b else ("B" if score_b > score_a else "平局")
        
        print(f"\n    单词: {word}")
        print(f"    策略A: {result_a} (得分: {score_a:.1f})")
        for p in parts_a:
            print(f"      -> {p}")
        print(f"    策略B: {result_b} (得分: {score_b:.1f})")
        for p in parts_b:
            print(f"      -> {p}")
        print(f"    >>> 获胜策略: {winner}")
    
    # 5. 展示特定词素的详细信息
    print("\n【7】特定词素详情:")
    for key in ["pre-", "ap-, apo-", "-able", "-ation", "plic-", "log-, -logy"]:
        if key in morphemes:
            info = morphemes[key]
            print(f"\n    词条: {key}")
            print(f"    含义: {info.get('meaning', [])}")
            print(f"    词源: {info.get('origin', '')}")
            print(f"    形式:")
            for form in info.get("forms", []):
                print(f"      loc={form.get('loc', '')}, root={form.get('root', '')}")


if __name__ == "__main__":
    main()