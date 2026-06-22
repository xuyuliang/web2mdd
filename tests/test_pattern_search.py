"""
正则表达式（通配符模式）搜索的测试用例

测试覆盖：
- 前缀模式：per*, dur*
- 后缀模式：*tic
- 中间通配模式：*tic*
- 单字符通配：c.t
- 混合模式
- 空结果

用法：
    python -m pytest tests/test_pattern_search.py -v
    或直接运行：
    python tests/test_pattern_search.py
"""
import sys
import os
import re
import time

# 确保能找到 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.word_freq import WordFreq

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "The little dict", "TLD.mdx.index.db")

wf = WordFreq(DB_PATH)


def search_all(pattern: str) -> list[str]:
    """全量搜索所有匹配的 COCA 单词（不带 max_results 截断）"""
    regex_parts = []
    for c in pattern:
        if c == "*":
            regex_parts.append(".*")
        elif c == ".":
            regex_parts.append(".")
        else:
            regex_parts.append(re.escape(c))
    regex = re.compile("^" + "".join(regex_parts) + "$", re.IGNORECASE)
    # 从数据库获取所有单词（按词频排序，使用 DISTINCT 去重）
    cursor = wf.cursor
    cursor.execute("SELECT DISTINCT LOWER(word) FROM coca_words ORDER BY frequency ASC")
    return [w[0] for w in cursor.fetchall() if regex.match(w[0])]


def test_search_prefix():
    """前缀模式：查询以 dur 开头的所有单词"""
    results = search_all("dur*")
    assert "during" in results, "during 应该在 dur* 结果中"
    assert "duration" in results, "duration 应该在 dur* 结果中"
    assert "durable" in results, "durable 应该在 dur* 结果中"
    print(f"[PASS] dur*: {len(results)} 个匹配")


def test_search_suffix():
    """后缀模式：查询以 tic 结尾的所有单词"""
    results = search_all("*tic")
    assert "dramatic" in results, "dramatic 应该在 *tic 结果中"
    assert "automatic" in results, "automatic 应该在 *tic 结果中"
    print(f"[PASS] *tic: {len(results)} 个匹配")


def test_search_middle():
    """中间通配模式：查询包含 tic 的所有单词"""
    results = search_all("*tic*")
    assert "tick" in results, "tick 应该在 *tic* 结果中"
    assert "political" in results, "political 应该在 *tic* 结果中"
    assert "practice" in results, "practice 应该在 *tic* 结果中"
    print(f"[PASS] *tic*: {len(results)} 个匹配（包含 tick）")


def test_search_single_char_wildcard():
    """单字符通配 . 的测试"""
    results = search_all("c.t")
    assert "cat" in results, "cat 应该在 c.t 结果中"
    assert "cut" in results, "cut 应该在 c.t 结果中"
    assert "cot" in results, "cot 应该在 c.t 结果中"
    print(f"[PASS] c.t: {results}")


def test_search_no_results():
    """无匹配结果的情况"""
    results = search_all("zzzzz*")
    assert len(results) == 0, "zzzzz* 应该没有匹配"
    print(f"[PASS] zzzzz*: 空结果正确")


def test_search_exact_word():
    """精确单词（无通配符）"""
    results = search_all("hello")
    assert "hello" in results
    assert len(results) == 1
    print(f"[PASS] hello: 精确匹配正确")


def test_max_results_limit():
    """验证现有限制逻辑：*tic* 被 max_results=50 截断时的情况"""
    results_limited = wf.search("*tic*", max_results=50)
    results_full = search_all("*tic*")
    # 实际返回数量可能少于 50（如果总匹配数不足）
    assert len(results_limited) == min(50, len(results_full))
    tick_in_limited = "tick" in results_limited
    tick_in_full = "tick" in results_full
    print(f"[INFO] *tic* max_results=50: 返回 {len(results_limited)} 个，tick={'包含' if tick_in_limited else '不包含'}")
    print(f"[INFO] *tic* 全量搜索: {len(results_full)} 个，tick={'包含' if tick_in_full else '不包含'}")


def test_performance():
    """性能测试：全量搜索应快于 500ms"""
    t0 = time.time()
    search_all("*tic*")
    dt = time.time() - t0
    assert dt < 0.5, f"全量搜索耗时 {dt*1000:.1f}ms，超过 500ms 阈值"
    print(f"[PASS] *tic* 全量搜索性能: {dt*1000:.1f}ms")


def test_ranked_includes_tick():
    """修复验证：如果全量收集再取前50，tick 应该出现"""
    results_all = search_all("*tic*")
    if len(results_all) <= 50:
        print(f"[INFO] *tic* 总共 {len(results_all)} 个匹配，"
              f"rank 第 {results_all.index('tick')+1}")
    else:
        print(f"[INFO] *tic* 共 {len(results_all)} 个（超过50），"
              f"tick 排名第 {results_all.index('tick')+1}，"
              f"前50个中仍不含 tick")


if __name__ == "__main__":
    print("=" * 60)
    print("正则表达式模式搜索测试")
    print("=" * 60)
    print()

    test_search_prefix()
    test_search_suffix()
    test_search_middle()
    test_search_single_char_wildcard()
    test_search_no_results()
    test_search_exact_word()
    print()
    print("=" * 60)
    print("确认当前 BUG")
    print("=" * 60)
    test_max_results_limit()
    print()
    print("=" * 60)
    print("当前状态下 *tic* 完整结果")
    print("=" * 60)
    results_full = search_all("*tic*")
    for i, w in enumerate(results_full, 1):
        marker = " <-- tick" if w == "tick" else ""
        print(f"  {i:3d}. {w}{marker}")
    print(f"\n总计: {len(results_full)} 个")
    print(f"tick 排名: {results_full.index('tick') + 1}")

    print()
    print("=" * 60)
    print("性能测试")
    print("=" * 60)
    test_performance()
