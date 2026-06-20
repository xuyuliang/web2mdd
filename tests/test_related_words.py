"""
测试相似词搜索和打分功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.related_words import RelatedWordsSearcher


def main():
    # 获取项目路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "数据资料")
    coca_path = os.path.join(data_dir, "COCA60000.txt")
    
    print("=" * 50)
    print("测试相似词搜索和打分功能")
    print("=" * 50)
    
    # 创建搜索器
    print("\n正在初始化搜索器...")
    searcher = RelatedWordsSearcher(coca_path, data_dir)
    print("[OK] 搜索器初始化完成")
    
    # 测试用例
    test_stems = ["situ", "test", "plan", "develop"]
    
    for stem in test_stems:
        print(f"\n{'-' * 40}")
        print(f"测试词干: {stem}")
        print(f"{'-' * 40}")
        
        results = searcher.search_and_score(stem, max_results=10)
        
        if not results:
            print("  没有找到相似词")
            continue
        
        for i, r in enumerate(results, 1):
            rank_str = f"#{r['rank']}" if r['rank'] else "N/A"
            print(f"  {i:2d}. {r['word']:20s}  分数: {r['score']:2d}  词频: {rank_str}")
    
    print(f"\n{'=' * 50}")
    print("测试完成!")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()