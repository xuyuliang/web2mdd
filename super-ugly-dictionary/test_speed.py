#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试查询速度"""

import json
import time

# 加载数据
with open('../数据资料/tiny_dict_flat.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

words = data['words']

# 测试查询速度
test_words = ['the', 'be', 'was', 'hello', 'world', 'dictionary', 'python', 'code']

start = time.time()
for _ in range(10000):
    for w in test_words:
        _ = words.get(w)
end = time.time()

print(f'查询 {len(test_words)} 个词 × 10000 次 = {len(test_words) * 10000} 次查询')
print(f'总耗时: {end - start:.4f} 秒')
print(f'平均每次查询: {(end - start) / (len(test_words) * 10000) * 1000000:.2f} 微秒')