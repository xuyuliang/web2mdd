"""
步骤6：把 JSON 文件转换成 dict 结构
便于用户根据单词或者单词的 inflection 检索到释义和词频
"""

import json
import os


def convert_json_to_dict(input_path, output_path=None, limit=None):
    """
    把数组结构的 JSON 转换成 dict 结构
    
    当前结构（数组）：
    {
      "words": [
        {"word": "the", "frequency": 1, "definition": "这", "inflections": []},
        ...
      ]
    }
    
    优化后结构（字典）：
    {
      "dict_name": "超级简陋小词典",
      "version": "1.0",
      "word_count": 60022,
      "words": {
        "the": {"frequency": 1, "definition": "这", "inflections": []},
        ...
      }
    }
    
    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出 JSON 文件路径
        limit: 限制处理的单词数量，None 表示全部
    """
    print(f"读取 {input_path}...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words_array = data["words"]
    
    if limit:
        words_array = words_array[:limit]
    
    print(f"处理 {len(words_array)} 个单词...")
    
    # 转换为 dict
    words_dict = {}
    
    for entry in words_array:
        word = entry["word"]
        
        # 存储主词条（只需要 frequency 和 definition）
        words_dict[word] = {
            "frequency": entry["frequency"],
            "definition": entry["definition"],
        }
        
        # 同时为每个变形词创建引用
        for inflection in entry["inflections"]:
            if inflection not in words_dict:
                words_dict[inflection] = {
                    "frequency": entry["frequency"],
                    "definition": entry["definition"],
                }
    
    # 构建新数据结构
    result = {
        "dict_name": data.get("dict_name", "超级简陋小词典"),
        "version": data.get("version", "1.0"),
        "word_count": len(words_dict),
        "words": words_dict,
    }
    
    # 保存到文件
    if output_path:
        print(f"保存到 {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("完成!")
    
    return result


def test_lookup():
    """测试查询功能"""
    # 先用100条测试
    input_path = os.path.join("..", "数据资料", "tiny_dict_test.json")
    output_path = os.path.join("..", "数据资料", "tiny_dict_test_dict.json")
    
    if not os.path.exists(input_path):
        print(f"测试文件不存在: {input_path}")
        return
    
    result = convert_json_to_dict(input_path, output_path, limit=None)
    
    # 测试查询
    print("\n=== 测试查询 ===")
    
    test_words = ["the", "be", "and", "apple", "apples", "storm", "stormed"]
    
    for word in test_words:
        if word in result["words"]:
            entry = result["words"][word]
            
            print(f"\n单词: {word}")
            print(f"  释义: {entry['definition']}")
            print(f"  词频: {entry['frequency']}")
        else:
            print(f"\n单词: {word} - 未找到")


if __name__ == "__main__":
    test_lookup()