"""
查词拆词 - 基于 FastAPI + htmx 的 TLD 词典查询网站
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from readmdict import MDX
import os
import bisect
from readmdict import lzo
import zlib
import time
import pickle
import re

from app.affix_loader import AffixLoader

app = FastAPI()

# __file__ 现在是 web2mdd/app/main.py，需上移两级到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE_DIR, "The little dict")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
CSS_PATH = os.path.join(DICT_DIR, "p.css")
CACHE_PATH = MDX_PATH + ".pkl"  # 缓存文件路径

templates = Jinja2Templates(directory=TEMPLATES_DIR)


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

    def lookup(self, word):
        """查找单词，返回 (结果, 是否精确匹配)"""
        word = word.strip()
        if not word:
            return None, False

        word_lower = word.lower()

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
                # 恢复原始大小写的显示
                orig = self.key_list[i][1].decode("utf-8", errors="ignore").strip()
                suggestions.append(orig)
            else:
                if suggestions:
                    break
            if len(suggestions) >= 10:
                break

        return suggestions, False

    def get_rank(self, word):
        """获取单词的词频（取所有 RANK 中的最小值）"""
        result, exact = self.lookup(word)
        if not exact or not result:
            return None
        ranks = re.findall(r'<span class="rank">(\d+)</span>', result)
        if ranks:
            return min(int(r) for r in ranks)
        return None


print("正在加载词典...")
mdx_reader = MDXReader(MDX_PATH)
print("[OK] 词典加载完成，服务器就绪！")

print("正在加载词根词缀数据...")
affix_loader = AffixLoader()
print(f"[OK] 词根词缀加载完成：{len(affix_loader.prefixes)} 个前缀，{len(affix_loader.suffixes)} 个后缀")


def is_valid_word(word: str) -> bool:
    """判断单词是否在词典中存在（用于词根词缀分析的词干验证）"""
    if len(word) < 2:
        return False
    result, exact = mdx_reader.lookup(word)
    return exact


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/lookup")
async def lookup(request: Request, word: str = Query(..., description="单词")):
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
            "partials/_lookup_result.html",
            {"request": request, "content": combined}
        )

    if result:
        return templates.TemplateResponse(
            "partials/_suggestions.html",
            {"request": request, "word": word, "suggestions": result}
        )

    return templates.TemplateResponse(
        "partials/_suggestions.html",
        {"request": request, "word": word, "suggestions": []}
    )


@app.get("/api/rank")
async def rank(word: str = Query(..., description="单词")):
    """获取单词的词频（取所有 RANK 中的最小值）"""
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    rank_val = mdx_reader.get_rank(word)

    if rank_val is not None:
        return {"word": word.strip(), "rank": rank_val, "found": True}
    else:
        # 检查是否是完全没找到 vs 找到了但没有 rank 字段
        result, exact = mdx_reader.lookup(word)
        if exact:
            return {"word": word.strip(), "rank": None, "found": True}
        return {"word": word.strip(), "rank": None, "found": False}


@app.get("/static/p.css")
async def get_css():
    if os.path.exists(CSS_PATH):
        return FileResponse(CSS_PATH, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")


@app.get("/static/style.css")
async def get_style_css():
    path = os.path.join(STATIC_DIR, "style.css")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
