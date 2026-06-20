"""
相似词搜索模块 - 搜索与词干相似的单词并打分排序

打分规则：
- 每个差异字母算1分
- 每个完整的前缀/后缀/常见字母组合整体算1分（不管长度）
- 同分按词频排序
"""
import re
import json
import os
from app.word_freq import WordFreq
from app.affix_loader import AffixLoader


class RelatedWordsSearcher:
    """相似词搜索和打分"""

    def __init__(self, coca_path: str, data_dir: str):
        """
        初始化搜索器
        
        Args:
            coca_path: COCA60000.txt 文件路径
            data_dir: 数据资料目录路径
        """
        self.data_dir = data_dir
        
        # 加载词频数据
        self.word_freq = WordFreq(coca_path)
        self.coca_word_set = self.word_freq.word_set
        
        # 加载前缀和后缀
        self.affix_loader = AffixLoader()
        
        # 加载常见字母组合
        self.common_combos = self._load_common_combos()
        
        # 编译前缀和后缀的正则（去除 - 符号）
        self.prefixes_clean = [p.lower().rstrip("-") for p in self.affix_loader.prefixes]
        self.suffixes_clean = [s.lower().lstrip("-") for s in self.affix_loader.suffixes]
        
        # 按长度降序排序，优先匹配长的
        self.prefixes_clean.sort(key=len, reverse=True)
        self.suffixes_clean.sort(key=len, reverse=True)

    def _load_common_combos(self) -> list[str]:
        """加载常见字母组合"""
        combo_path = os.path.join(self.data_dir, "常见字母组合.json")
        if not os.path.exists(combo_path):
            return []
        
        try:
            with open(combo_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            combos = []
            for pattern in data.get("patterns", []):
                regex_str = pattern.get("regex", "")
                if regex_str:
                    try:
                        combos.append((re.compile(regex_str, re.IGNORECASE), pattern.get("name", "")))
                    except re.error:
                        pass
            return combos
        except Exception:
            return []

    def calculate_score(self, stem: str, word: str) -> int:
        """
        计算词干与单词的相似度分数
        
        分数越低越相似。
        
        打分规则：
        - 每个差异字母算1分
        - 如果发现完整的前缀/后缀/常见字母组合，整体只算1分
        
        Args:
            stem: 词干
            word: 候选单词
            
        Returns:
            分数（越低越相似）
        """
        stem = stem.lower()
        word = word.lower()
        
        if stem == word:
            return 0
        
        # 找出差异部分
        diff_parts = self._find_diff_parts(stem, word)
        
        if not diff_parts:
            return float('inf')  # 没有关联，不相似
        
        # 对差异部分打分
        total_score = 0
        for part in diff_parts:
            total_score += self._score_part(part)
        
        return total_score

    def _find_diff_parts(self, stem: str, word: str) -> list[str]:
        """
        找出词干与单词之间的差异部分
        
        Returns:
            差异部分列表
        """
        # 检查 word 是否包含 stem
        stem_pos = word.find(stem)
        if stem_pos >= 0:
            parts = []
            if stem_pos > 0:
                parts.append(word[:stem_pos])  # 前缀差异
            if stem_pos + len(stem) < len(word):
                parts.append(word[stem_pos + len(stem):])  # 后缀差异
            return parts
        
        # 检查 stem 是否包含 word
        word_pos = stem.find(word)
        if word_pos >= 0:
            parts = []
            if word_pos > 0:
                parts.append(stem[:word_pos])  # 前缀差异
            if word_pos + len(word) < len(stem):
                parts.append(stem[word_pos + len(word):])  # 后缀差异
            return parts
        
        # 使用编辑距离找出差异（简化处理：返回两个词的不重叠部分）
        return self._edit_distance_diff(stem, word)

    def _edit_distance_diff(self, stem: str, word: str) -> list[str]:
        """
        通过编辑距离找出差异部分（简化版）
        """
        # 使用动态规划计算编辑距离，并回溯差异
        m, n = len(stem), len(word)
        
        # 构建编辑距离矩阵
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if stem[i-1] == word[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        # 回溯找出不匹配的字符
        diffs = []
        i, j = m, n
        while i > 0 or j > 0:
            if i > 0 and j > 0 and stem[i-1] == word[j-1]:
                i -= 1
                j -= 1
            elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
                diffs.append(stem[i-1])
                diffs.append(word[j-1])
                i -= 1
                j -= 1
            elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
                diffs.append(stem[i-1])
                i -= 1
            elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
                diffs.append(word[j-1])
                j -= 1
            else:
                break
        
        return diffs if diffs else ["unknown"]

    def _score_part(self, part: str) -> int:
        """
        对差异部分打分
        
        - 如果部分是空字符串，0分
        - 如果能匹配已知前缀/后缀/常见字母组合，整体只算1分
        - 如果不能直接匹配，尝试拆分为多个已知后缀/前缀组合
        - 否则，每个字母1分
        """
        if not part:
            return 0
        
        part_lower = part.lower()
        
        # 检查是否是已知前缀
        for p in self.prefixes_clean:
            if p and part_lower == p:
                return 1
        
        # 检查是否是已知后缀
        for s in self.suffixes_clean:
            if s and part_lower == s:
                return 1
        
        # 检查是否是常见字母组合
        for regex, name in self.common_combos:
            if regex.search(part_lower):
                return 1
        
        # 尝试拆分：从右向左匹配后缀（因为是后缀，优先匹配右边的）
        suffix_score = self._score_with_splitting(part_lower, self.suffixes_clean, is_prefix=False)
        
        # 尝试拆分：从左向右匹配前缀
        prefix_score = self._score_with_splitting(part_lower, self.prefixes_clean, is_prefix=True)
        
        # 取较小值
        split_score = min(suffix_score, prefix_score)
        
        # 如果拆分后比逐字母打分更优，使用拆分结果
        if split_score < len(part_lower):
            return split_score
        
        # 否则，每个字母1分
        return len(part)
    
    def _score_with_splitting(self, text: str, known_items: list[str], is_prefix: bool = False) -> int:
        """
        使用动态规划将文本拆分为已知项的组合，计算最低分数
        
        允许部分字符无法匹配已知项，未匹配的每个字符计1分。
        匹配到的已知项每个计1分（不管长度）。
        
        Args:
            text: 待打分的文本
            known_items: 已知前缀/后缀列表（已按长度降序排序）
            
        Returns:
            最低分数
        """
        n = len(text)
        if n == 0:
            return 0
        
        # dp[i] = 将 text[0:i] 拆分的最小分数
        # 允许跳过未匹配的字符，每个计1分
        dp = list(range(n + 1))  # 初始：每个字符都未匹配，i分
        
        # 从左到右扫描
        for i in range(1, n + 1):
            # 选项1：当前字符未匹配，继承 dp[i-1] + 1
            dp[i] = min(dp[i], dp[i - 1] + 1)
            
            # 选项2：尝试匹配所有已知项，以位置i结尾
            for item in known_items:
                if not item:
                    continue
                item_len = len(item)
                if i >= item_len and text[i - item_len:i] == item:
                    # 匹配成功，尝试更新
                    if dp[i] > dp[i - item_len] + 1:
                        dp[i] = dp[i - item_len] + 1
        
        return dp[n]

    def search_and_score(self, stem: str, max_results: int = 50) -> list[dict]:
        """
        搜索与词干相似的单词并打分排序
        
        Args:
            stem: 词干
            max_results: 最大返回结果数
            
        Returns:
            结果列表，每个元素包含:
            - word: 单词
            - score: 分数
            - rank: 词频排名
            - breakdown: 分数详情
        """
        stem = stem.strip().lower()
        if not stem:
            return []
        
        # 使用 *stem* 正则搜索
        regex_pattern = f"*{stem}*"
        matching_words = self.word_freq.search(regex_pattern, max_results=max_results * 3)
        
        # 对每个匹配词打分
        scored_results = []
        for word in matching_words:
            if word == stem:
                continue  # 跳过词干本身
            
            score = self.calculate_score(stem, word)
            if score == float('inf'):
                continue
            
            rank = self.word_freq.get_rank(word)
            
            scored_results.append({
                "word": word,
                "score": score,
                "rank": rank,
            })
        
        # 按分数升序（越低越相似），同分按词频排名升序
        scored_results.sort(key=lambda x: (x["score"], x["rank"] if x["rank"] else float('inf')))
        
        return scored_results[:max_results]
    
    def highlight_word(self, stem: str, word: str) -> str:
        """
        将单词分块并用 "." 连接显示
        
        例如：stem='situ', word='situational' → 'situ.ation.al'
        
        分块规则：
        1. 词干部分作为第一块
        2. 前缀/后缀/常见字母组合各自为一块
        3. 剩余未识别的单字符或多字符各为一块
        
        Args:
            stem: 词干
            word: 完整单词
            
        Returns:
            用 "." 连接的块字符串
        """
        stem = stem.lower()
        word_lower = word.lower()
        
        # 找出 word 相对于 stem 的前缀、词干、后缀
        stem_pos = word_lower.find(stem)
        
        if stem_pos >= 0:
            # word = 前缀 + stem + 后缀
            prefix_part = word_lower[:stem_pos] if stem_pos > 0 else ""
            suffix_part = word_lower[stem_pos + len(stem):] if stem_pos + len(stem) < len(word_lower) else ""
            
            blocks = []
            # 前缀部分：从左向右匹配，只使用 prefixes_clean
            if prefix_part:
                blocks.extend(self._match_text(prefix_part, self.prefixes_clean, forward=True))
            blocks.append(stem)  # 词干本身是一块
            # 后缀部分：从右向左匹配，只使用 suffixes_clean
            if suffix_part:
                blocks.extend(self._match_text(suffix_part, self.suffixes_clean, forward=False))
            
            return ".".join(blocks)
        
        # 如果 stem 不在 word 中，尝试用编辑距离分块（简化处理）
        return word
        
    def _split_into_blocks(self, text: str, known_items: list[str]) -> list[str]:
        """
        将文本拆分为已知项的块
        
        Args:
            text: 待拆分的文本
            known_items: 已知项列表（前缀或后缀），已按长度降序排序
            
        Returns:
            块列表，例如 ['ation'] 或 ['pre']
        """
        if not text:
            return []
        
        # 判断 text 是前缀还是后缀部分（根据 text 在原单词中的位置）
        # 这里统一使用从左向右匹配
        return self._match_text(text, known_items, forward=True)
    
    def _match_text(self, text: str, known_items: list[str], forward: bool = True) -> list[str]:
        """
        将文本拆分为已知项的块
        
        Args:
            text: 待拆分的文本
            known_items: 已知项列表（已按长度降序排序）
            forward: True=从左向右匹配, False=从右向左匹配
            
        Returns:
            块列表
        """
        if not text:
            return []
        
        blocks = []
        
        if forward:
            # 从左向右匹配
            i = 0
            while i < len(text):
                matched = False
                for item in known_items:
                    if not item:
                        continue
                    if text[i:i+len(item)] == item:
                        blocks.append(item)
                        i += len(item)
                        matched = True
                        break
                if not matched:
                    # 未匹配的字符保持连续，作为一个块
                    blocks.append(text[i])
                    i += 1
        else:
            # 从右向左匹配
            i = len(text) - 1
            while i >= 0:
                matched = False
                for item in known_items:
                    if not item:
                        continue
                    start = i - len(item) + 1
                    if start >= 0 and text[start:i+1] == item:
                        blocks.insert(0, item)
                        i = start - 1
                        matched = True
                        break
                if not matched:
                    blocks.insert(0, text[i])
                    i -= 1
        
        return blocks
