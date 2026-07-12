import json

# 读取当前数据和原始null列表
with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('../数据资料/tiny_dict_null.json', 'r', encoding='utf-8') as f:
    null_words = json.load(f)

# 把所有null单词重新设为null
for word in null_words.keys():
    for entry in data['words']:
        if entry['word'] == word:
            entry['definition'] = None
            break

# 保存
with open('../数据资料/tiny_dict.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('已恢复')

# 统计
null_count = sum(1 for w in data['words'] if w['definition'] is None)
print(f'剩余 null: {null_count}')