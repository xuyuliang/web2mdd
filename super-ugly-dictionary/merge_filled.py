import json

# 读取原始数据和已填补数据
with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('../数据资料/tiny_dict_filled.json', 'r', encoding='utf-8') as f:
    filled = json.load(f)

# 合并
count = 0
for word, definition in filled.items():
    for entry in data['words']:
        if entry['word'] == word:
            entry['definition'] = definition
            count += 1
            break

print(f'已填补 {count} 个单词')

# 保存
with open('../数据资料/tiny_dict.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('已更新 tiny_dict.json')

# 检查剩余null
null_count = sum(1 for w in data['words'] if w['definition'] is None)
print(f'剩余 null: {null_count}')