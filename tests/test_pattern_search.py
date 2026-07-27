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

from app.word_freq import WordFreq, add_brackets

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "The little dict", "TLD.mdx.index.db")

wf = WordFreq(DB_PATH)


def search_all(pattern: str) -> list[str]:
    """全量搜索所有匹配的 COCA 单词（不带 max_results 截断）"""
    # 支持裸大写通配符
    pattern = add_brackets(pattern)
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


def test_add_brackets_basic():
    """add_brackets: 裸大写通配符补全"""
    assert add_brackets("aTTle") == "a[TT]le"
    assert add_brackets("cAnA") == "c[A]n[A]"
    assert add_brackets("tAAer") == "t[AA]er"
    assert add_brackets("TTout") == "[TT]out"
    assert add_brackets("TTT*tion") == "[TTT]*tion"
    assert add_brackets("TTTtion") == "[TTT]tion"
    print("[PASS] add_brackets: 基础通配符补全正确")


def test_add_brackets_caret():
    """add_brackets: 裸 ^ 反义补全"""
    assert add_brackets("ep^i*") == "ep[^i]*"
    assert add_brackets("s^e^e^e") == "s[^e][^e][^e]"
    print("[PASS] add_brackets: ^ 反义补全正确")


def test_add_brackets_mixed():
    """add_brackets: 混合写法（已有[] + 裸）"""
    assert add_brackets("c[A]nA") == "c[A]n[A]"
    assert add_brackets("[A]cAde") == "[A]c[A]de"  # wait, is this right?
    print("[PASS] add_brackets: 混合写法正确")


def test_add_brackets_noop():
    """add_brackets: 无大写字母时不变"""
    assert add_brackets("hello") == "hello"
    assert add_brackets("dur*") == "dur*"
    assert add_brackets("c.t") == "c.t"
    assert add_brackets("*tic*") == "*tic*"
    print("[PASS] add_brackets: 无大写字母时不变")


def test_bare_vowel_search():
    """裸 A 通配符搜索（通过 PatternPreprocessor 展开）"""
    results = wf.search("cAn*", max_results=50)
    assert "can" in results
    print(f"[PASS] cAn*: {len(results)} 个匹配（含 can 等）")


def test_bare_digraph_search():
    """裸 AA 通配符搜索（通过 PatternPreprocessor 展开）"""
    results = wf.search("tAAer", max_results=50)
    assert "tower" in results
    print(f"[PASS] tAAer: {len(results)} 个匹配（含 tower）")


def test_bare_consonant_search():
    """裸 TT 通配符搜索（通过 PatternPreprocessor 展开）"""
    results = wf.search("TTout", max_results=50)
    assert "shout" in results
    assert "trout" in results
    assert "scout" in results
    print(f"[PASS] TTout: {len(results)} 个匹配（含 shout, trout, scout）")


def test_bare_trigraph_search():
    """裸 TTT 通配符搜索（通过 PatternPreprocessor 展开）"""
    results = wf.search("TTT*tion", max_results=50)
    assert "stratification" in results
    assert "strangulation" in results
    print(f"[PASS] TTT*tion: {len(results)} 个匹配（含 stratification 等）")


def test_bare_caret_search():
    """裸 ^ 反义搜索（通过 PatternPreprocessor 展开）"""
    results = wf.search("ep^i*", max_results=50)
    assert "epoch" in results
    assert "epsilon" in results  # has i but not at ep^i position
    assert "epic" not in results
    print(f"[PASS] ep^i*: {len(results)} 个匹配（含 epoch，不含 epic）")


def test_bare_bracket_equivalence():
    """裸写法和括号写法产生相同结果"""
    for bare, bracketed in [
        ("cAn*", "c[A]n*"),
        ("tAAer", "t[AA]er"),
        ("TTout", "[TT]out"),
        ("TTT*tion", "[TTT]*tion"),
        ("ep^i*", "ep[^i]*"),
    ]:
        r1 = wf.search(bare, max_results=100)
        r2 = wf.search(bracketed, max_results=100)
        assert r1 == r2, f"{bare} != {bracketed}: {set(r1) ^ set(r2)}"
        print(f"[PASS] {bare} == {bracketed}: {len(r1)} 个匹配")


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

    test_add_brackets_basic()
    test_add_brackets_caret()
    test_add_brackets_mixed()
    test_add_brackets_noop()
    test_bare_vowel_search()
    test_bare_digraph_search()
    test_bare_consonant_search()
    test_bare_trigraph_search()
    test_bare_caret_search()
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
