import json
import os

# 读取
with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 找出 definition 为 null 的单词
null_words = {w['word']: w['definition'] for w in data['words'] if w['definition'] is None}

print(f'共 {len(null_words)} 个单词无法修复')

# 保存到新文件
output_path = '../数据资料/tiny_dict_null.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(null_words, f, ensure_ascii=False, indent=2)

print(f'已保存到 {output_path}')
print(f'文件大小: {os.path.getsize(output_path)} bytes')