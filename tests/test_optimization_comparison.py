"""
优化方案性能对比测试 - 比较 4 种不同的查询策略
"""
import time
import sys
import os
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.word_freq import WordFreq
from app.mdx_sqlite_reader import MDXSQLiteReader


class Timer:
    """简单的计时器上下文管理器"""
    def __init__(self, label=""):
        self.label = label
        self.elapsed = 0
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed = time.time() - self.start


# ============================================================
# 方案 1: 当前基准 - 串行逐个查询
# ============================================================
def benchmark_sequential(mdx_reader, words, page_size=10, max_pages=5):
    """
    方案1: 串行逐个查询，分页加载
    每页10条，最多5页(50条)
    """
    results = []
    total_time = Timer("方案1: 串行查询")
    
    with total_time:
        total_words = len(words)
        pages_needed = min(max_pages, (total_words + page_size - 1) // page_size)
        
        for page in range(pages_needed):
            start = page * page_size
            end = min(start + page_size, total_words)
            page_words = words[start:end]
            
            for word in page_words:
                html, _ = mdx_reader.lookup(word)
                if isinstance(html, str) and html:
                    results.append((word, html))
    
    return results, total_time.elapsed


# ============================================================
# 方案 2: 批量合并查询 - 使用 SQL JOIN 一次性获取所有记录
# ============================================================
def benchmark_batch_join(mdx_reader, words, page_size=10, max_pages=5):
    """
    方案2: 批量合并查询
    通过 SQL JOIN 一次性查询所有单词的记录信息，然后批量读取
    """
    results = []
    total_time = Timer("方案2: 批量JOIN")
    
    with total_time:
        total_words = len(words)
        pages_needed = min(max_pages, (total_words + page_size - 1) // page_size)
        
        for page in range(pages_needed):
            start = page * page_size
            end = min(start + page_size, total_words)
            page_words = words[start:end]
            
            if not page_words:
                continue
            
            # 构建批量查询的 SQL
            placeholders = ','.join(['?' for _ in page_words])
            cursor = mdx_reader.conn.cursor()
            
            # 一次性查询所有单词的记录信息
            # 先查精确匹配，再查小写匹配
            lower_placeholders = ','.join(['?' for _ in page_words])
            query = f"""
                SELECT word, record_offset, record_length 
                FROM word_index 
                WHERE word IN ({placeholders}) 
                UNION
                SELECT word, record_offset, record_length 
                FROM word_index 
                WHERE word_lower IN ({lower_placeholders})
            """
            params = page_words + [w.lower() for w in page_words]
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 去重，保留第一个匹配
            seen = set()
            matched_words = []
            for row in rows:
                word = row['word']
                if word not in seen:
                    seen.add(word)
                    matched_words.append(row)
            
            # 批量读取记录
            for row in matched_words:
                html = mdx_reader._read_record_from_file(row['record_offset'], row['record_length'])
                if html:
                    results.append((row['word'], html))
    
    return results, total_time.elapsed


# ============================================================
# 方案 3: 异步并发查询
# ============================================================
def benchmark_async_concurrent(mdx_reader, words, page_size=10, max_pages=5, max_workers=10):
    """
    方案3: 使用线程池并发查询
    每个线程创建独立的 reader 实例来避免 SQLite 线程问题
    """
    results = []
    total_time = Timer("方案3: 异步并发")
    
    # 获取 MDX 和 DB 路径
    mdx_path = mdx_reader.path
    db_path = mdx_reader.db_path
    
    def lookup_single(word):
        """在每个线程中创建独立的 reader 实例"""
        try:
            # 创建新的 SQLite 连接（check_same_thread=False 允许跨线程）
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            row = None
            # 精确匹配
            cursor.execute("SELECT * FROM word_index WHERE word = ?", (word,))
            row = cursor.fetchone()
            
            if not row:
                # 小写匹配
                cursor.execute("SELECT * FROM word_index WHERE word_lower = ?", (word.lower(),))
                row = cursor.fetchone()
            
            conn.close()
            
            if row:
                # 使用原来 reader 的 _read_record_from_file 方法读取记录
                html = mdx_reader._read_record_from_file(row["record_offset"], row["record_length"])
                if isinstance(html, str) and html:
                    return (word, html)
        except Exception as e:
            print(f"  线程查询 {word} 出错: {e}")
        return None
    
    with total_time:
        total_words = len(words)
        pages_needed = min(max_pages, (total_words + page_size - 1) // page_size)
        
        for page in range(pages_needed):
            start = page * page_size
            end = min(start + page_size, total_words)
            page_words = words[start:end]
            
            if not page_words:
                continue
            
            # 使用线程池并发查询
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(lookup_single, w) for w in page_words]
                for future in futures:
                    result = future.result()
                    if result:
                        results.append(result)
    
    return results, total_time.elapsed


# ============================================================
# 方案 4: 分页按需加载
# ============================================================
def benchmark_paginated(mdx_reader, words, page_size=10, max_pages=5):
    """
    方案4: 严格分页，每次只查询一页
    模拟实际使用场景：用户可能只看第一页
    """
    results = []
    total_time = Timer("方案4: 分页加载")
    
    with total_time:
        # 只加载第一页（10条）
        page_words = words[:page_size]
        
        for word in page_words:
            html, _ = mdx_reader.lookup(word)
            if isinstance(html, str) and html:
                results.append((word, html))
    
    return results, total_time.elapsed


# ============================================================
# 额外测试：分页加载多页的累计时间
# ============================================================
def benchmark_paginated_multi_page(mdx_reader, words, page_size=10, max_pages=5):
    """
    测试分页加载多页的累计时间
    """
    results = []
    total_time = Timer("方案4+: 分页多页加载")
    page_times = []
    
    with total_time:
        pages_needed = min(max_pages, (len(words) + page_size - 1) // page_size)
        
        for page in range(pages_needed):
            page_start = time.time()
            start = page * page_size
            end = min(start + page_size, len(words))
            page_words = words[start:end]
            
            for word in page_words:
                html, _ = mdx_reader.lookup(word)
                if isinstance(html, str) and html:
                    results.append((word, html))
            
            page_times.append((time.time() - page_start) * 1000)
    
    return results, total_time.elapsed, page_times


# ============================================================
# 主测试函数
# ============================================================
def run_all_benchmarks():
    """运行所有基准测试"""
    
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'The little dict', 'TLD.mdx.index.db')
    MDX_PATH = os.path.join(os.path.dirname(__file__), '..', 'The little dict', 'TLD.mdx')
    
    print("=" * 70)
    print("优化方案性能对比测试")
    print("=" * 70)
    
    # 初始化
    word_freq = WordFreq(DB_PATH)
    mdx_reader = MDXSQLiteReader(MDX_PATH, DB_PATH)
    
    # 获取测试单词列表
    test_patterns = ['*pig*', '*cat*', '*dog*', '*ing*']
    
    for pattern in test_patterns:
        print(f"\n{'=' * 70}")
        print(f"测试模式: {pattern}")
        print(f"{'=' * 70}")
        
        t0 = time.time()
        words = word_freq.search(pattern, max_results=50)
        t1 = time.time()
        
        print(f"匹配单词数: {len(words)}")
        print(f"搜索耗时: {(t1-t0)*1000:.1f}ms")
        print(f"测试单词: {words[:10]}{'...' if len(words) > 10 else ''}")
        
        if not words:
            print("无匹配单词，跳过测试")
            continue
        
        # 运行所有测试
        benchmarks = [
            ("方案1: 串行查询(分页)", lambda: benchmark_sequential(mdx_reader, words)),
            ("方案2: 批量JOIN", lambda: benchmark_batch_join(mdx_reader, words)),
            ("方案3: 异步并发", lambda: benchmark_async_concurrent(mdx_reader, words)),
            ("方案4: 分页(第1页)", lambda: benchmark_paginated(mdx_reader, words)),
            ("方案4+: 分页多页", lambda: benchmark_paginated_multi_page(mdx_reader, words)),
        ]
        
        results = []
        for name, func in benchmarks:
            t0 = time.time()
            result = func()
            elapsed = time.time() - t0
            
            if name.startswith("方案4+"):
                res_words, total_ms, page_times = result
                print(f"\n  {name}:")
                print(f"    获取单词数: {len(res_words)}")
                print(f"    总耗时: {total_ms:.1f}ms")
                for i, pt in enumerate(page_times):
                    print(f"    第{i+1}页: {pt:.1f}ms")
            else:
                res_words, total_ms = result
                print(f"\n  {name}:")
                print(f"    获取单词数: {len(res_words)}")
                print(f"    耗时: {total_ms:.1f}ms")
            
            results.append((name, res_words, total_ms))
        
        # 打印对比表格
        print(f"\n{'=' * 70}")
        print(f"性能对比汇总 (模式: {pattern}, 结果数: {len(words)})")
        print(f"{'=' * 70}")
        print(f"{'方案':<25} {'获取数':<8} {'耗时(ms)':<12} {'相对速度'}")
        print("-" * 70)
        
        baseline = None
        for name, res_words, total_ms in results:
            if '串行' in name:
                baseline = total_ms
                print(f"{name:<25} {len(res_words):<8} {total_ms:<12.1f} 1.0x")
            else:
                if baseline and baseline > 0:
                    speed = baseline / total_ms if total_ms > 0 else float('inf')
                    print(f"{name:<25} {len(res_words):<8} {total_ms:<12.1f} {speed:.2f}x")
                else:
                    print(f"{name:<25} {len(res_words):<8} {total_ms:<12.1f} N/A")


if __name__ == "__main__":
    run_all_benchmarks()