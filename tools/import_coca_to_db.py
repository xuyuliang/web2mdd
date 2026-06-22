"""
将 oldCOCA60000.txt 导入到 The Little dict 的 SQLite 数据库中
（数据已存储在 TLD.mdx.index.db 的 coca_words 表中）
"""
import sqlite3
import os

# 路径设置
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "The little dict", "TLD.mdx.index.db")
TXT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "数据资料", "oldCOCA60000.txt")

def main():
    print(f"数据库路径: {DB_PATH}")
    print(f"文本路径: {TXT_PATH}")
    
    # 检查文件是否存在
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        return
    if not os.path.exists(TXT_PATH):
        print(f"错误: 文本文件不存在: {TXT_PATH}")
        return
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 先查看现有表结构
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = [t[0] for t in cursor.fetchall()]
    print(f"现有表: {tables}")
    
    # 创建 COCA 单词表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coca_words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            frequency INTEGER NOT NULL
        )
    """)
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_coca_word ON coca_words(word)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_coca_frequency ON coca_words(frequency)')
    
    # 读取并插入数据
    count = 0
    batch = []
    batch_size = 5000
    
    with open(TXT_PATH, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            word = line.strip()
            if not word:
                continue
            # 格式: 每行只是一个单词，如 'the', 'be' 等
            batch.append((line_num, word, line_num))
            count += 1

            if len(batch) >= batch_size:
                cursor.executemany(
                    'INSERT OR REPLACE INTO coca_words (id, word, frequency) VALUES (?, ?, ?)',
                    batch
                )
                batch = []
                print(f"  已插入 {count} 条记录...")
    
    # 插入剩余数据
    if batch:
        cursor.executemany(
            'INSERT OR REPLACE INTO coca_words (id, word, frequency) VALUES (?, ?, ?)',
            batch
        )
    
    conn.commit()
    conn.close()
    
    print(f"\n成功! 共导入 {count} 条 COCA 单词到数据库")
    print(f"数据库文件: {DB_PATH}")
    print(f"原始文本文件保持不变: {TXT_PATH}")

if __name__ == "__main__":
    main()