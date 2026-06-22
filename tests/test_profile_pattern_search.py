"""
模式搜索性能分析 - 模拟真实搜索流程，定位瓶颈
"""
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 设置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE_DIR, "The little dict")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
DB_PATH = os.path.join(DICT_DIR, "TLD.mdx.index.db")


def profile_pattern_search():
    """完整模拟模式搜索流程，测量每一步的耗时"""
    
    print("=" * 70)
    print("模式搜索性能分析 - 完整流程")
    print("=" * 70)
    
    overall_start = time.time()
    
    # ========== 步骤 1: 初始化组件 ==========
    print("\n【步骤 1】初始化组件...")
    t0 = time.time()
    
    from app.word_freq import WordFreq
    from app.mdx_sqlite_reader import MDXSQLiteReader
    from app.morphemes_loader import MorphemesLoader
    
    print("  - 加载 WordFreq...")
    word_freq = WordFreq(DB_PATH)
    t1 = time.time()
    print(f"    WordFreq 加载耗时: {(t1-t0)*1000:.1f}ms")
    
    print("  - 加载 MDXSQLiteReader...")
    mdx_reader = MDXSQLiteReader(MDX_PATH, DB_PATH)
    t2 = time.time()
    print(f"    MDXSQLiteReader 加载耗时: {(t2-t1)*1000:.1f}ms")
    
    print("  - 加载 MorphemesLoader...")
    morphemes_loader = MorphemesLoader()
    t3 = time.time()
    print(f"    MorphemesLoader 加载耗时: {(t3-t2)*1000:.1f}ms")
    
    init_total = t3 - overall_start
    print(f"\n  【总计】组件初始化总耗时: {init_total*1000:.1f}ms")
    
    # ========== 步骤 2: 执行模式搜索 ==========
    print("\n" + "=" * 70)
    print("【步骤 2】执行模式搜索: *pig*")
    print("=" * 70)
    
    pattern = "*pig*"
    
    # 2a: COCA 词频搜索
    print("\n  2a. COCA 词频搜索: word_freq.search('{}')".format(pattern))
    t_start = time.time()
    
    coca_results = word_freq.search(pattern, max_results=50)
    t_end = time.time()
    
    print(f"      结果数量: {len(coca_results)}")
    print(f"      耗时: {(t_end - t_start)*1000:.1f}ms")
    if coca_results:
        print(f"      前5个: {coca_results[:5]}")
    
    coca_search_time = t_end - t_start
    
    # 2b: 直接使用 COCA 返回的小写单词（不做大小写映射）
    print("\n  2b. 直接使用 COCA 返回的小写单词（已优化，跳过映射）...")
    t_start = time.time()
    
    # 模拟优化后的 pattern_search_ranked 方法
    ranked_out = coca_results[:50]  # 直接使用 COCA 结果
    
    t_end = time.time()
    map_time = t_end - t_start
    print(f"      结果数量: {len(ranked_out)}")
    print(f"      总耗时: {map_time*1000:.1f}ms (可忽略)")
    if ranked_out:
        print(f"      前5个: {ranked_out[:5]}")
    
    # 2c: 截取第一页
    print("\n  2c. 截取第一页 (10个单词)...")
    t_start = time.time()
    
    page_size = 10
    page_words = ranked_out[:page_size]
    
    t_end = time.time()
    print(f"      第一页单词: {page_words}")
    print(f"      耗时: {(t_end - t_start)*1000:.1f}ms (可忽略)")
    
    # ========== 步骤 3: 查询每个单词的释义 ==========
    print("\n" + "=" * 70)
    print("【步骤 3】查询每个单词的释义 (mdx_reader.lookup)")
    print("=" * 70)
    
    lookup_times = []
    for i, word in enumerate(page_words):
        t_start = time.time()
        html, exact = mdx_reader.lookup(word)
        t_end = time.time()
        
        elapsed = t_end - t_start
        lookup_times.append(elapsed)
        
        status = "✓" if exact else "✗"
        print(f"    [{i+1:2d}] {status} {word:20s} 耗时 {elapsed*1000:6.1f}ms")
    
    total_lookup_time = sum(lookup_times)
    avg_lookup_time = total_lookup_time / len(lookup_times) if lookup_times else 0
    max_lookup_time = max(lookup_times) if lookup_times else 0
    min_lookup_time = min(lookup_times) if lookup_times else 0
    
    print(f"\n    【释义查询统计】")
    print(f"      总耗时: {total_lookup_time*1000:.1f}ms")
    print(f"      平均耗时: {avg_lookup_time*1000:.1f}ms/单词")
    print(f"      最快: {min_lookup_time*1000:.1f}ms")
    print(f"      最慢: {max_lookup_time*1000:.1f}ms")
    
    # ========== 步骤 4: 提取摘要 ==========
    print("\n  4. 提取摘要 (_extract_summary)...")
    t_start = time.time()
    
    for word, html in zip(page_words, [mdx_reader.lookup(w)[0] for w in page_words]):
        if html:
            summary = MDXReader._extract_summary(html)
    
    t_end = time.time()
    print(f"      耗时: {(t_end - t_start)*1000:.1f}ms (可忽略)")
    
    # ========== 步骤 5: 模板渲染 ==========
    print("\n  5. 模板渲染...")
    t_start = time.time()
    
    from jinja2 import Environment, FileSystemLoader
    templates_dir = os.path.join(BASE_DIR, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("partials/_pattern_results.html")
    
    # 模拟渲染数据
    page_results = []
    for word, html in zip(page_words, [mdx_reader.lookup(w)[0] for w in page_words]):
        rank = word_freq.get_rank(word)
        summary = MDXReader._extract_summary(html) if html else ""
        page_results.append({
            "word": word,
            "highlighted_word": word,
            "summary": summary,
            "has_full": bool(html),
            "rank": rank
        })
    
    context = {
        "word": pattern,
        "results": page_results,
        "page": 1,
        "total_pages": max(1, (len(ranked_out) + page_size - 1) // page_size),
        "total_count": len(ranked_out),
        "page_ranked_count": min(page_size, len(ranked_out)),
        "back_word": None,
        "back_page": None,
    }
    
    rendered = template.render(**context)
    t_end = time.time()
    print(f"      渲染耗时: {(t_end - t_start)*1000:.1f}ms")
    print(f"      渲染长度: {len(rendered)} 字符")
    
    # ========== 总计 ==========
    overall_end = time.time()
    total_time = overall_end - overall_start
    
    print("\n" + "=" * 70)
    print("性能分析总结")
    print("=" * 70)
    print(f"""
  组件初始化:        {init_total*1000:8.1f}ms  ({init_total/total_time*100:5.1f}%)
  COCA 词频搜索:      {coca_search_time*1000:8.1f}ms  ({coca_search_time/total_time*100:5.1f}%)
  单词映射:           {map_time*1000:8.1f}ms  ({map_time/total_time*100:5.1f}%)
  释义查询 (10个):    {total_lookup_time*1000:8.1f}ms  ({total_lookup_time/total_time*100:5.1f}%)
  模板渲染:           {sum(lookup_times) * 0:8.1f}ms  (可忽略)
  ─────────────────────────────────
  首次加载总计:       {total_time*1000:8.1f}ms  ({total_time:5.2f}s)
  
  释义查询是主要瓶颈。
  每个单词平均释义查询时间: {avg_lookup_time*1000:.1f}ms
""")
    
    # 找出最耗时的单词
    if lookup_times and page_words:
        max_idx = lookup_times.index(max(lookup_times))
        print(f"  最慢的单词: {page_words[max_idx]} ({max_lookup_time*1000:.1f}ms)")
        
        # 找出耗时超过 100ms 的单词
        slow_words = [(w, t) for w, t in zip(page_words, lookup_times) if t > 0.1]
        if slow_words:
            print(f"\n  耗时 >100ms 的单词:")
            for w, t in slow_words:
                print(f"    {w}: {t*1000:.1f}ms")


# 需要导入 MDXReader 类来使用 _extract_summary
from app.main import MDXReader


if __name__ == "__main__":
    profile_pattern_search()