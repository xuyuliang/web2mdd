#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 tiny_dict.json 转换为扁平化的 dict 结构
- 原始词条保留
- inflections 展开为独立词条，沿用 definition 和 frequency
- 完全去重，只保留第一次出现的数据
- 使用 dict 结构实现 O(1) 查询
"""

import json
import sys

def convert_to_flat_dict(input_path, output_path):
    print(f'读取源文件: {input_path}')
    sys.stdout.flush()
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_words = data.get('words', [])
    print(f'原始词条数量: {len(original_words)}')
    sys.stdout.flush()
    
    # 创建扁平化的 dict，完全去重
    flat_words = {}
    
    for entry in original_words:
        word = entry.get('word')
        definition = entry.get('definition')
        frequency = entry.get('frequency')
        inflections = entry.get('inflections', [])
        
        if not word or not definition:
            continue
        
        # 添加原始词条（如果已存在则跳过）
        if word not in flat_words:
            flat_words[word] = {
                "word": word,
                "definition": definition,
                "frequency": frequency
            }
        
        # 添加变形词条（如果已存在则跳过）
        for inflection in inflections:
            if inflection and inflection not in flat_words:
                flat_words[inflection] = {
                    "word": inflection,
                    "definition": definition,
                    "frequency": frequency
                }
    
    print(f'扁平化后词条数量: {len(flat_words)}')
    sys.stdout.flush()
    
    # 构建新数据结构
    new_data = {
        "dict_name": data.get('dict_name', '超级简陋小词典'),
        "version": data.get('version', '1.0'),
        "word_count": len(flat_words),
        "words": flat_words
    }
    
    print(f'写入目标文件: {output_path}')
    sys.stdout.flush()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    print('转换完成！')
    sys.stdout.flush()

if __name__ == '__main__':
    convert_to_flat_dict(
        '../数据资料/tiny_dict.json',
        '../数据资料/tiny_dict_flat.json'
    )