"""
超级简陋小词典 - 数据提取模块

从 oldCOCA60000.txt 读取单词，查询词典，提取数据
"""

import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiny_dict_parser import extract_definition, extract_verb_forms, extract_noun_forms
from tiny_dict_lookup import lookup_word


# COCA 词频文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COCA_FILE = os.path.join(BASE_DIR, "数据资料", "oldCOCA60000.txt")


def read_coca_words(limit: int = None) -> list[str]:
    """
    读取 COCA 词频表
    
    Args:
        limit: 限制读取的单词数量，None 表示全部
        
    Returns:
        单词列表
    """
    words = []
    
    with open(COCA_FILE, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            word = line.strip()
            if word:
                words.append(word)
    
    return words


def build_dict_entry(word: str, frequency: int, html: str | None) -> dict:
    """
    构建词典条目
    
    Args:
        word: 单词
        frequency: 词频（行号）
        html: 词典返回的 HTML 内容
        
    Returns:
        词典条目字典
    """
    entry = {
        "word": word,
        "frequency": frequency,
        "definition": None,
        "inflections": [],
    }
    
    if not html:
        return entry
    
    # 提取释义
    definition = extract_definition(html)
    entry["definition"] = definition
    
    # 提取动词变形
    verb_forms = extract_verb_forms(html)
    
    # 提取名词变形
    noun_forms = extract_noun_forms(html)
    
    # 合并所有变形
    all_inflections = verb_forms + noun_forms
    entry["inflections"] = all_inflections
    
    return entry


def process_words(words: list[str], start_index: int = 1) -> list[dict]:
    """
    处理单词列表，提取数据
    
    Args:
        words: 单词列表
        start_index: 起始词频（默认1）
        
    Returns:
        词典条目列表
    """
    results = []
    
    for i, word in enumerate(words):
        frequency = start_index + i
        
        # 查询词典
        html = lookup_word(word)
        
        # 构建条目
        entry = build_dict_entry(word, frequency, html)
        results.append(entry)
        
        # 打印进度
        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1} 个单词...")
    
    return results


def build_tiny_dict(output_path: str = None, limit: int = None):
    """
    构建超级简陋小词典
    
    Args:
        output_path: 输出文件路径
        limit: 限制处理的单词数量，None 表示全部
        
    Returns:
        词典数据
    """
    print("读取 COCA 词表...")
    words = read_coca_words(limit=limit)
    print(f"共 {len(words)} 个单词")
    
    print("开始处理单词...")
    entries = process_words(words)
    
    # 构建最终数据
    data = {
        "dict_name": "超级简陋小词典",
        "version": "1.0",
        "word_count": len(entries),
        "words": entries,
    }
    
    # 保存到文件
    if output_path:
        import json
        print(f"保存到 {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("完成!")
    
    return data


if __name__ == "__main__":
    # 测试：处理前10个单词
    print("=== 测试：处理前10个单词 ===")
    words = read_coca_words(limit=10)
    print(f"单词列表: {words}")
    
    results = process_words(words)
    for entry in results:
        print(f"\n单词: {entry['word']}")
        print(f"  词频: {entry['frequency']}")
        print(f"  释义: {entry['definition']}")
        print(f"  变形: {entry['inflections']}")