"""
模式搜索性能测试 - 测量各步骤耗时，定位瓶颈
"""
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.word_freq import WordFreq
from app.mdx_sqlite_reader import MDXSQLiteReader


def test_pattern_search_performance():
    """测试模式搜索各阶段的性能"""
    
    # 初始化
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'The little dict', 'TLD.mdx.index.db')
    MDX_PATH = os.path.join(os.path.dirname(__file__), '..', 'The little dict', 'TLD.mdx')
    
    print("=" * 60)
    print("模式搜索性能测试")
    print("=" * 60)
    
    # 1. 测试 COCA 词频搜索
    print("\n[1] 测试 COCA 词频搜索: word_freq.search('*pig*')")
    word_freq = WordFreq(DB_PATH)
    
    t0 = time.time()
    coca_results = word_freq.search('*pig*', max_results=50)
    t1 = time.time()
    
    print(f"    结果数量: {len(coca_results)}")
    print(f"    COCA 搜索耗时: {(t1-t0)*1000:.1f}ms")
    if coca_results:
        print(f"    前5个结果: {coca_results[:5]}")
    
    # 2. 测试 MDX lookup
    print(f"\n[2] 测试 MDX 释义查询 (测试前5个单词)")
    mdx_reader = MDXSQLiteReader(MDX_PATH, DB_PATH)
    
    total_lookup_time = 0
    for i, word in enumerate(coca_results[:5]):
        t0 = time.time()
        result, exact = mdx_reader.lookup(word)
        t1 = time.time()
        total_lookup_time += (t1 - t0)
        print(f"    '{word}': 耗时 {(t1-t0)*1000:.1f}ms, 找到={exact}")
    
    avg_lookup = total_lookup_time / min(5, len(coca_results)) if coca_results else 0
    print(f"    平均每次 lookup: {avg_lookup*1000:.1f}ms")
    print(f"    查询全部 {len(coca_results)} 个单词预估耗时: {(len(coca_results) * avg_lookup)*1000:.1f}ms")
    
    # 3. 测试完整流程（第一页 15 个单词）
    if coca_results:
        print(f"\n[3] 测试完整流程: 查询前 {min(15, len(coca_results))} 个单词的释义")
        page_size = min(15, len(coca_results))
        
        t0 = time.time()
        page_results = []
        for w in coca_results[:page_size]:
            html, _ = mdx_reader.lookup(w)
            if isinstance(html, str) and html:
                page_results.append(w)
        t1 = time.time()
        
        print(f"    成功获取释义: {len(page_results)} 个")
        print(f"    完整流程耗时: {(t1-t0)*1000:.1f}ms")
    
    # 4. 测试一个匹配更多结果的 pattern
    print(f"\n[4] 测试广泛匹配: word_freq.search('*ing*')")
    t0 = time.time()
    ing_results = word_freq.search('*ing*', max_results=50)
    t1 = time.time()
    print(f"    结果数量: {len(ing_results)}")
    print(f"    COCA 搜索耗时: {(t1-t0)*1000:.1f}ms")
    
    # 5. 测试一个匹配较少结果的 pattern
    print(f"\n[5] 测试窄泛匹配: word_freq.search('*qx*')")
    t0 = time.time()
    qx_results = word_freq.search('*qx*', max_results=50)
    t1 = time.time()
    print(f"    结果数量: {len(qx_results)}")
    print(f"    COCA 搜索耗时: {(t1-t0)*1000:.1f}ms")
    
    # 总结
    print("\n" + "=" * 60)
    print("性能分析总结:")
    print("=" * 60)
    print(f"  - COCA 搜索 (50条 LIMIT): {(t1-t0)*1000:.1f}ms")
    print(f"  - 单次 MDX lookup: {avg_lookup*1000:.1f}ms")
    print(f"  - 15 个单词完整查询预估: {(15 * avg_lookup)*1000:.1f}ms")
    print(f"  - 50 个单词完整查询预估: {(50 * avg_lookup)*1000:.1f}ms")


if __name__ == "__main__":
    test_pattern_search_performance()