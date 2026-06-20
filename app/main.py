"""
查词拆词 - 基于 FastAPI + htmx 的 TLD 词典查询网站
"""

# ⚠️ 重要：在导入 readmdict 之前，先注入假的 lzo 模块
# TLD.mdx 引擎版本 2.0+，使用 zlib 压缩，不需要真实的 python-lzo 库
import types
import sys
_lzo_stub = types.ModuleType("lzo")
def _lzo_decompress(data, initSize=None, blockSize=None):
    """永远不会被调用 - TLD.mdx 使用 zlib 压缩（版本 2.0+）"""
    raise RuntimeError("lzo decompress called unexpectedly - this MDX uses zlib")
_lzo_stub.decompress = _lzo_decompress
sys.modules["lzo"] = _lzo_stub

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from readmdict import MDX
import os
import bisect
import zlib
import time
import pickle
import re
import lzo  # 使用注入的 stub（引擎 2.0 用 zlib，不会真正调用 lzo）

from app.affix_loader import AffixLoader
from app.word_freq import WordFreq

app = FastAPI()

# __file__ 现在是 web2mdd/app/main.py，需上移两级到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE_DIR, "The little dict")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
CSS_PATH = os.path.join(DICT_DIR, "p.css")
CACHE_PATH = MDX_PATH + ".pkl"  # 缓存文件路径
COCA_PATH = os.path.join(BASE_DIR, "数据资料", "coca60000.txt")
PATTERN_PAGE_SIZE = 15  # 模式搜索每页显示数量
PATTERN_MAX_TOTAL = 50  # 模式搜索最多返回单词数

templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Python 3.14 兼容：Jinja2 3.1.6 缓存键含 dict（不可哈希），禁用缓存
templates.env.cache = None

class MDXReader:
    """MDX 词典读取器 - 内存中建索引，按需解压读取记录"""

    def __init__(self, path):
        t0 = time.time()

        # 检查缓存是否有效（缓存文件存在且比 MDX 文件新）
        cache_valid = False
        if os.path.exists(CACHE_PATH):
            cache_mtime = os.path.getmtime(CACHE_PATH)
            mdx_mtime = os.path.getmtime(path)
            if cache_mtime > mdx_mtime:
                cache_valid = True

        if cache_valid:
            # 从缓存加载（跳过 MDX 文件解析和索引构建）
            print(f"[MDX] 正在加载缓存 {CACHE_PATH} ...")
            with open(CACHE_PATH, "rb") as f:
                cache = pickle.load(f)
            self.path = path
            self.encoding = cache["encoding"]
            self.key_list = cache["key_list"]
            self.word_to_idx = cache["word_to_idx"]
            self.lower_words = cache["lower_words"]
            self.block_infos = cache["block_infos"]
            self.block_starts = cache["block_starts"]
            self.data_offset = cache["data_offset"]
            self._stylesheet = cache.get("_stylesheet")
            self._substyle = cache.get("_substyle", False)
            self.lower_word_set = set(self.lower_words)

            # 兼容旧缓存：加载或重建 lower_to_orig
            if "lower_to_orig" in cache:
                self.lower_to_orig = cache["lower_to_orig"]
            else:
                # 旧缓存，现场重建 lower_to_orig
                print("[MDX] 旧缓存格式，正在重建 lower_to_orig ...")
                self.lower_to_orig = {}
                for i, (off, key_bytes) in enumerate(self.key_list):
                    lower_w = key_bytes.decode("utf-8", errors="ignore").strip().lower()
                    orig_w = key_bytes.decode("utf-8", errors="ignore").strip()
                    self.lower_to_orig[lower_w] = orig_w
                print(f"[MDX] lower_to_orig 重建完成（{len(self.lower_to_orig)} 条目）")

            print(f"[MDX] 缓存加载完成（含 {len(self.key_list)} 词条），耗时 {time.time()-t0:.1f}s")
        else:
            # 完整构建
            print(f"[MDX] 正在解析词典文件...")
            mdx = MDX(path, substyle=True)
            self.path = path
            self.encoding = mdx._encoding
            self.key_list = mdx._key_list  # [(offset, key_bytes)]

            # 单词 -> 索引号
            self.word_to_idx = {}
            for i, (off, key_bytes) in enumerate(self.key_list):
                word = key_bytes.decode("utf-8", errors="ignore").strip()
                self.word_to_idx[word] = i

            # 用于前缀搜索的小写单词列表
            self.lower_words = []
            for i, (off, key_bytes) in enumerate(self.key_list):
                word = key_bytes.decode("utf-8", errors="ignore").strip().lower()
                self.lower_words.append(word)

            # 小写单词 -> 原始大小写形式 的映射（用于 O(1) 查找，替代 bisect）
            # 注意：lower_words 是按 MDX 记录顺序排列的（不是字母序），
            # 所以不能用 bisect 做精确查找。lower_to_orig 字典提供 O(1) 映射。
            self.lower_to_orig = {}
            for i, (off, key_bytes) in enumerate(self.key_list):
                lower_w = key_bytes.decode("utf-8", errors="ignore").strip().lower()
                orig_w = key_bytes.decode("utf-8", errors="ignore").strip()
                self.lower_to_orig[lower_w] = orig_w

            # 小写单词集合，用于 O(1) 存在性检查
            self.lower_word_set = set(self.lower_words)

            print(f"[MDX] 索引构建完成: {len(self.key_list)} 词条, {time.time()-t0:.1f}s")

            # 记录块信息 & 样式表（仅在构建时需要 mdx 对象）
            self._stylesheet = mdx._stylesheet
            self._substyle = mdx._substyle
            self._load_block_info(mdx)

            # 构建完成，保存缓存到磁盘
            print(f"[MDX] 正在保存缓存到 {CACHE_PATH} ...")
            cache = {
                "encoding": self.encoding,
                "key_list": self.key_list,
                "word_to_idx": self.word_to_idx,
                "lower_words": self.lower_words,
                "lower_to_orig": self.lower_to_orig,
                "block_infos": self.block_infos,
                "block_starts": self.block_starts,
                "data_offset": self.data_offset,
                "_stylesheet": self._stylesheet,
                "_substyle": self._substyle,
            }
            with open(CACHE_PATH, "wb") as f:
                pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"[MDX] 缓存保存完成")

    def _load_block_info(self, mdx):
        """从 MDX 对象读取块信息"""
        f = open(self.path, "rb")
        f.seek(mdx._record_block_offset)
        num_blocks = mdx._read_number(f)
        mdx._read_number(f)  # num_entries
        mdx._read_number(f)  # info_size
        mdx._read_number(f)  # block_size

        self.block_infos = []
        for _ in range(num_blocks):
            comp = mdx._read_number(f)
            decomp = mdx._read_number(f)
            self.block_infos.append((comp, decomp))
        self.data_offset = f.tell()
        f.close()

        # 每个块在解压数据流中的起始偏移
        s = 0
        self.block_starts = []
        for comp, decomp in self.block_infos:
            self.block_starts.append(s)
            s += decomp

    def _substitute_stylesheet(self, text):
        """替换文本中的样式标记（替代 mdx._substitute_stylesheet 以减少依赖）"""
        if not self._substyle or not self._stylesheet:
            return text
        txt_list = re.split(r'`\d+`', text)
        txt_tag = re.findall(r'`\d+`', text)
        txt_styled = txt_list[0]
        for j, p in enumerate(txt_list[1:]):
            style = self._stylesheet[txt_tag[j][1:-1]]
            if p and p[-1] == '\n':
                txt_styled = txt_styled + style[0] + p.rstrip() + style[1] + '\r\n'
            else:
                txt_styled = txt_styled + style[0] + p + style[1]
        return txt_styled

    def _decompress_block(self, idx):
        """读取并解压指定索引的记录块"""
        comp, decomp = self.block_infos[idx]
        f = open(self.path, "rb")
        f.seek(self.data_offset)
        for i in range(idx):
            f.seek(self.block_infos[i][0], 1)
        data = f.read(comp)
        f.close()

        bt = data[:4]
        if bt == b"\x00\x00\x00\x00":
            return data[8:]
        elif bt == b"\x01\x00\x00\x00":
            return lzo.decompress(data[8:], initSize=decomp, blockSize=1308672)
        elif bt == b"\x02\x00\x00\x00":
            return zlib.decompress(data[8:])
        raise ValueError(f"未知压缩类型: {bt}")

    def _read_record(self, idx):
        """读取索引 idx 对应的记录内容"""
        rec_off = self.key_list[idx][0]
        next_off = (
            self.key_list[idx + 1][0]
            if idx + 1 < len(self.key_list)
            else self.block_starts[-1] + self.block_infos[-1][1]
        )

        # 定位所属记录块
        bi = bisect.bisect_right(self.block_starts, rec_off) - 1
        if bi < 0:
            bi = 0

        dec = self._decompress_block(bi)
        raw = dec[rec_off - self.block_starts[bi] : next_off - self.block_starts[bi]]

        # 解码（原始编码 -> utf-8）
        text = raw.decode(self.encoding, errors="ignore").strip("\x00")

        # 样式替换
        text = self._substitute_stylesheet(text)

        return text

    @staticmethod
    def _has_pattern(word: str) -> bool:
        """检查单词中是否含有通配符 * 或 ."""
        return '*' in word or '.' in word

    @staticmethod
    def _pattern_to_regex(pattern: str) -> re.Pattern:
        """将用户输入的简单模式（* 和 .）编译为正则表达式

        * → 匹配零或多个字符
        . → 匹配任意单个字符（即正则 . 的语义）
        """
        parts = []
        for c in pattern:
            if c == '*':
                parts.append('.*')
            elif c == '.':
                parts.append('.')
            else:
                parts.append(re.escape(c))
        regex_str = '^' + ''.join(parts) + '$'
        return re.compile(regex_str, re.IGNORECASE)

    @staticmethod
    def _pattern_highlight(pattern: str, word: str) -> str:
        """将匹配到的单词中的用户输入字面量部分用深蓝色高亮

        例如 pattern='pl.d', word='plod' →
        返回 '<span class="hl-literal">pl</span>o<span class="hl-literal">d</span>'

        其中 pl 和 d 是用户字面输入（深蓝色），o 是通配符匹配的部分（默认黑色）
        """
        # 每个字符一个捕获组，区分字面量
        group_parts = []
        is_literal = []
        for c in pattern:
            if c == '*':
                group_parts.append('(.*)')
                is_literal.append(False)
            elif c == '.':
                group_parts.append('(.)')
                is_literal.append(False)
            else:
                group_parts.append(f'({re.escape(c)})')
                is_literal.append(True)
        regex_str = '^' + ''.join(group_parts) + '$'
        regex = re.compile(regex_str, re.IGNORECASE)

        m = regex.match(word)
        if not m:
            # 理论上不应发生，但做 fallback
            return word

        # 合并相邻的字面量 span
        html_parts = []
        i = 0
        while i < len(is_literal):
            if is_literal[i]:
                # 合并连续的字面量
                literal_chars = []
                while i < len(is_literal) and is_literal[i]:
                    literal_chars.append(m.group(i + 1))
                    i += 1
                html_parts.append(f'<span class="hl-literal">{"".join(literal_chars)}</span>')
            else:
                # 通配符 — 直接显示匹配内容（可能为空串）
                matched = m.group(i + 1) or ''
                html_parts.append(matched)
                i += 1

        return ''.join(html_parts)

    @staticmethod
    def _extract_summary(html: str) -> str:
        """从完整释义 HTML 中提取摘要（中文翻译+释义）

        提取两部分（如果存在）：
        - <div class="coca2">...</div>  → 翻译+百分比
        - <div class="gdc">...</div>        → 整个释义区块
        """
        parts = []
        # 提取 coca2（翻译+百分比）
        m = re.search(r'<div class="coca2">.*?</div>', html)
        if m:
            parts.append(m.group(0))
        # 提取 gdc 释义区块（匹配到 </div></div> 闭合）
        m = re.search(r'<div class="gdc">.*?</div>\s*</div>', html, re.DOTALL)
        if m:
            parts.append(m.group(0))
        return ''.join(parts) if parts else ''

    def _pattern_search_mdx(self, pattern: str, max_results: int = PATTERN_MAX_TOTAL):
        """纯在 MDX 词典中搜索匹配单词（无词频排序）"""
        regex = self._pattern_to_regex(pattern)
        results = []
        for i, w in enumerate(self.lower_words):
            if regex.match(w):
                orig = self.key_list[i][1].decode("utf-8", errors="ignore").strip()
                results.append(orig)
                if len(results) >= max_results:
                    break
        return results

    def _get_mdx_word(self, lower_word: str) -> str | None:
        """将小写单词映射到 MDX 中的原始大小写形式

        使用 lower_to_orig 字典进行 O(1) 查找。
        注意：lower_words 是按 MDX 记录顺序排列的（不是字母序），
        所以不能用 bisect 做精确查找——这是之前 bug 的根因。
        """
        return self.lower_to_orig.get(lower_word)

    def pattern_search_ranked(self, pattern: str):
        """带词频排序的模式搜索

        直接在 COCA 词频列表中搜索（天然按词频排序），
        将结果映射到 MDX 原始大小写后返回。
        返回 (ranked_words, unranked_words, total_count)
        ranked_words 和 unranked_words 均为 MDX 中的原始大小写形式
        （unranked 始终为空，不使用全量 MDX 补词以避免性能问题）。
        """
        coca_results = word_freq.search(pattern, max_results=PATTERN_MAX_TOTAL)

        # 将 COCA 小写词映射为 MDX 原始大小写
        ranked_in_mdx = []
        for w in coca_results:
            mdx_word = self._get_mdx_word(w)
            if mdx_word:
                ranked_in_mdx.append(mdx_word)

        ranked_out = ranked_in_mdx[:PATTERN_MAX_TOTAL]
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

        word_lower = word.lower()

        # 通配符模式：包含 * 或 . 时直接跳过精确匹配，做正则搜索
        if self._has_pattern(word):
            ranked, unranked, total = self.pattern_search_ranked(word)
            return (ranked, unranked, total), False

        # 精确查找：尝试各种变体
        candidates = [word, word_lower, word + "\r\n", word_lower + "\r\n"]
        for c in candidates:
            idx = self.word_to_idx.get(c)
            if idx is not None:
                html = self._read_record(idx)
                return html, True

        # 前缀匹配
        suggestions = []
        start = bisect.bisect_left(self.lower_words, word_lower)
        for i in range(start, min(start + 20, len(self.lower_words))):
            w = self.lower_words[i]
            if w == word_lower:
                continue
            if w.startswith(word_lower):
                orig = self.key_list[i][1].decode("utf-8", errors="ignore").strip()
                suggestions.append(orig)
            else:
                if suggestions:
                    break
            if len(suggestions) >= 10:
                break

        return suggestions, False


print("正在加载词典...")
mdx_reader = MDXReader(MDX_PATH)
print("[OK] 词典加载完成，服务器就绪！")

print("正在加载词根词缀数据...")
affix_loader = AffixLoader()
print(f"[OK] 词根词缀加载完成：{len(affix_loader.prefixes)} 个前缀，{len(affix_loader.suffixes)} 个后缀")

print("正在加载 COCA 词频数据...")
word_freq = WordFreq(COCA_PATH)
print("[OK] 词频数据加载完成")


def is_valid_word(word: str) -> bool:
    """判断单词是否在词典中存在（用于词根词缀分析的词干验证）"""
    if len(word) < 2:
        return False
    result, exact = mdx_reader.lookup(word)
    return exact


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/lookup")
async def lookup(request: Request, word: str = Query(..., description="单词"), page: int = Query(1, ge=1, description="页码"), back_word: str = Query(None, description="返回搜索词"), back_page: int = Query(1, description="返回页码")):
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    result, exact = mdx_reader.lookup(word)

    if exact:
        # 精确匹配时，同时进行词根词缀分析
        analysis = affix_loader.analyze(word, is_valid_word=is_valid_word)
        affix_html = None
        if analysis and (analysis["prefix"] or analysis["suffix"]):
            # 查询词干的词典释义
            stem_result, stem_exact = mdx_reader.lookup(analysis["final_stem"])
            stem_lookup_html = stem_result if stem_exact else None
            # 用 Jinja2 直接渲染片段模板为字符串
            affix_template = templates.env.get_template("partials/_affix_result.html")
            affix_html = affix_template.render(
                prefix=analysis["prefix"],
                suffix=analysis["suffix"],
                stem=analysis["stem"],
                final_stem=analysis["final_stem"],
                stem_lookup_result=stem_lookup_html,
            )

        # 将词根词缀分析结果附加到查词结果后面
        combined = result + (affix_html or "")

        return templates.TemplateResponse(
            request, "partials/_lookup_result.html",
            {"content": combined, "back_word": back_word, "back_page": back_page}
        )

    # 模式搜索（包含 * 或 .）
    if MDXReader._has_pattern(word):
        # result 是 (ranked, unranked, total) 元组
        if result:
            ranked, unranked, total = result
        else:
            ranked, unranked, total = [], [], 0

        # 计算总页数
        total_pages = max(1, (total + PATTERN_PAGE_SIZE - 1) // PATTERN_PAGE_SIZE)
        page = min(page, total_pages)

        # 将 ranked 和 unranked 合并为完整列表，再截取当前页的单词
        all_words = ranked + unranked
        start_idx = (page - 1) * PATTERN_PAGE_SIZE
        page_words = all_words[start_idx:start_idx + PATTERN_PAGE_SIZE]

        # 读取当前页单词的释义（只提取摘要）
        page_results = []
        for w in page_words:
            html, _ = mdx_reader.lookup(w)
            highlighted = MDXReader._pattern_highlight(word, w)
            rank = word_freq.get_rank(w)
            if html:
                summary = MDXReader._extract_summary(html)
                page_results.append({"word": w, "highlighted_word": highlighted, "summary": summary, "has_full": True, "rank": rank})
            else:
                page_results.append({"word": w, "highlighted_word": highlighted, "summary": "", "has_full": False, "rank": rank})

        # 确定当前页中哪些是 ranked 的
        ranked_count = len(ranked)
        page_ranked_count = max(0, min(PATTERN_PAGE_SIZE, ranked_count - start_idx))

        return templates.TemplateResponse(
            request, "partials/_pattern_results.html",
            {
                "word": word,
                "results": page_results,
                "page": page,
                "total_pages": total_pages,
                "total_count": total,
                "page_ranked_count": page_ranked_count,
            }
        )

    # 普通单词：前缀建议
    if result:
        return templates.TemplateResponse(
            request, "partials/_suggestions.html",
            {"word": word, "suggestions": result, "pattern_mode": False}
        )

    return templates.TemplateResponse(
        request, "partials/_suggestions.html",
        {"word": word, "suggestions": [], "pattern_mode": False}
    )


@app.get("/api/lookup_expand")
async def lookup_expand(request: Request, word: str = Query(..., description="单词")):
    """展开某个单词的完整释义（用于模式搜索的点击展开）"""
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    html, exact = mdx_reader.lookup(word)
    if exact and html:
        # 同时进行词根词缀分析
        analysis = affix_loader.analyze(word, is_valid_word=is_valid_word)
        affix_html = None
        if analysis and (analysis["prefix"] or analysis["suffix"]):
            stem_result, stem_exact = mdx_reader.lookup(analysis["final_stem"])
            stem_lookup_html = stem_result if stem_exact else None
            affix_template = templates.env.get_template("partials/_affix_result.html")
            affix_html = affix_template.render(
                prefix=analysis["prefix"],
                suffix=analysis["suffix"],
                stem=analysis["stem"],
                final_stem=analysis["final_stem"],
                stem_lookup_result=stem_lookup_html,
            )
        combined = html + (affix_html or "")
        return templates.TemplateResponse(
            request, "partials/_lookup_result.html",
            {"content": combined}
        )

    return templates.TemplateResponse(
        request, "partials/_suggestions.html",
        {"word": word, "suggestions": [], "pattern_mode": False}
    )



@app.get("/static/p.css")
async def get_css():
    """从词典目录提供 p.css（MDX 词典自带的样式）"""
    if os.path.exists(CSS_PATH):
        return FileResponse(CSS_PATH, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")


@app.get("/static/{file_path:path}")
async def get_static_file(file_path: str):
    """通用静态文件服务路由（favicon、style.css 等）"""
    # 安全检查：防止目录穿越攻击
    file_full_path = os.path.normpath(os.path.join(STATIC_DIR, file_path))
    if not file_full_path.startswith(os.path.normpath(STATIC_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if os.path.exists(file_full_path) and os.path.isfile(file_full_path):
        return FileResponse(file_full_path)
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
