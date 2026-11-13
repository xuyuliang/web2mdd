"""
词频工具 - 从 SQLite 数据库读取 COCA 词频数据，提供按词频排序的模式匹配搜索

启动时把 (小写单词, 最小词频) 全量读入内存（约 54000 条），
模式搜索在内存中用一个正则完成，不再对每个展开模式各做一次 SQL 全表扫描。

支持的通配符（语义与原来的 GLOB 一致）：
    *   →  .*     （任意字符序列）
    .   →  .      （单个字符）
    [abc] → [abc] （字符类，匹配其中任一字符）
    [a-z] → [a-z] （范围）
    [^e]  → [^e]  （反义，不含这些字符）

高级占位符（通过 glob替换表.json 配置）：
    [A]       → [aeiou]
    [T]       → [bcdfghjklmnpqrstvwxyz]
    [AA]      → ai|ay|ee|ea|oa|oo|ie|ei|ey|au|aw|ow|ou|oi|oy|ue|ui|eu|ew|oe|al|ar|er|ir|or|ur
    [AAA]     → air|are|awn|ear|eer|ere|ier|igh|ire|oir|oor|ore|oun|our|ure
    [TT]      → sp|st|tr|cr|gr|fr|pr|br|dr|pl|bl|cl|fl|gl|sl|sc|sk|sm|sn|sw|tw|dw|qu|kn|wr|wh|th|ch|sh|ph|gn|rh
    [TTT]     → str|spr|scr|spl|thr|shr|squ|sph|sch

示例（→ compile_pattern() 编译为单个正则）：
    "dur*"          → during, duration, durable
    "h.llo"         → hello, hallo, hullo
    "cen[aeo]*"     → cenote, cenotaph
    "c[A]n*"        → can*, cen*, cin*, con*, cun*
    "c[AA]n*"       → cain*, cayn*, ceen*, ...
"""
import json
import os
import re
import sqlite3
from itertools import product
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).parent.parent
GLOB_REPLACEMENTS_PATH = BASE_DIR / "static" / "glob替换表.json"

# 已知大写通配符，按长度降序排列（贪心匹配）
WILDCARD_KEYS = ['TTT', 'TT', 'T', 'AAA', 'AA', 'A']
WILDCARD_LETTERS = frozenset(['A', 'T'])


def add_brackets(pattern: str) -> str:
    """将裸大写通配符（A, AA, T, TT 等）和裸 ^ 补上[...]括号

    保持向后兼容，不修改已有的[...]内容。
    示例：
        aTTle    → a[TT]le
        cAnA     → c[A]n[A]
        ep^i*    → ep[^i]*
        s^e^e^e  → s[^e][^e][^e]
        c[A]nA   → c[A]n[A]   (混合写法)
    """
    result = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]

        # 已有括号组 → 整段复制
        if ch == '[':
            j = pattern.find(']', i + 1)
            if j == -1:
                result.append(ch)
                i += 1
            else:
                result.append(pattern[i:j + 1])
                i = j + 1
            continue

        # 裸 ^ → 补为 [^...]
        if ch == '^':
            i += 1
            if i < len(pattern):
                rest = pattern[i:]
                # 尝试匹配最长通配符
                matched = False
                for wc in WILDCARD_KEYS:
                    wlen = len(wc)
                    if len(rest) >= wlen and rest[:wlen] == wc:
                        result.append(f'[^{wc}]')
                        i += wlen
                        matched = True
                        break
                if not matched:
                    # 单个字符
                    result.append(f'[^{pattern[i]}]')
                    i += 1
            else:
                result.append('^')
            continue

        # 裸大写通配符
        if ch in WILDCARD_LETTERS:
            rest = pattern[i:]
            matched = False
            for wc in (w for w in WILDCARD_KEYS if w[0] == ch):
                wlen = len(wc)
                if len(rest) >= wlen and rest[:wlen] == wc:
                    result.append(f'[{wc}]')
                    i += wlen
                    matched = True
                    break
            if matched:
                continue

        # 普通字符
        result.append(ch)
        i += 1

    return ''.join(result)


class PatternPreprocessor:
    """高级模式预处理器：将 [A], [AA] 等占位符展开为实际 GLOB 模式列表"""
    
    def __init__(self, replacements_path: str = None):
        self.replacements_path = replacements_path or str(GLOB_REPLACEMENTS_PATH)
        self.replacements = self._load_replacements()
    
    def _load_replacements(self) -> dict:
        """加载配置文件"""
        if not os.path.exists(self.replacements_path):
            print(f"[PatternPreprocessor] 配置文件不存在: {self.replacements_path}, 使用空配置")
            return {}
        
        with open(self.replacements_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"[PatternPreprocessor] 已加载 {len(data)} 个替换规则")
        return data
    
    def preprocess(self, pattern: str) -> list[str]:
        """预处理模式，返回所有展开后的 GLOB 模式列表
         
         算法步骤：
         1. 将裸大写通配符（A, AA, T, TT 等）自动补上[...]
         2. 找到所有 [xxx] 方括号
         3. 对每个方括号，确定其展开选项
            - 如果是高级占位符且值为列表（如 AA->["ai","ay",...]），每个选项独立
            - 如果是高级占位符且值为字符串（如 A->"aeiou"），包装为 [aeiou]
            - 如果不是高级占位符（如 [aeo]），保持原样 [aeo]
         4. 对所有方括号进行笛卡尔积组合
         5. 将组合结果插入原模式对应位置
         
         示例：
         - cAn*     -> ['can*', 'cen*', 'cin*', 'con*', 'cun*']
         - cAAn*    -> ['cain*', 'cayn*', 'ceen*', 'cean*', ...]
         - cen[aeo]* -> ['cen[aeo]*'] (普通字符类，不展开)
         """
        # 补全裸大写通配符
        pattern = add_brackets(pattern)

        # 查找所有 [xxx] 模式
        bracket_matches = list(re.finditer(r'\[([^\]]*)\]', pattern))
        
        if not bracket_matches:
            return [pattern.lower()]
        
        # 对每个方括号确定其展开选项
        bracket_options = []
        for match in bracket_matches:
            content = match.group(1)
            
            if content in self.replacements:
                replacement = self.replacements[content]
                if isinstance(replacement, list):
                    # 多字符组合：如 AA -> ["ai", "ay", ...]
                    bracket_options.append(replacement)
                else:
                    # 单字符类：如 A -> "aeiou"，包装为 [aeiou]
                    bracket_options.append([f'[{replacement}]'])
            else:
                # 不是高级占位符，保持原样作为 GLOB 字符类
                bracket_options.append([f'[{content}]'])
        
        # 进行笛卡尔积展开
        # 例如：c[A]n* -> bracket_options = [['a','e','i','o','u']]
        #       组合结果 = ['a', 'e', 'i', 'o', 'u']
        # 例如：[tAA]n -> bracket_options = [['ta','ty',...], ['n']]（如果有多个括号）
        #       组合结果 = ['ta', 'ty', ...]
        
        all_combinations = list(product(*bracket_options))
        
        # 将组合结果插入原模式
        final_patterns = []
        for combo in all_combinations:
            result = pattern
            # 从后往前替换，避免索引偏移
            for match, value in zip(reversed(bracket_matches), reversed(combo)):
                start, end = match.start(), match.end()
                result = result[:start] + value + result[end:]
            final_patterns.append(result)
        
        return [p.lower() for p in final_patterns]


# 全局预处理器实例
_preprocessor = None


def get_preprocessor() -> PatternPreprocessor:
    """获取全局预处理器实例（单例）"""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = PatternPreprocessor()
    return _preprocessor


def compile_pattern(pattern: str) -> re.Pattern:
    """把用户模式编译成单个正则表达式

    语义与旧的“展开成多条 GLOB 再 UNION”保持一致：
        *       -> .*          （任意字符序列）
        .       -> .           （单个字符）
        [abc]   -> [abc]       （字符类，支持 [^e] / [a-z]）
        [A]     -> [aeiou]
        [AA]    -> (?:ai|ay|...) （多字符组合用非捕获组）
        [TT]    -> (?:sp|st|...)
    其余字符一律按字面量转义。
    """
    pattern = add_brackets(pattern.strip())
    replacements = get_preprocessor().replacements

    parts: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == '*':
            parts.append('.*')
            i += 1
        elif ch == '.':
            parts.append('.')
            i += 1
        elif ch == '[':
            j = pattern.find(']', i + 1)
            content = pattern[i + 1:j] if j != -1 else ''
            if j == -1 or not content:
                # 不闭合或空字符类，按字面量处理
                parts.append(re.escape(ch))
                i += 1
                continue
            if content in replacements:
                value = replacements[content]
                if isinstance(value, list):
                    parts.append('(?:' + '|'.join(re.escape(v) for v in value) + ')')
                else:
                    parts.append('[' + value + ']')
            else:
                # 与旧实现一致：展开完成后整体转小写
                parts.append('[' + content.lower() + ']')
            i = j + 1
        else:
            parts.append(re.escape(ch.lower()))
            i += 1

    return re.compile('^' + ''.join(parts) + '$')


class WordFreq:
    """COCA 词频工具 - 从 TLD.mdx.index.db 的 coca_words 表读取数据

    启动时把 (小写单词, 最小词频) 全量读进内存（约 54000 条，占 4~5MB），
    之后的模式搜索和排名查询都在内存里完成，不再走 SQL 全表扫描。
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        # 一次性加载词频数据，按词频升序（最常用的在前）
        rows = self.cursor.execute("""
            SELECT LOWER(word) AS w, MIN(frequency) AS f
            FROM coca_words
            GROUP BY LOWER(word)
            ORDER BY f ASC
        """).fetchall()
        # 小写单词 -> 最小词频
        self.freq_map: dict[str, int] = {w: f for w, f in rows}
        # 按词频升序排列的小写单词列表（模式搜索的扫描顺序）
        self._ordered_words: list[str] = [w for w, _f in rows]
        # 兼容旧接口：所有小写单词集合
        self.word_set: set[str] = set(self.freq_map)
        print(f"[WordFreq] 已从数据库加载 {len(self.freq_map)} 个唯一词条")

    def __del__(self):
        """析构时关闭数据库连接"""
        if hasattr(self, 'conn'):
            try:
                self.conn.close()
            except Exception:
                pass

    def get_rank(self, word: str) -> int | None:
        """获取单词的 COCA 词频值（frequency），不在词频表中返回 None"""
        return self.freq_map.get(word.lower())

    def search(self, pattern: str, max_results: int = 50) -> list[str]:
        """在内存词表中搜索匹配的单词（按 frequency 升序，即最常用的在前）

        支持以下模式（与原有 GLOB 语法语义一致）：
        - 精确匹配: "hello"
        - 通配符 *: 任意字符序列 (如 "dur*")
        - 通配符 .: 单个字符 (如 "h.llo" → hello/hallo)
        - 字符类: [abc] 匹配其中任一字符 (如 "cen[aeo]*")，支持 [^e] 与 [a-z]
        - 高级占位符: [A], [T], [AA], [TT], [TTT] 等（通过配置文件）

        返回小写词列表，至多 max_results 个（已去重）。
        """
        pattern = pattern.strip()

        if not pattern:
            return []

        regex = compile_pattern(pattern)

        results: list[str] = []
        for word in self._ordered_words:
            if regex.match(word):
                results.append(word)
                if len(results) >= max_results:
                    break
        return results

