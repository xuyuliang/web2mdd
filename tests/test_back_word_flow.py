"""
测试返回链接流程

验证以下场景：
1. 从首页搜索单词后，返回结果中是否包含正确的返回逻辑
2. 从模式搜索结果点击进入单词详情页时，back_word 是否正确传递
3. 返回链接的 HTML 是否正确生成

注意：直接测试模板渲染，避免 SQLite 线程问题
"""

import pytest
import os

# 确保可以找到 templates 目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def test_lookup_result_has_back_link_when_back_word_present():
    """测试 _lookup_result.html 在 back_word 存在时包含返回链接"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_lookup_result.html")
    
    # 场景：从模式搜索结果点击进入单词详情页
    # back_word 是模式搜索词，如 "*beaut*"
    html = template.render(
        content="<div>单词释义</div>",
        back_word="*beaut*",
        back_page="1",
        word="beautiful"
    )
    
    # 应该包含返回链接
    assert "back-link" in html
    assert "返回" in html
    assert "*beaut*" in html or "beaut" in html


def test_lookup_result_no_back_link_when_back_word_none():
    """测试 _lookup_result.html 在 back_word 为 None 时不包含返回链接"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_lookup_result.html")
    
    # 场景：从首页直接搜索单词，没有上一页
    html = template.render(
        content="<div>单词释义</div>",
        back_word=None,
        back_page=None,
        word="beautiful"
    )
    
    # 不应该包含返回链接
    assert "back-link" not in html


def test_pattern_results_has_back_link_when_back_word_present():
    """测试 _pattern_results.html 在 back_word 存在时包含返回链接"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_pattern_results.html")
    
    # 场景：在单词详情页触发模式搜索
    # back_word 是当前单词，如 "beautiful"
    html = template.render(
        word="*beaut*",
        results=[],
        page=1,
        total_pages=1,
        total_count=0,
        page_ranked_count=0,
        back_word="beautiful",
        back_page=None
    )
    
    # 应该包含返回链接
    assert "back-link" in html
    assert "返回" in html
    # 返回链接应该指向 back_word
    assert "beautiful" in html


def test_pattern_results_no_back_link_when_back_word_none():
    """测试 _pattern_results.html 在 back_word 为 None 时不包含返回链接"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_pattern_results.html")
    
    # 场景：从首页直接进行模式搜索（不太常见，但可能）
    html = template.render(
        word="*beaut*",
        results=[],
        page=1,
        total_pages=1,
        total_count=0,
        page_ranked_count=0,
        back_word=None,
        back_page=None
    )
    
    # 不应该包含返回链接
    assert "back-link" not in html


def test_pattern_results_back_link_points_to_correct_url():
    """测试模式搜索结果的返回链接指向正确的 URL"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_pattern_results.html")
    
    html = template.render(
        word="*beaut*",
        results=[],
        page=1,
        total_pages=3,
        total_count=30,
        page_ranked_count=15,
        back_word="original_search",
        back_page=2
    )
    
    # 返回链接应该包含 back_word 和 page
    assert 'hx-get="/api/lookup?word=original_search&page=2"' in html


def test_pattern_result_click_sets_back_word_correctly():
    """测试从模式搜索结果点击进入单词时，back_word 正确设置为当前模式搜索词"""
    from jinja2 import Environment, FileSystemLoader
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("partials/_pattern_results.html")
    
    # 模拟：当前模式搜索是 "*beaut*"，在第 1 页
    # 点击单词 "beautiful" 时，back_word 应该是 "*beaut*"，back_page 应该是 1
    html = template.render(
        word="*beaut*",
        results=[
            {
                "word": "beautiful",
                "highlighted_word": "<span>beau</span>tiful",
                "summary": "<div>adj. 美丽的</div>",
                "has_full": True,
                "rank": 150
            }
        ],
        page=1,
        total_pages=2,
        total_count=25,
        page_ranked_count=25,
        back_word=None,  # 从模式搜索直接进入，没有 back_word
        back_page=None
    )
    
    # 检查点击链接是否正确设置了 back_word
    # 链接应该是: /api/lookup?word=beautiful&back_word=*beaut*&back_page=1
    assert "back_word=" in html
    assert "back_page=" in html


def test_javascript_back_word_logic():
    """测试 JavaScript 中获取 back_word 的逻辑"""
    # 模拟 URL 没有 word 参数的情况（首页搜索后 URL 未更新）
    from urllib.parse import urlparse, parse_qs
    
    # 场景 1: URL 是 "/"，没有 word 参数
    url = "http://localhost:8000/"
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    back_word_from_url = params.get("back_word", [None])[0]
    word_from_url = params.get("word", [None])[0]
    
    # 当前代码逻辑：如果没有 back_word，尝试从 URL 获取 word
    # 但在 URL 没有 word 参数的情况下，back_word 仍然是 None
    assert back_word_from_url is None
    assert word_from_url is None  # 这就是问题所在！
    
    # 场景 2: URL 是 "/?word=beautiful"，有 word 参数
    url = "http://localhost:8000/?word=beautiful"
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    back_word_from_url = params.get("back_word", [None])[0]
    word_from_url = params.get("word", [None])[0]
    
    # 如果 hx-push-url 正确工作，这里应该能获取到 word
    assert back_word_from_url is None
    assert word_from_url == "beautiful"  # 这样可以正确获取




def simulate_js_get_current_word_from_url(url_string):
    """
    模拟 JavaScript 代码中获取当前搜索单词的逻辑。
    这是关键函数：展示为什么当前的实现会失败。
    """
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url_string)
    params = parse_qs(parsed.query)

    back_word = params.get("back_word", [None])[0]
    back_page = params.get("back_page", [None])[0]

    # 当前代码逻辑：如果没有 back_word，尝试从 URL 获取 word
    if not back_word:
        back_word = params.get("word", [None])[0]

    return back_word, back_page


def test_simulate_url_scenarios():
    """模拟各种 URL 场景，验证 JavaScript 逻辑是否正确"""

    # 场景 1: 初始首页，未进行搜索
    # URL: http://localhost:8000/
    url = "http://localhost:8000/"
    back_word, back_page = simulate_js_get_current_word_from_url(url)
    assert back_word is None, f"场景1失败: 期望 back_word=None, 实际={back_word}"
    print(f"场景1 (初始首页): URL={url}, back_word={back_word}, back_page={back_page}")

    # 场景 2: 搜索后，hx-push-url 生效，URL 更新为 /?word=beautiful
    # URL: http://localhost:8000/?word=beautiful
    url = "http://localhost:8000/?word=beautiful"
    back_word, back_page = simulate_js_get_current_word_from_url(url)
    assert back_word == "beautiful", f"场景2失败: 期望 back_word='beautiful', 实际={back_word}"
    print(f"场景2 (搜索后, hx-push-url 生效): URL={url}, back_word={back_word}, back_page={back_page}")

    # 场景 3: 搜索后，hx-push-url 未生效，URL 仍然是 /
    # URL: http://localhost:8000/
    url = "http://localhost:8000/"
    back_word, back_page = simulate_js_get_current_word_from_url(url)
    assert back_word is None, f"场景3失败: 期望 back_word=None, 实际={back_word}"
    print(f"场景3 (搜索后, hx-push-url 未生效): URL={url}, back_word={back_word}, back_page={back_page}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
