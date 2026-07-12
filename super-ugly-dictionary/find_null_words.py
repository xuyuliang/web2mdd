import json

with open('../数据资料/tiny_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 找出 definition 为 null 的单词
null_words = [w for w in data['words'] if w['definition'] is None]

print(f'总共 {len(null_words)} 个单词的 definition 为 null')
print(f'前20个:')
for w in null_words[:20]:
    print(f'  {w["word"]}: frequency={w["frequency"]}')