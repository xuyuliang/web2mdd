#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试测试脚本"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiny_dict_lookup import lookup_word
from tiny_dict_parser import extract_definition

# 查询
html = lookup_word('apple')
print('HTML found:', html is not None)

# 解析
result = extract_definition(html)
print('Definition:', result)

# 打印HTML的一部分
if html:
    # 搜索coca相关
    import re
    # 搜索所有包含coca的部分
    import re
    matches = re.findall(r'<div[^>]*coca[^>]*>[^<]+', html)
    for m in matches[:5]:
        print('Match:', m)
    
    # 测试解析器的正则
    pattern = r'<div class="coca2">([^<]+)</div>'
    match = re.search(pattern, html)
    print('Pattern match:', match)
    if match:
        print('Group 1:', match.group(1))