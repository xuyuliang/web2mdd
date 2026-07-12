import json

with open('../数据资料/tiny_dict_test_dict.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"总词条数: {data['word_count']}")

# 测试前100词中的单词
test_words = ['the', 'be', 'and', 'of', 'a', 'in', 'to', 'have', 'it', 'i']

for word in test_words:
    if word in data['words']:
        entry = data['words'][word]
        is_inf = entry.get('_is_inflection', False)
        original = entry.get('_original_word', '')
        mark = f" (变形自 {original})" if is_inf else ""
        print(f'{word}: 释义={entry["definition"]}, 词频={entry["frequency"]}{mark}')
    else:
        print(f'{word}: 未找到')