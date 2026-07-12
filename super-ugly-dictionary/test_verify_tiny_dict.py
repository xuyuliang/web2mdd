"""
超级简陋小词典 - 步骤5：抽查验证

从60000个词中随机抽取20个词，验证JSON文件中的数据
"""

import json
import random
import os

# JSON 文件路径
JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "数据资料",
    "tiny_dict.json"
)


def load_tiny_dict():
    """加载小词典"""
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_random_words(count=20):
    """随机抽查验证"""
    data = load_tiny_dict()
    words = data["words"]
    
    print(f"总单词数: {len(words)}")
    print(f"随机抽取 {count} 个词进行验证:\n")
    
    # 设置随机种子以便复现
    random.seed(42)
    
    # 随机抽取索引
    indices = random.sample(range(len(words)), count)
    
    for i, idx in enumerate(indices):
        entry = words[idx]
        print(f"{i+1}. 单词: {entry['word']}")
        print(f"   词频: {entry['frequency']}")
        print(f"   释义: {entry['definition']}")
        print(f"   变形: {entry['inflections']}")
        print()


def verify_specific_words():
    """验证特定单词"""
    data = load_tiny_dict()
    words = data["words"]
    
    # 构建单词到索引的映射
    word_to_entry = {w["word"]: w for w in words}
    
    # 测试一些常见单词
    test_words = ["apple", "storm", "keyboard", "run", "walk", "book", "computer"]
    
    print("验证特定单词:\n")
    
    for word in test_words:
        if word in word_to_entry:
            entry = word_to_entry[word]
            print(f"✓ {word}: 释义={entry['definition']}, 词频={entry['frequency']}, 变形={entry['inflections']}")
        else:
            print(f"✗ {word}: 未找到")


def verify_data_quality():
    """验证数据质量"""
    data = load_tiny_dict()
    words = data["words"]
    
    print("数据质量统计:\n")
    
    # 统计有释义的单词数量
    with_definition = sum(1 for w in words if w["definition"])
    print(f"有释义的单词: {with_definition}/{len(words)} ({100*with_definition/len(words):.1f}%)")
    
    # 统计有变形的单词数量
    with_inflections = sum(1 for w in words if w["inflections"])
    print(f"有变形的单词: {with_inflections}/{len(words)} ({100*with_inflections/len(words):.1f}%)")
    
    # 统计变形总数
    total_inflections = sum(len(w["inflections"]) for w in words)
    print(f"变形总数: {total_inflections}")
    
    # 词频统计
    frequencies = [w["frequency"] for w in words]
    print(f"词频范围: {min(frequencies)} - {max(frequencies)}")


if __name__ == "__main__":
    print("=" * 50)
    print("步骤5：抽查验证")
    print("=" * 50)
    
    # 随机抽查
    verify_random_words(20)
    
    print("\n" + "=" * 50)
    
    # 验证特定单词
    verify_specific_words()
    
    print("\n" + "=" * 50)
    
    # 数据质量统计
    verify_data_quality()