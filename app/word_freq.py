"""
词频工具 - 从 SQLite 数据库读取 COCA 词频数据，提供按词频排序的模式匹配搜索
"""
import re
import os
import sqlite3


class WordFreq:
    """COCA 词频工具 - 从 TLD.mdx.index.db 的 coca_words 表读取数据"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        # 缓存：存储所有小写单词集合，用于快速判断单词是否存在
        # 使用子查询去重，取每个单词的最小 frequency（优先级最高）
        self.cursor.execute("""
            SELECT LOWER(word), MIN(frequency) 
            FROM coca_words 
            GROUP BY LOWER(word)
        """)
        self.word_set: set[str] = {row[0] for row in self.cursor.fetchall()}
        print(f"[WordFreq] 已从数据库加载 {len(self.word_set)} 个唯一词条")

    def __del__(self):
        """析构时关闭数据库连接"""
        if hasattr(self, 'conn'):
            try:
                self.conn.close()
            except Exception:
                pass

    def get_rank(self, word: str) -> int | None:
        """获取单词的 COCA 词频值（frequency），不在词频表中返回 None"""
        self.cursor.execute(
            "SELECT MIN(frequency) FROM coca_words WHERE LOWER(word) = ?", (word.lower(),)
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def search(self, pattern: str, max_results: int = 50) -> list[str]:
        """在词频数据库中搜索匹配的单词（按 frequency 升序，即最常用的在前）

        使用 SQL LIKE 进行原生模式匹配，大幅提升搜索速度。
        返回小写词列表，至多 max_results 个（已去重）。
        """
        # 将用户的通配符模式转换为 SQL LIKE 模式
        like_pattern = self._pattern_to_like(pattern)
        
        if like_pattern is None:
            # 没有通配符，精确匹配
            self.cursor.execute("""
                SELECT DISTINCT LOWER(word) FROM coca_words 
                WHERE LOWER(word) = ?
                ORDER BY frequency ASC
                LIMIT ?
            """, (pattern.strip().lower(), max_results))
        else:
            # 有通配符，使用 LIKE 查询
            self.cursor.execute("""
                SELECT DISTINCT LOWER(word) FROM coca_words 
                WHERE LOWER(word) LIKE ? ESCAPE '\\'
                ORDER BY frequency ASC
                LIMIT ?
            """, (like_pattern, max_results))
        
        return [row[0] for row in self.cursor.fetchall()]

    @staticmethod
    def _pattern_to_like(pattern: str) -> str | None:
        """将通配符模式 (* 和 .) 转换为 SQL LIKE 模式
        
        - * → % (匹配任意字符序列)
        - . → _ (匹配单个字符)
        - 其他字符需要转义 LIKE 特殊字符 (% _ \)
        
        返回 LIKE 模式字符串，如果没有通配符则返回 None。
        """
        has_wildcard = False
        parts = []
        
        for c in pattern:
            if c == '*':
                parts.append('%')
                has_wildcard = True
            elif c == '.':
                parts.append('_')
                has_wildcard = True
            elif c in ('%', '_', '\\'):
                # 转义 SQL LIKE 的特殊字符
                parts.append(f'\\{c}')
            else:
                parts.append(c.lower())
        
        return ''.join(parts) if has_wildcard else None