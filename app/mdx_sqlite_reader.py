"""
MDX SQLite Reader - 使用 SQLite 缓存索引的 MDX 阅读器

内存占用极低，索引数据存储在 SQLite 数据库中，只在查询时读取需要的行。

使用方式：
    reader = MDXSQLiteReader(mdx_path, db_path)
    result = reader.lookup("hello")
"""
import os
import sys
import sqlite3
import bisect
import zlib
import re
import time
import types

# ⚠️ 注入假的 lzo stub
_lzo_stub = types.ModuleType("lzo")
def _lzo_decompress(data, initSize=None, blockSize=None):
    raise RuntimeError("lzo decompress called unexpectedly")
_lzo_stub.decompress = _lzo_decompress
sys.modules["lzo"] = _lzo_stub

from readmdict import MDX


class MDXSQLiteReader:
    """使用 SQLite 缓存索引的 MDX 阅读器"""
    
    def __init__(self, mdx_path: str, db_path: str = None, build_if_not_exists: bool = True):
        """
        初始化阅读器
        
        Args:
            mdx_path: MDX 文件路径
            db_path: SQLite 数据库路径，默认为 mdx_path + ".index.db"
            build_if_not_exists: 如果数据库不存在，是否自动构建
        """
        self.path = mdx_path
        
        if db_path is None:
            db_path = mdx_path + ".index.db"
        self.db_path = db_path
        
        self._stylesheet = None
        self._substyle = False
        self.encoding = "utf-8"
        self._record_block_offset = 0
        self._block_infos = []
        self._block_starts = []
        self._data_offset = 0
        
        # 连接数据库（必须先连接才能加载元数据）
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # 如果数据库不存在且需要构建，则构建索引
        if not os.path.exists(db_path):
            if build_if_not_exists:
                print(f"[MDX-SQLite] 数据库不存在，正在构建索引...")
                self._build_index()
            else:
                raise FileNotFoundError(f"索引数据库不存在: {db_path}")
        else:
            # 从 SQLite 数据库读取块信息（用于记录解压）
            print(f"[MDX-SQLite] 从数据库读取块信息...")
            self._load_block_info_from_mdx()
        
        print(f"[MDX-SQLite] 已连接索引数据库: {db_path}")
    
    def _build_index(self):
        """从 MDX 文件构建 SQLite 索引"""
        t0 = time.time()
        
        # 加载 MDX 文件
        mdx = MDX(self.path, substyle=True)
        raw_key_list = mdx._key_list
        
        self._stylesheet = mdx._stylesheet
        self._substyle = mdx._substyle
        self.encoding = mdx._encoding
        self._record_block_offset = mdx._record_block_offset
        
        # 读取块信息
        self._load_block_info(mdx)
        
        print(f"[MDX-SQLite] 共 {len(raw_key_list)} 个词条，正在构建数据库...")
        
        # 创建数据库表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 存储 MDX 元数据
        import json
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mdx_meta (
                id INTEGER PRIMARY KEY,
                encoding TEXT,
                substyle INTEGER,
                data_offset INTEGER,
                block_infos TEXT,
                stylesheet TEXT
            )
        """)
        
        # 插入元数据
        block_infos_json = json.dumps(self._block_infos)
        stylesheet_json = json.dumps(dict(self._stylesheet)) if self._stylesheet else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO mdx_meta (id, encoding, substyle, data_offset, block_infos, stylesheet)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (self.encoding, 1 if self._substyle else 0, self._data_offset, block_infos_json, stylesheet_json))
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_index (
                rowid INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                word_lower TEXT NOT NULL,
                key_offset INTEGER NOT NULL,
                key_length INTEGER NOT NULL,
                record_offset INTEGER NOT NULL,
                record_length INTEGER NOT NULL
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_lower ON word_index(word_lower)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word ON word_index(word)")
        
        # 计算每条记录的偏移和长度
        key_records = self._calculate_record_offsets(raw_key_list)
        
        # 插入数据
        batch_size = 10000
        batch = []
        count = 0
        
        for i, (off, key_bytes) in enumerate(raw_key_list):
            word = key_bytes.decode("utf-8", errors="ignore").strip()
            word_lower = word.lower()
            rec_off, rec_len = key_records[i]
            batch.append((i, word, word_lower, off, len(key_bytes), rec_off, rec_len))
            count += 1
            
            if len(batch) >= batch_size:
                cursor.executemany(
                    "INSERT OR REPLACE INTO word_index (rowid, word, word_lower, key_offset, key_length, record_offset, record_length) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    batch
                )
                batch = []
                if count % 500000 == 0:
                    print(f"[MDX-SQLite] 已插入 {count} 条记录...")
        
        if batch:
            cursor.executemany(
                "INSERT OR REPLACE INTO word_index (rowid, word, word_lower, key_offset, key_length, record_offset, record_length) VALUES (?, ?, ?, ?, ?, ?, ?)",
                batch
            )
        
        conn.commit()
        conn.close()
        
        elapsed = time.time() - t0
        print(f"[MDX-SQLite] 索引构建完成: {count} 条记录, 耗时 {elapsed:.1f}s")
    
    def _load_block_info(self, mdx):
        """从 MDX 对象读取块信息"""
        f = open(self.path, "rb")
        f.seek(mdx._record_block_offset)
        num_blocks = mdx._read_number(f)
        mdx._read_number(f)  # num_entries
        mdx._read_number(f)  # info_size
        mdx._read_number(f)  # block_size
        
        self._block_infos = []
        for _ in range(num_blocks):
            comp = mdx._read_number(f)
            decomp = mdx._read_number(f)
            self._block_infos.append((comp, decomp))
        self._data_offset = f.tell()
        f.close()
        
        # 每个块在解压数据流中的起始偏移
        s = 0
        self._block_starts = []
        for comp, decomp in self._block_infos:
            self._block_starts.append(s)
            s += decomp
    
    def _load_block_info_from_mdx(self):
        """从 SQLite 数据库读取块信息（在构建索引时已存储）"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM mdx_meta LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            # 如果没有元数据，说明是旧版数据库，需要从 MDX 文件重新读取
            print("[MDX-SQLite] 数据库缺少元数据，需要从 MDX 文件重新构建索引")
            raise FileNotFoundError("请使用 --overwrite 参数重新构建索引")
        
        # 解析块信息（JSON 格式）
        import json
        block_infos_json = row["block_infos"]
        self._block_infos = json.loads(block_infos_json)
        self._data_offset = row["data_offset"]
        self.encoding = row["encoding"]
        self._substyle = bool(row["substyle"]) if row["substyle"] is not None else False
        
        # 加载样式表
        if row["stylesheet"]:
            self._stylesheet = json.loads(row["stylesheet"])
        else:
            self._stylesheet = None
        
        # 每个块在解压数据流中的起始偏移
        s = 0
        self._block_starts = []
        for comp, decomp in self._block_infos:
            self._block_starts.append(s)
            s += decomp
        
        print(f"[MDX-SQLite] 块信息加载完成: {len(self._block_infos)} 个块")
    
    def _calculate_record_offsets(self, raw_key_list):
        """计算每条记录的偏移和长度"""
        records = []
        for i in range(len(raw_key_list)):
            rec_off = raw_key_list[i][0]
            if i + 1 < len(raw_key_list):
                next_off = raw_key_list[i + 1][0]
            else:
                # 最后一条记录延伸到块的末尾
                bi = bisect.bisect_right(self._block_starts, rec_off) - 1
                next_off = self._block_starts[bi] + self._block_infos[bi][1]
            
            rec_len = next_off - rec_off
            records.append((rec_off, rec_len))
        return records
    
    def _decompress_block(self, idx):
        """读取并解压指定索引的记录块"""
        comp, decomp = self._block_infos[idx]
        f = open(self.path, "rb")
        f.seek(self._data_offset)
        for i in range(idx):
            f.seek(self._block_infos[i][0], 1)
        data = f.read(comp)
        f.close()
        
        bt = data[:4]
        if bt == b"\x00\x00\x00\x00":
            return data[8:]
        elif bt == b"\x01\x00\x00\x00":
            return data[8:]  # lzo stub won't be called for this MDX
        elif bt == b"\x02\x00\x00\x00":
            return zlib.decompress(data[8:])
        raise ValueError(f"未知压缩类型: {bt}")
    
    def _read_record_from_file(self, record_offset: int, record_length: int) -> str:
        """从 MDX 文件读取指定记录"""
        # 定位所属记录块
        bi = bisect.bisect_right(self._block_starts, record_offset) - 1
        if bi < 0:
            bi = 0
        
        dec = self._decompress_block(bi)
        raw = dec[record_offset - self._block_starts[bi] : record_offset - self._block_starts[bi] + record_length]
        
        # 解码
        text = raw.decode(self.encoding, errors="ignore").strip("\x00")
        
        # 样式替换
        text = self._substitute_stylesheet(text)
        
        return text
    
    def _substitute_stylesheet(self, text: str) -> str:
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
    
    def lookup(self, word: str) -> tuple:
        """
        查找单词
        
        Args:
            word: 要查找的单词
            
        Returns:
            (html_content, is_exact) 元组
        """
        word = word.strip()
        if not word:
            return None, False
        
        # 尝试精确匹配（大小写敏感）
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM word_index WHERE word = ?", (word,))
        row = cursor.fetchone()
        
        if row:
            html = self._read_record_from_file(row["record_offset"], row["record_length"])
            return html, True
        
        # 尝试小写匹配
        cursor.execute("SELECT * FROM word_index WHERE word_lower = ?", (word.lower(),))
        row = cursor.fetchone()
        
        if row:
            html = self._read_record_from_file(row["record_offset"], row["record_length"])
            return html, True
        
        return None, False
    
    def prefix_search(self, prefix: str, limit: int = 20) -> list:
        """
        前缀搜索
        
        Args:
            prefix: 前缀
            limit: 返回结果数量限制
            
        Returns:
            匹配的单词列表 [(word, record_offset, record_length), ...]
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT word, record_offset, record_length FROM word_index WHERE word_lower LIKE ? LIMIT ?",
            (prefix.lower() + "%", limit)
        )
        return [(row["word"], row["record_offset"], row["record_length"]) for row in cursor.fetchall()]
    
    def pattern_search(self, pattern: str, max_results: int = 50) -> list:
        """
        模式搜索（支持 * 和 . 通配符）
        
        Args:
            pattern: 搜索模式
            max_results: 最大结果数
            
        Returns:
            匹配的单词列表 [(word, record_offset, record_length), ...]
        """
        # 将用户模式转换为 SQL LIKE 模式
        # * → % (零个或多个字符)
        # . → _ (单个字符)
        like_pattern = pattern.replace("*", "%").replace(".", "_")
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT word, record_offset, record_length FROM word_index WHERE word_lower LIKE ? LIMIT ?",
            (like_pattern.lower(), max_results)
        )
        return [(row["word"], row["record_offset"], row["record_length"]) for row in cursor.fetchall()]
    
    def get_word_by_rowid(self, rowid: int) -> tuple:
        """
        通过 rowid 获取单词信息
        
        Returns:
            (word, record_offset, record_length) 元组
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT word, record_offset, record_length FROM word_index WHERE rowid = ?", (rowid,))
        row = cursor.fetchone()
        if row:
            return (row["word"], row["record_offset"], row["record_length"])
        return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 全局阅读器实例（延迟初始化）
_reader_instance = None


def get_reader(mdx_path: str, db_path: str = None) -> MDXSQLiteReader:
    """获取或创建全局阅读器实例"""
    global _reader_instance
    if _reader_instance is None:
        _reader_instance = MDXSQLiteReader(mdx_path, db_path)
    return _reader_instance