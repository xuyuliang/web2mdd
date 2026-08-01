"""
查词拆词 - 基于 FastAPI + htmx 的 TLD 词典查询网站

使用 SQLite 缓存索引，大幅降低内存占用
"""

import os
import re
import time
import threading
import webbrowser
import bisect
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.mdx_sqlite_reader import MDXSQLiteReader
from app.word_freq import WordFreq, get_preprocessor, add_brackets
from app.related_words import RelatedWordsSearcher
from app.word_cutter import WordCutter

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时加载数据，关闭时释放资源"""
    # 启动时加载所有数据
    print("正在加载词典...")
    mdx_reader = MDXReader(MDX_PATH, DB_PATH)
    print("[OK] 词典加载完成，服务器就绪！")

    print("正在加载词根切分数据...")
    word_cutter = WordCutter(BASE_DIR)
    print("[OK] 词根切分数据加载完成")

    print("正在加载蒸馏模型2...")
    from app.distill_cutter import DistillCutter
    distill_model_path = os.path.join(BASE_DIR, "蒸馏计划2完整词根", "output", "model.npz")
    distill_rules_path = os.path.join(BASE_DIR, "蒸馏计划2完整词根", "rules.py")
    if os.path.exists(distill_model_path):
        distill_cutter = DistillCutter(distill_model_path, distill_rules_path)
        print("[OK] 蒸馏模型2加载完成")
    else:
        distill_cutter = None
        print("[WARN] 未找到蒸馏模型2权重，跳过:", distill_model_path)

    print("正在加载 COCA 词频数据...")
    word_freq = WordFreq(DB_PATH)
    print("[OK] 词频数据加载完成")

    DATA_DIR = os.path.join(BASE_DIR, "数据资料")
    print("正在加载相似词搜索数据...")
    related_words_searcher = RelatedWordsSearcher(DB_PATH, DATA_DIR)
    print("[OK] 相似词搜索器初始化完成")

    # 存储到 app.state
    app.state.mdx_reader = mdx_reader
    app.state.word_cutter = word_cutter
    app.state.distill_cutter = distill_cutter
    app.state.word_freq = word_freq
    app.state.related_words_searcher = related_words_searcher

    # 所有数据加载完成，延迟打开浏览器（服务器上通过环境变量 OPEN_BROWSER=0 关闭）
    if os.environ.get("OPEN_BROWSER", "1") == "1":
        print("正在打开浏览器...")
        threading.Timer(2.0, lambda: webbrowser.open('http://localhost:8000')).start()

    yield

    # 关闭时释放资源
    mdx_reader.close()




app = FastAPI(lifespan=lifespan)

# __file__ 现在是 web2mdd/app/main.py，需上移两级到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE_DIR, "The little dict")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
DB_PATH = os.path.join(DICT_DIR, "TLD.mdx.index.db")
CSS_PATH = os.path.join(DICT_DIR, "p.css")
DICT_STATIC_DIR = DICT_DIR  # 词典目录，用于提供静态资源
# COCA 词频数据已从 TLD.mdx.index.db 的 coca_words 表读取，不再需要 txt 文件
PATTERN_PAGE_SIZE = 10  # 模式搜索每页显示数量
PATTERN_MAX_TOTAL = 50  # 模式搜索预获取的候选单词总数（用于排序和分页）

templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Python 3.14 兼容：Jinja2 3.1.6 缓存键含 dict（不可哈希），禁用缓存
templates.env.cache = None


class MDXReader:
    """MDX 词典读取器 - 使用 SQLite 缓存索引，内存占用极低
    
    包装 MDXSQLiteReader，保持与原 API 兼容
    """
    
    def __init__(self, path, db_path=None):
        t0 = time.time()
        
        if db_path is None:
            db_path = path + ".index.db"
        
        self._sqlite_reader = MDXSQLiteReader(path, db_path, build_if_not_exists=True)
        self.path = path
        self.encoding = self._sqlite_reader.encoding
        self._substyle = self._sqlite_reader._substyle
        self._stylesheet = self._sqlite_reader._stylesheet
        
        print(f"[MDX] SQLite 阅读器初始化完成，耗时 {time.time()-t0:.1f}s")
    
    @staticmethod
    def _fix_resource_paths(html: str) -> str:
        """将 HTML 中的资源路径替换为带 /static/ 前缀的路径
        
        处理 href="xxx.css", href='xxx.css', src="xxx.png" 等相对路径引用。
        避免重复添加 /static/ 前缀。
        """
        if not isinstance(html, str):
            return html
        
        # 定义资源文件扩展名
        css_pattern = r'(href\s*=\s*)["\']([^"\']*?\.css)["\']'
        img_pattern = r'(src\s*=\s*)["\']([^"\']*\.(?:png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot))["\']'
        js_pattern = r'(src\s*=\s*)["\']([^"\']*?\.js)["\']'
        
        def add_static_prefix(match):
            """只有当路径不以 / 或 http:// 或 data: 开头时才添加 /static/ 前缀"""
            prefix = match.group(1)
            path = match.group(2)
            quote = match.group(3) if match.lastindex >= 3 else ''
            
            # 如果路径已经是绝对路径或完整URL，保持不变
            if path.startswith('/static/') or path.startswith('http://') or path.startswith('https://') or path.startswith('data:'):
                return match.group(0)
            # 如果路径以 / 开头但不是 /static/，添加 /static/ 前缀
            if path.startswith('/'):
                return prefix + '"' + '/static' + path + '"'
            # 相对路径，添加 /static/ 前缀
            return prefix + '"' + '/static/' + path + '"'
        
        # 处理双引号的 href
        html = re.sub(
            r'(href\s*=\s*)"([^"]*?\.css)"',
            lambda m: m.group(0) if m.group(2).startswith(('/static/', 'http://', 'https://', 'data:')) else m.group(1) + '"/static/' + m.group(2) + '"',
            html
        )
        # 处理单引号的 href
        html = re.sub(
            r"(href\s*=\s*)'([^']*?\.css)'",
            lambda m: m.group(0) if m.group(2).startswith(('/static/', 'http://', 'https://', 'data:')) else m.group(1) + "'/static/" + m.group(2) + "'",
            html
        )
        # 处理双引号的 src (图片)
        html = re.sub(
            r'(src\s*=\s*)"([^"]*\.(?:png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot))"',
            lambda m: m.group(0) if m.group(2).startswith(('/static/', 'http://', 'https://', 'data:')) else m.group(1) + '"/static/' + m.group(2) + '"',
            html
        )
        # 处理单引号的 src (图片)
        html = re.sub(
            r"(src\s*=\s*)'([^']*?\.(?:png|jpg|jpeg|gif|svg|ico))'",
            lambda m: m.group(0) if m.group(2).startswith(('/static/', 'http://', 'https://', 'data:')) else m.group(1) + "'/static/" + m.group(2) + "'",
            html
        )
        # 处理 js 文件的 src
        html = re.sub(
            r'(src\s*=\s*)"([^"]*?\.js)"',
            lambda m: m.group(0) if m.group(2).startswith(('/static/', 'http://', 'https://', 'data:')) else m.group(1) + '"/static/' + m.group(2) + '"',
            html
        )
        
        return html
    
    def _substitute_stylesheet(self, text):
        """替换文本中的样式标记"""
        if not self._substyle or not self._stylesheet:
            return text
        txt_list = re.split(r'`\d+`', text)
        txt_tag = re.findall(r'`\d+`', text)
        txt_styled = txt_list[0]
        for j, p in enumerate(txt_list[1:]):
            style = self._stylesheet[txt_tag[j]]
            if p and p[-1] == '\n':
                txt_styled = txt_styled + style[0] + p.rstrip() + style[1] + '\r\n'
            else:
                txt_styled = txt_styled + style[0] + p + style[1]
        return txt_styled
    
    @staticmethod
    def _has_pattern(word: str) -> bool:
        """检查单词中是否含有通配符 * 、 . 或字符类 [abc]"""
        return '*' in word or '.' in word or ('[' in word and ']' in word)
    
    @staticmethod
    def _stem_highlight(stem: str, word: str) -> str:
        """将词干在推荐词中的匹配部分高亮显示"""
        stem_lower = stem.lower()
        word_lower = word.lower()
        pos = word_lower.find(stem_lower)
        if pos >= 0:
            before = word[:pos]
            matched = word[pos:pos + len(stem)]
            after = word[pos + len(stem):]
            return f'{before}<span class="stem-highlight">{matched}</span>{after}'
        return word
    @staticmethod
    def _pattern_highlight(pattern: str, word: str) -> str:
        """将匹配到的单词中的用户输入字面量部分用深蓝色高亮
        
        显示整个单词，通配符匹配的部分正常显示（不高亮），
        字面字符部分用 <span class="hl-literal"> 包裹高亮。
        连续的字面字符会合并为一个高亮标签。
        被通配符隔开的字面字符分别高亮。
        """
        # 策略：
        # 1. 从 pattern 中提取所有连续的字面字符段及其位置
        # 2. 在每个字面字符段前面加上 .* ，依次在 word 中搜索
        # 3. 每个匹配的部分分别高亮
        
        # 提取字面字符段列表，保持顺序
        literal_segments = []  # [chars]
        current_literal = []
        
        i = 0
        while i < len(pattern):
            c = pattern[i]
            if c in ('*', '.'):
                # 通配符，保存当前的字面字符段
                if current_literal:
                    literal_segments.append(''.join(current_literal))
                    current_literal = []
                i += 1
            elif c == '[':
                # 查找闭合括号
                j = pattern.find(']', i + 1)
                if j == -1:
                    # 没有闭合括号，当作普通字符
                    current_literal.append(c)
                    i += 1
                else:
                    # 整个 [...] 是通配符，保存当前字面段
                    if current_literal:
                        literal_segments.append(''.join(current_literal))
                        current_literal = []
                    i = j + 1  # 跳过 ]
            else:
                current_literal.append(c)
                i += 1
        
        # 保存最后的字面字符段
        if current_literal:
            literal_segments.append(''.join(current_literal))
        
        # 如果没有字面字符段，直接返回原单词
        if not literal_segments:
            return word
        
        # 依次在每个字面字符段前面搜索，记录匹配位置
        search_pos = 0
        match_ranges = []  # [(start, end), ...]
        
        for idx, chars in enumerate(literal_segments):
            escaped = re.escape(chars)
            if idx < len(literal_segments) - 1:
                # 不是最后一个段，用 .* 前缀搜索（贪婪匹配到下一个字面段）
                pattern_search = f'.*{escaped}'
            else:
                # 最后一个段，精确匹配
                pattern_search = escaped
            
            m = re.search(pattern_search, word[search_pos:], re.IGNORECASE)
            if m:
                matched_text = m.group(0)
                # 计算字面部分在匹配文本中的位置
                # 对于非最后一段，matched_text 可能是 "xxxtric"，我们需要找到 "tric" 的开始位置
                if idx < len(literal_segments) - 1:
                    # 找到字面段在匹配文本中的位置
                    literal_pos = matched_text.lower().find(chars.lower())
                    actual_start = search_pos + m.start() + literal_pos
                    actual_end = actual_start + len(chars)
                else:
                    # 最后一段，整个匹配就是字面部分
                    actual_start = search_pos + m.start()
                    actual_end = search_pos + m.end()
                
                match_ranges.append((actual_start, actual_end))
                search_pos = actual_end
            else:
                # 找不到这个段，返回原单词
                return word
        
        # 构建 HTML：在高亮位置插入标签
        html_parts = []
        pos = 0
        for start, end in match_ranges:
            html_parts.append(word[pos:start])
            html_parts.append(f'<span class="hl-literal">{word[start:end]}</span>')
            pos = end
        html_parts.append(word[pos:])
        
        return ''.join(html_parts)
    @staticmethod
    def _glob_bracket_to_regex(bracket_content: str) -> str:
        """将 GLOB 方括号内容转换为正则表达式字符类
        
        处理高级占位符：
        - 'A' -> '[aeiou]'
        - 'T' -> '[bcdfghjklmnpqrstvwxyz]'
        - 'AA' -> '(ai|ay|ee|...)'  # 注意：AA 可能匹配多个字符，用非捕获组
        - 'aeo' -> '[aeo]'  # 普通字符类保持不变
        """
        preprocessor = get_preprocessor()
        
        if bracket_content in preprocessor.replacements:
            replacement = preprocessor.replacements[bracket_content]
            if isinstance(replacement, list):
                # 多字符组合：如 AA -> ["ai", "ay", ...]
                # 转换为正则：(?:ai|ay|ee|...)
                return '(?:' + '|'.join(replacement) + ')'
            else:
                # 单字符类：如 A -> "aeiou"
                return f'[{replacement}]'
        else:
            # 不是高级占位符，直接作为字符类
            return f'[{bracket_content}]'
    
    @staticmethod
    def _extract_ipa(html: str) -> str:
        """从完整释义 HTML 中提取音标"""
        if not isinstance(html, str) or not html:
            return ""
        m = re.search(r'<span class="ipa">([^<]*)</span>', html)
        if m:
            return m.group(1).strip()
        return ""
    
    @staticmethod
    def _extract_summary(html: str) -> str:
        """从完整释义 HTML 中提取摘要（优先 coca2，不存在则取 gdc）"""
        if not isinstance(html, str) or not html:
            return ""
        
        # 先尝试提取 coca2
        m = re.search(r'<div class="coca2">.*?</div>', html)
        if m:
            return m.group(0)
        
        # coca2 不存在，尝试提取 gdc
        m = re.search(r'<div class="gdc">.*?</div>\s*</div>', html, re.DOTALL)
        if m:
            return m.group(0)
        
        return ""
    
    def _get_mdx_word(self, lower_word: str) -> str | None:
        """将小写单词映射到 MDX 中的原始大小写形式"""
        # 使用 SQLite 的前缀搜索
        results = self._sqlite_reader.prefix_search(lower_word, limit=1)
        if results:
            return results[0][0]
        return None
    
    def pattern_search_ranked(self, pattern: str):
        """带词频排序的模式搜索
        
        预获取最多50个候选单词用于排序，但释义查询采用分页按需加载。
        直接使用 COCA 返回的小写单词，不做大小写映射（lookup 方法内部会自动处理小写匹配）。
        """
        coca_results = app.state.word_freq.search(pattern, max_results=PATTERN_MAX_TOTAL)
        
        # 直接使用 COCA 返回的小写单词，不做大小写映射
        # MDXSQLiteReader.lookup() 内部会先查 word 精确匹配，再查 word_lower 匹配
        ranked_out = coca_results[:PATTERN_MAX_TOTAL]
        unranked: list[str] = []
        total_count = len(ranked_out)
        
        return ranked_out, unranked, total_count
    
    def lookup(self, word):
        """查找单词，返回 (结果, 是否精确匹配)
        
        * 普通单词：精确匹配 或 前缀建议
        * 包含 * 或 . 的模式：先精确匹配，失败则返回排序结果
        """
        word = word.strip()
        if not word:
            return None, False

        # 补全裸大写通配符（如 aTTle → a[TT]le）
        word = add_brackets(word)

        word_lower = word.lower()
        
        # 通配符模式：包含 * 或 . 时直接跳过精确匹配，做正则搜索
        if self._has_pattern(word):
            ranked, unranked, total = self.pattern_search_ranked(word)
            return (ranked, unranked, total), False
        
        # 精确查找
        result, exact = self._sqlite_reader.lookup(word)
        if exact and result:
            # 修复 HTML 中的资源路径，将相对路径替换为 /static/ 前缀
            if isinstance(result, str):
                result = self._fix_resource_paths(result)
            return result, True
        
        # 尝试小写匹配
        if word != word_lower:
            result, exact = self._sqlite_reader.lookup(word_lower)
            if exact and result:
                if isinstance(result, str):
                    result = self._fix_resource_paths(result)
                return result, True
        
        # 前缀匹配
        suggestions = self._sqlite_reader.prefix_search(word_lower, limit=10)
        if suggestions:
            suggestion_words = [s[0] for s in suggestions if s[0].lower() != word_lower]
            if suggestion_words:
                return suggestion_words[:10], False
        
        return [], False
    
    def close(self):
        """关闭阅读器"""
        self._sqlite_reader.close()


def is_valid_word(word: str) -> bool:
    """判断单词是否在词典中存在（用于词根词缀分析的词干验证）"""
    if len(word) < 2:
        return False
    result, exact = app.state.mdx_reader.lookup(word)
    return exact


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/guide")
async def guide_page(request: Request):
    """使用说明页面"""
    return templates.TemplateResponse(request, "guide.html")


@app.get("/debug")
async def debug_page(request: Request):
    """调试页面 - 用于测试返回链接流程"""
    return templates.TemplateResponse(request, "debug.html")


def make_template_response(request, template_name, context, push_url=None):
    """创建模板响应，并添加 HX-Push header 来自定义浏览器 URL"""
    from fastapi import Response
    response = templates.TemplateResponse(request, template_name, context)
    if push_url:
        # 让 htmx 推送指定的 URL 而不是 /api/lookup?...
        response.headers["HX-Push"] = push_url
    return response


@app.get("/api/lookup")
async def lookup(request: Request, word: str = Query(..., description="单词"), page: int = Query(1, ge=1, description="页码"), back_word: str = Query(None, description="返回搜索词"), back_page: int = Query(1, description="返回页码")):
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    word = add_brackets(word.strip())
    result, exact = request.app.state.mdx_reader.lookup(word)

    if exact:
        # 精确匹配时进行词根切分和相似词搜索
        pipeline_result = request.app.state.word_cutter.segment(word)
        affix_template = templates.env.get_template("partials/_affix_result.html")
        affix_html = affix_template.render(pipeline=pipeline_result)
        related_words_html = None

        distill_html = None
        if request.app.state.distill_cutter is not None:
            distill_segs = request.app.state.distill_cutter.segment(word)
            distill_template = templates.env.get_template("partials/_distill_result.html")
            distill_html = distill_template.render(word=word, segments=distill_segs)

        if pipeline_result and pipeline_result.get("parts"):
            parts = pipeline_result["parts"]
            meaningful = [p for p in parts if p.get("meaning") and p.get("source")]
            if meaningful:
                stem = max(meaningful, key=lambda p: len(p["text"]))["text"]
                related_results = request.app.state.related_words_searcher.search_and_score(stem, max_results=30)
                if related_results:
                    for rw in related_results:
                        rw["highlighted_word"] = MDXReader._stem_highlight(stem, rw["word"])
                    related_template = templates.env.get_template("partials/_related_words.html")
                    related_words_html = related_template.render(
                        stem=stem,
                        related_words=related_results,
                        back_word=back_word if back_word else word,
                    )

        combined = result + affix_html + (distill_html or "") + (related_words_html or "")

        # 构建推送 URL，包含所有相关参数以便历史回退时恢复完整状态
        push_url_parts = ["?word=" + word]
        if back_word:
            push_url_parts.append("&back_word=" + back_word)
        if back_page and int(back_page) > 1:
            push_url_parts.append("&back_page=" + str(back_page))
        push_url = "".join(push_url_parts)

        return make_template_response(
            request, "partials/_lookup_result.html",
            {"content": combined, "back_word": back_word, "back_page": back_page, "word": word},
            push_url=push_url
        )

    # 模式搜索（包含 * 或 .）
    if MDXReader._has_pattern(word):
        if result:
            ranked, unranked, total = result
        else:
            ranked, unranked, total = [], [], 0

        total_pages = max(1, (total + PATTERN_PAGE_SIZE - 1) // PATTERN_PAGE_SIZE)
        page = min(page, total_pages)

        all_words = ranked + unranked
        start_idx = (page - 1) * PATTERN_PAGE_SIZE
        page_words = all_words[start_idx:start_idx + PATTERN_PAGE_SIZE]

        page_results = []
        for w in page_words:
            html, _ = request.app.state.mdx_reader.lookup(w)
            highlighted = MDXReader._pattern_highlight(word, w)
            rank = request.app.state.word_freq.get_rank(w)
            if isinstance(html, str) and html:
                summary = MDXReader._extract_summary(html)
                ipa = MDXReader._extract_ipa(html)
                page_results.append({"word": w, "highlighted_word": highlighted, "summary": summary, "ipa": ipa, "has_full": True, "rank": rank})
            else:
                page_results.append({"word": w, "highlighted_word": highlighted, "summary": "", "ipa": "", "has_full": False, "rank": rank})

        ranked_count = len(ranked)
        page_ranked_count = max(0, min(PATTERN_PAGE_SIZE, ranked_count - start_idx))

        # 推送到首页 URL，包含模式搜索词和 back_word
        push_url = f"?word={word}"
        if back_word:
            push_url += f"&back_word={back_word}"
        if int(page) > 1:
            push_url += f"&page={page}"

        return make_template_response(
            request, "partials/_pattern_results.html",
            {
                "word": word,
                "results": page_results,
                "page": page,
                "total_pages": total_pages,
                "total_count": total,
                "page_ranked_count": page_ranked_count,
                "back_word": back_word,
                "back_page": back_page,
            },
            push_url=push_url
        )

    # 普通单词：前缀建议
    if result:
        return make_template_response(
            request, "partials/_suggestions.html",
            {"word": word, "suggestions": result, "pattern_mode": False},
            push_url=f"?word={word}"
        )

    return make_template_response(
        request, "partials/_suggestions.html",
        {"word": word, "suggestions": [], "pattern_mode": False}
    )


@app.get("/api/lookup_expand")
async def lookup_expand(request: Request, word: str = Query(..., description="单词")):
    """展开某个单词的完整释义（用于模式搜索的点击展开）"""
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    html, exact = request.app.state.mdx_reader.lookup(word)
    if exact and html:
        pipeline_result = request.app.state.word_cutter.segment(word)
        affix_template = templates.env.get_template("partials/_affix_result.html")
        affix_html = affix_template.render(pipeline=pipeline_result)
        distill_html = ""
        if request.app.state.distill_cutter is not None:
            distill_segs = request.app.state.distill_cutter.segment(word)
            distill_template = templates.env.get_template("partials/_distill_result.html")
            distill_html = distill_template.render(word=word, segments=distill_segs)
        combined = html + affix_html + distill_html
        return templates.TemplateResponse(
            request, "partials/_lookup_result.html",
            {"content": combined}
        )

    return templates.TemplateResponse(
        request, "partials/_suggestions.html",
        {"word": word, "suggestions": [], "pattern_mode": False}
    )


# 媒体类型映射
MEDIA_TYPES = {
    ".css": "text/css",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".js": "application/javascript",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".json": "application/json",
    ".ini": "text/plain",
    ".txt": "text/plain",
}


# ==================== 调试日志接口 ====================
LOG_DIR = Path(BASE_DIR) / "logs"
LOG_DIR.mkdir(exist_ok=True)
DEBUG_LOG_FILE = LOG_DIR / "web_debug.log"

# 配置调试日志记录器
debug_logger = logging.getLogger("web_debug")
debug_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(DEBUG_LOG_FILE, encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
debug_logger.addHandler(file_handler)


@app.post("/api/debug/log")
async def submit_debug_log(entries: List[dict]):
    """接收前端提交的调试日志
    
    请求体格式: [{"timestamp": "...", "level": "info|warn|error", "message": "...", "url": "..."}, ...]
    """
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="期望列表格式")
    
    for entry in entries:
        ts = entry.get("timestamp", "")
        level = entry.get("level", "info")
        message = entry.get("message", "")
        url = entry.get("url", "")
        debug_logger.info(f"[{level}] {message} | url={url}")
    
    return JSONResponse({"status": "ok", "received": len(entries)})


@app.get("/api/debug/logs")
async def get_debug_logs(count: int = 100):
    """读取最近的调试日志"""
    if not DEBUG_LOG_FILE.exists():
        return JSONResponse({"logs": [], "message": "无日志文件"})
    
    with open(DEBUG_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    return JSONResponse({"logs": lines[-count:]})


@app.get("/config.ini")
async def get_config_ini():
    """提供 static 目录下的 config.ini 文件"""
    config_path = os.path.join(STATIC_DIR, "config.ini")
    if os.path.exists(config_path):
        return FileResponse(config_path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="config.ini not found")


@app.get("/static/{file_path:path}")
async def get_static_file(file_path: str):
    """通用静态文件服务路由（favicon、style.css 等）"""
    file_full_path = os.path.normpath(os.path.join(STATIC_DIR, file_path))
    if not file_full_path.startswith(os.path.normpath(STATIC_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if os.path.exists(file_full_path) and os.path.isfile(file_full_path):
        ext = os.path.splitext(file_full_path)[1].lower()
        media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
        return FileResponse(file_full_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)