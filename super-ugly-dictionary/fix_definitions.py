"""
步骤6：修复 definition 为 null 的单词
"""

import json
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiny_dict_parser import extract_definition, extract_definition_fallback
from tiny_dict_lookup import TinyDictLookup


def fix_null_definitions(input_path, output_path=None, limit=None):
    """
    修复 definition 为 null 的单词
    
    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出 JSON 文件路径
        limit: 限制处理的单词数量
    """
    print(f"读取 {input_path}...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words = data["words"]
    
    # 找出 definition 为 null 的单词
    null_words = [w for w in words if w["definition"] is None]
    
    print(f"总共 {len(null_words)} 个单词的 definition 为 null")
    
    if limit:
        null_words = null_words[:limit]
        print(f"限制处理 {limit} 个单词")
    
    # 初始化词典查询器
    lookup = TinyDictLookup()
    
    fixed_count = 0
    failed_count = 0
    
    for i, word_entry in enumerate(null_words):
        word = word_entry["word"]
        
        # 查询词典
        html = lookup.lookup(word)
        
        if html:
            # 先尝试从 coca2 提取
            definition = extract_definition(html)
            
            # 如果为 None，再从 dcn 提取
            if definition is None:
                definition = extract_definition_fallback(html)
            
            if definition:
                # 更新 definition
                word_entry["definition"] = definition
                fixed_count += 1
            else:
                failed_count += 1
        else:
            failed_count += 1
        
        # 打印进度
        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1} 个单词... (修复: {fixed_count}, 失败: {failed_count})")
    
    lookup.close()
    
    print(f"\n修复完成!")
    print(f"  成功修复: {fixed_count}")
    print(f"  无法修复: {failed_count}")
    
    # 统计修复后的 null 数量
    remaining_null = sum(1 for w in words if w["definition"] is None)
    print(f"  剩余 null: {remaining_null}")
    
    # 保存到文件
    if output_path:
        print(f"保存到 {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("完成!")
    
    return data


if __name__ == "__main__":
    # 处理全部 9378 个单词
    input_path = os.path.join("..", "数据资料", "tiny_dict.json")
    output_path = os.path.join("..", "数据资料", "tiny_dict.json")  # 直接覆盖原文件
    
    fix_null_definitions(input_path, output_path, limit=None)