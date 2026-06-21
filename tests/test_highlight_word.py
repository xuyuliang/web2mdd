"""
测试 highlight_word 方法
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.related_words import RelatedWordsSearcher


def main():
    # 初始化搜索器
    coca_path = os.path.join("数据资料", "coca60000.txt")
    data_dir = "数据资料"
    searcher = RelatedWordsSearcher(coca_path, data_dir)

    # 测试 highlight_word
    print("=== 测试 highlight_word ===")
    print()

    test_cases = [
        ("comfor", "comfortable", '<span class="stem-highlight">comfor</span>t.able'),
        ("fort", "comfortable", 'com.<span class="stem-highlight">fort</span>.able'),
        ("comfort", "comfortable", '<span class="stem-highlight">comfort</span>.able'),
        ("situ", "situational", '<span class="stem-highlight">situ</span>ation.al'),
        ("situ", "situated", '<span class="stem-highlight">situ</span>a.t.ed'),
    ]

    all_passed = True
    for stem, word, expected in test_cases:
        result = searcher.highlight_word(stem, word)
        passed = result == expected
        if not passed:
            all_passed = False
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] stem={stem}, word={word}")
        print(f"  结果: {result}")
        if not passed:
            print(f"  期望: {expected}")
        print()

    if all_passed:
        print("所有测试通过!")
    else:
        print("有测试失败!")

    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)