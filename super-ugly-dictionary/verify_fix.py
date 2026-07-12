import json

with open('../数据资料/tiny_dict_fixed.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 找出修复后的单词
test_words = ['do', 'one', 'hello', 'communicate', 'internet', 'yeah', 'order', 'pm', 'ok']

for word in data['words']:
    if word['word'] in test_words:
        print(f"{word['word']}: {word['definition']} (freq={word['frequency']})")