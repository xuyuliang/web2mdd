#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 JSON 文件格式"""

import json
import sys

try:
    with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print('JSON 格式合法！')
    print('顶层键:', list(data.keys()))
    print('词条数量:', len(data.get('words', [])))
    sys.stdout.flush()
    
    # 检查是否有 None 或空字符串的 definition
    null_count = 0
    empty_count = 0
    null_words = []
    for w in data['words']:
        if w.get('definition') is None:
            null_count += 1
            null_words.append(w['word'])
        elif w.get('definition') == '':
            empty_count += 1
    
    print('None 定义数量:', null_count)
    print('空字符串定义数量:', empty_count)
    if null_words:
        print('None 词条:', null_words[:10])
    
except json.JSONDecodeError as e:
    print('JSON 格式错误:', e)
except Exception as e:
    print('其他错误:', e)