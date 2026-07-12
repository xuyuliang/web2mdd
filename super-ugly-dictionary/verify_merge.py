#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证合并结果"""

import json

with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

null_count = sum(1 for w in data['words'] if w.get('definition') is None)
print('剩余 null 定义数量:', null_count)

# 显示几个已更新的词条示例
sample_words = ['african-american', 'cheer', 'labor', 'protestant', 'apache', 'x-ray']
for w in data['words']:
    if w['word'] in sample_words:
        print(f"{w['word']}: {w.get('definition')}")