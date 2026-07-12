#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并 deepseek 填充的数据到主字典"""

import json
import sys

def main():
    # 读取用户填充的数据
    with open('../数据资料/deepseek_json_20260712_c0de63.json', 'r', encoding='utf-8') as f:
        filled = json.load(f)

    print(f'填充数据条目数: {len(filled)}')
    sys.stdout.flush()

    # 读取主字典
    with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data['words']
    print(f'主字典词条数: {len(words)}')
    sys.stdout.flush()

    # 查找并更新匹配的词条
    updated = 0
    not_found = []

    # 创建单词到索引的映射以加快查找
    word_to_idx = {w['word']: i for i, w in enumerate(words)}

    for word, definition in filled.items():
        if word == 'mark':
            continue  # 跳过标记字段
        if word in word_to_idx:
            idx = word_to_idx[word]
            words[idx]['definition'] = definition
            updated += 1
        else:
            not_found.append(word)

    print(f'更新词条数: {updated}')
    if not_found:
        print(f'未找到词条: {not_found}')
    sys.stdout.flush()

    # 保存结果
    with open('../数据资料/tiny_dict.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('合并完成！')
    sys.stdout.flush()

if __name__ == '__main__':
    main()