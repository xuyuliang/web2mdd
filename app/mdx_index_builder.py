"""
MDX 索引构建器 - 将 MDX 词典的索引数据导出到 SQLite 数据库

使用方式：
    python -m app.mdx_index_builder path/to/TLD.mdx

构建完成后，应用可以从 SQLite 数据库查询索引，而不需要全部加载到内存。
"""
import os
import sys
import sqlite3
import time
import types

# ⚠️ 注入假的 lzo stub（TLD.mdx 使用 zlib 压缩，不会真正调用 lzo）
_lzo_stub = types.ModuleType("lzo")
def _lzo_decompress(data, initSize=None, blockSize=None):
    raise RuntimeError("lzo decompress called unexpectedly - this MDX uses zlib")
_lzo_stub.decompress = _lzo_decompress
sys.modules["lzo"] = _lzo_stub

from readmdict import MDX


def build_index(mdx_path: str, db_path: str, overwrite: bool = False):
    """
    构建 MDX 索引的 SQLite 数据库
    
    Args:
        mdx_path: MDX 文件路径
        db_path: SQLite 数据库路径
        overwrite: 是否覆盖已存在的数据库
    """
    # 如果数据库已存在且不覆盖，直接返回
    if os.path.exists(db_path) and not overwrite:
        print(f"[INDEX] 数据库已存在: {db_path}")
        print(f"[INDEX] 使用 --overwrite 参数强制重建")
        return db_path
    
    if os.path.exists(db_path):
        print(f"[INDEX] 删除旧数据库: {db_path}")
        os.remove(db_path)
    
    print(f"[INDEX] 正在解析 MDX 文件: {mdx_path}")
    t0 = time.time()
    
    # 加载 MDX 文件（只读取索引，不读取释义内容）
    mdx = MDX(mdx_path, substyle=True)
    raw_key_list = mdx._key_list  # [(offset, key_bytes), ...]
    
    print(f"[INDEX] 共 {len(raw_key_list)} 个词条，正在构建 SQLite 数据库...")
    
    # 创建 SQLite 数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute("""
        CREATE TABLE word_index (
            rowid INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            word_lower TEXT NOT NULL,
            key_offset INTEGER NOT NULL,
            key_length INTEGER NOT NULL,
            record_offset INTEGER NOT NULL,
            record_length INTEGER NOT NULL
        )
    """)
    
    # 创建索引
    cursor.execute("CREATE INDEX idx_word_lower ON word_index(word_lower)")
    cursor.execute("CREATE INDEX idx_word ON word_index(word)")
    
    # 插入数据
    batch_size = 10000
    batch = []
    count = 0
    
    for i, (off, key_bytes) in enumerate(raw_key_list):
        word = key_bytes.decode("utf-8", errors="ignore").strip()
        word_lower = word.lower()
        
        # record_offset 和 record_length 需要从 MDX 对象获取
        # 这里简化处理，实际使用时需要从 MDX 文件读取
        batch.append((i, word, word_lower, off, len(key_bytes), 0, 0))
        count += 1
        
        if len(batch) >= batch_size:
            cursor.executemany(
                "INSERT INTO word_index (rowid, word, word_lower, key_offset, key_length, record_offset, record_length) VALUES (?, ?, ?, ?, ?, ?, ?)",
                batch
            )
            batch = []
            if count % 100000 == 0:
                print(f"[INDEX] 已插入 {count} 条记录...")
    
    # 插入剩余数据
    if batch:
        cursor.executemany(
            "INSERT INTO word_index (rowid, word, word_lower, key_offset, key_length, record_offset, record_length) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch
        )
    
    conn.commit()
    conn.close()
    
    elapsed = time.time() - t0
    print(f"[INDEX] 索引构建完成: {count} 条记录, 耗时 {elapsed:.1f}s")
    print(f"[INDEX] 数据库路径: {db_path}")
    
    return db_path


def main():
    if len(sys.argv) < 3:
        print("用法: python -m app.mdx_index_builder <mdx路径> [db路径] [--overwrite]")
        print()
        print("示例:")
        print("  python -m app.mdx_index_builder F:/data/TLD.mdx F:/data/TLD.index.db")
        print("  python -m app.mdx_index_builder F:/data/TLD.mdx F:/data/TLD.index.db --overwrite")
        sys.exit(1)
    
    mdx_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else mdx_path + ".index.db"
    overwrite = "--overwrite" in sys.argv
    
    if not os.path.exists(mdx_path):
        print(f"[ERROR] 文件不存在: {mdx_path}")
        sys.exit(1)
    
    build_index(mdx_path, db_path, overwrite)


if __name__ == "__main__":
    main()