#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找出空字符串定义"""

import json

with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for w in data['words']:
    if w.get('definition') == '':
        print(f"词条: '{w['word']}' -> definition 是空字符串")