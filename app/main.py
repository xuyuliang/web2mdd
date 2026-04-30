"""
查词拆词 - 基于 FastAPI + htmx 的 TLD 词典查询网站
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from mdict_utils.base.readmdict import MDX, MDD
import os
import bisect
from mdict_utils.base import lzo
import zlib
import time

app = FastAPI()

# __file__ 现在是 web2mdd/app/main.py，需上移两级到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE_DIR, "The little dict")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
MDD_PATH = os.path.join(DICT_DIR, "TLD.mdd")
CSS_PATH = os.path.join(DICT_DIR, "p.css")


class MDXReader:
    """MDX 词典读取器 - 内存中建索引，按需解压读取记录"""

    def __init__(self, path):
        t0 = time.time()
        self.mdx = MDX(path, substyle=True)
        self.path = path
        self.encoding = self.mdx._encoding
        self.key_list = self.mdx._key_list  # [(offset, key_bytes)]

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
        self._load_block_info()

    def _load_block_info(self):
        f = open(self.path, "rb")
        f.seek(self.mdx._record_block_offset)
        num_blocks = self.mdx._read_number(f)
        self.mdx._read_number(f)  # num_entries
        self.mdx._read_number(f)  # info_size
        self.mdx._read_number(f)  # block_size

        self.block_infos = []
        for _ in range(num_blocks):
            comp = self.mdx._read_number(f)
            decomp = self.mdx._read_number(f)
            self.block_infos.append((comp, decomp))
        self.data_offset = f.tell()
        f.close()

        # 每个块在解压数据流中的起始偏移
        s = 0
        self.block_starts = []
        for comp, decomp in self.block_infos:
            self.block_starts.append(s)
            s += decomp

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
        if self.mdx._substyle and self.mdx._stylesheet:
            text = self.mdx._substitute_stylesheet(text)

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


class MDDReader:
    """MDD 多媒体资源读取器 - 全量缓存到内存"""

    def __init__(self, path):
        t0 = time.time()
        self.mdd = MDD(path)
        self.path = path
        # 全量加载所有资源到内存字典
        self.media_cache = {}
        for key_bytes, data in self.mdd.items():
            key = key_bytes.decode("utf-8", errors="ignore").strip().lower()
            self.media_cache[key] = data
        print(f"[MDD] 已加载 {len(self.media_cache)} 个资源到缓存, {time.time()-t0:.1f}s")

    def get_media(self, path_str):
        key = path_str.strip().lower()
        # 直接字典查找
        if key in self.media_cache:
            return self.media_cache[key]
        # 尝试替换路径分隔符
        alt = key.replace("\\", "/")
        if alt in self.media_cache:
            return self.media_cache[alt]
        alt = key.replace("/", "\\")
        if alt in self.media_cache:
            return self.media_cache[alt]
        return None



print("正在加载词典（首次约 25-30 秒）...")
mdx_reader = MDXReader(MDX_PATH)
mdd_reader = MDDReader(MDD_PATH) if os.path.exists(MDD_PATH) else None
print("[OK] 词典加载完成，服务器就绪！")


def _load_index_html():
    """从 templates/index.html 读取首页 HTML"""
    path = os.path.join(TEMPLATES_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


HOME_HTML = _load_index_html()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HOME_HTML


@app.get("/api/lookup")
async def lookup(word: str = Query(..., description="单词")):
    if not word or not word.strip():
        raise HTTPException(status_code=400, detail="请输入单词")

    result, exact = mdx_reader.lookup(word)

    if exact:
        return HTMLResponse(f'<div class="dict-content">{result}</div>')

    if result:
        suggestions = result
        links = " ".join(
            f'<a class="sug-link" onclick="document.querySelector(\'[name=word]\').value=\'{s}\'; htmx.trigger(\'[name=word]\', \'search\')">{s}</a>'
            for s in suggestions
        )
        return HTMLResponse(
            f'<div class="suggestion">未找到 "<strong>{word}</strong>"<br><br>您是不是想查：<br>{links}</div>'
        )

    return HTMLResponse(f'<div class="suggestion">未找到 "<strong>{word}</strong>"</div>')


@app.get("/api/media/{path:path}")
async def get_media(path: str):
    if not mdd_reader:
        raise HTTPException(status_code=404, detail="无多媒体资源")
    data = mdd_reader.get_media(path)
    if data is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    ext = os.path.splitext(path)[1].lower()
    ct_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".spx": "audio/speex",
        ".ogg": "audio/ogg",
    }
    return Response(content=data, media_type=ct_map.get(ext, "application/octet-stream"))


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
