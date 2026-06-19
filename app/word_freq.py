"""
词频工具 - 加载 COCA 词频列表，提供按词频排序的模式匹配搜索
"""
import re
import os


class WordFreq:
    """COCA 词频列表，按频率降序排列（最常用词在前）"""

    def __init__(self, filepath: str):
        self.words: list[str] = []
        self.rank_map: dict[str, int] = {}
        seen: set[str] = set()
        with open(filepath, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                w = line.strip().lower()
                if w and w not in seen:
                    seen.add(w)
                    self.words.append(w)
                    self.rank_map[w] = line_no
        self.word_set = seen
        print(f"[WordFreq] 已加载 {len(self.words)} 个词频词条")

    def get_rank(self, word: str) -> int | None:
        """获取单词的 COCA 词频排名（1-based），不在词频表中返回 None"""
        return self.rank_map.get(word.lower())

    def search(self, pattern: str, max_results: int = 50):
        """在词频列表中搜索匹配的单词（天然按频率排序）

        返回 (ranked_lower: list[str]) — 已经按词频排序好的小写词列表，
        至多 max_results 个。
        """
        regex = self._compile_pattern(pattern)
        results: list[str] = []
        for w in self.words:
            if regex.match(w):
                results.append(w)
                if len(results) >= max_results:
                    break
        return results

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern:
        """将用户的简单通配符 (* → .*, . → .) 转成正则"""
        parts = []
        for c in pattern:
            if c == "*":
                parts.append(".*")
            elif c == ".":
                parts.append(".")
            else:
                parts.append(re.escape(c))
        return re.compile("^" + "".join(parts) + "$", re.IGNORECASE)
