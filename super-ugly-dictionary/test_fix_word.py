from tiny_dict_lookup import lookup_word
from tiny_dict_parser import extract_definition, extract_definition_fallback

# 测试几个单词
test_words = ['communicate', 'internet', 'hello', 'do', 'one']

for word in test_words:
    print(f'\n=== 单词: {word} ===')
    html = lookup_word(word)
    
    if html:
        # 先尝试从 coca2 提取
        definition = extract_definition(html)
        print(f'从 coca2 提取: {definition}')
        
        # 如果为 None，再从 dcn 提取
        if definition is None:
            definition = extract_definition_fallback(html)
            print(f'从 dcn 提取: {definition}')
    else:
        print('未找到 HTML')