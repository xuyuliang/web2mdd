import json

# 读取主数据和AI填充的数据
with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('../数据资料/tiny_dict_filled.json', 'r', encoding='utf-8') as f:
    filled = json.load(f)

print(f'AI填充了 {len(filled)} 个单词')

# 合并到主数据
count = 0
for word, definition in filled.items():
    for entry in data['words']:
        if entry['word'] == word:
            entry['definition'] = definition
            count += 1
            break

print(f'已更新 {count} 个单词')

# 保存
with open('../数据资料/tiny_dict.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('已保存到 tiny_dict.json')

# 检查剩余null
null_count = sum(1 for w in data['words'] if w['definition'] is None)
print(f'剩余 null: {null_count}')