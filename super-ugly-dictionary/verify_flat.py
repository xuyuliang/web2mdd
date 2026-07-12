#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证扁平化后的 JSON"""

import json

with open('../数据资料/tiny_dict_flat.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('顶层键:', list(data.keys()))
print('词条数量:', data.get('word_count'))

# 验证几个词条
words = data.get('words', {})
print()
print('be:', words.get('be'))
print('was:', words.get('was'))
print('been:', words.get('been'))
print('the:', words.get('the'))