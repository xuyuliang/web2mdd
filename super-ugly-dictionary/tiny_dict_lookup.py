"""
超级简陋小词典 - 词典查询模块

封装词典查询功能，提供统一的查询入口
"""

import os
import sys

# 添加父目录到路径，以便导入 MDX 相关模块
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app.mdx_sqlite_reader import MDXSQLiteReader


class TinyDictLookup:
    """词典查询类"""
    
    # 词典路径 - 相对于 super-ugly-dictionary 目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DICT_DIR = os.path.join(BASE_DIR, "The little dict")
    MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
    DB_PATH = os.path.join(DICT_DIR, "TLD.mdx.index.db")
    
    _instance = None
    _reader = None
    
    def __new__(cls):
        """单例模式 - 只有一个词典阅读器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_reader()
        return cls._instance
    
    def _init_reader(self):
        """初始化词典阅读器"""
        if self._reader is None:
            self._reader = MDXSQLiteReader(self.MDX_PATH, self.DB_PATH)
    
    def lookup(self, word: str) -> str | None:
        """
        查询单词，返回 HTML 内容
        
        Args:
            word: 要查询的单词
            
        Returns:
            HTML 内容字符串，或 None（未找到时）
        """
        if not word or not word.strip():
            return None
        
        word = word.strip()
        
        # 尝试精确匹配（大小写敏感）
        html, exact = self._reader.lookup(word)
        
        if exact and html:
            return html
        
        # 尝试小写匹配
        html, exact = self._reader.lookup(word.lower())
        
        if exact and html:
            return html
        
        return None
    
    def close(self):
        """关闭词典阅读器"""
        if self._reader:
            self._reader.close()
            self._reader = None


# 全局查询函数
def lookup_word(word: str) -> str | None:
    """
    查询单词，返回 HTML 内容
    
    Args:
        word: 要查询的单词
        
    Returns:
        HTML 内容字符串，或 None（未找到时）
    """
    lookup = TinyDictLookup()
    return lookup.lookup(word)


if __name__ == "__main__":
    # 简单测试
    result = lookup_word("apple")
    if result:
        print(f"Found 'apple', HTML length: {len(result)}")
        # 显示部分内容
        print(result[:500])
    else:
        print("Not found")