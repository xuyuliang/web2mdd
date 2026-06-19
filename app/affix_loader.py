"""
词根词缀加载器 - 从 _prefixes.txt 和 _suffixes.txt 加载前缀和后缀列表
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIXES_PATH = os.path.join(BASE_DIR, "数据资料", "_prefixes.txt")
SUFFIXES_PATH = os.path.join(BASE_DIR, "数据资料", "_suffixes.txt")


class AffixLoader:
    """加载并管理前缀/后缀数据（仅保留不重复的列表）"""

    def __init__(self):
        self.prefixes: list[str] = []  # 按长度降序
        self.suffixes: list[str] = []  # 按长度降序
        self._load()

    def _load(self):
        """从 txt 文件加载所有不重复的前缀和后缀"""
        # 加载前缀
        prefixes_set: set[str] = set()
        with open(PREFIXES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("共"):
                    prefixes_set.add(line)

        # 加载后缀
        suffixes_set: set[str] = set()
        with open(SUFFIXES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("共"):
                    suffixes_set.add(line)

        # 按长度降序排列（优先匹配更长的）
        self.prefixes = sorted(prefixes_set, key=lambda x: len(x), reverse=True)
        self.suffixes = sorted(suffixes_set, key=lambda x: len(x), reverse=True)

    def analyze(self, word: str, min_stem_len: int = 2,
                is_valid_word=None):
        """
        分析单词的前缀和后缀

        参数:
            word: 要分析的单词
            min_stem_len: 去掉前后缀后剩余部分的最小长度
            is_valid_word: 可选函数，接受一个词干字符串，返回 bool
                           用于判断词干是否是一个有效单词

        返回:
        {
            "word": 原词,
            "prefix": 匹配到的前缀（如 "un-"），无则为 "",
            "suffix": 匹配到的后缀（如 "-ness"），无则为 "",
            "stem": 去掉前缀后的词干,
            "final_stem": 去掉前后缀后的最终词干,
        }
        """
        word = word.strip().lower()
        if not word:
            return None

        result = {
            "word": word,
            "prefix": "",
            "suffix": "",
            "stem": word,
            "final_stem": word,
        }

        # 1. 匹配前缀（从开头匹配，按长度降序）
        remaining = word
        for p in self.prefixes:
            p_clean = p.lower().rstrip("-")  # "un-" -> "un"
            if remaining.startswith(p_clean) and len(p_clean) > 0:
                new_remaining = remaining[len(p_clean):]
                if len(new_remaining) >= min_stem_len:
                    # 如果去掉前缀后的词干本身是一个有效单词，才进行切分
                    # 这可以避免 "beautiful" 被切掉 "be-" 剩下 "autiful"
                    if is_valid_word is None or is_valid_word(new_remaining):
                        result["prefix"] = p
                        remaining = new_remaining
                        break

        result["stem"] = remaining

        # 2. 匹配后缀（从结尾匹配，按长度降序）
        for s in self.suffixes:
            s_clean = s.lower().lstrip("-")  # "-ness" -> "ness"
            if remaining.endswith(s_clean) and len(s_clean) > 0:
                new_remaining = remaining[:-len(s_clean)]
                if len(new_remaining) >= min_stem_len:
                    # 条件1: 去掉后缀后的词干本身是一个有效单词
                    stem_is_valid = is_valid_word is None or is_valid_word(new_remaining)
                    if not stem_is_valid:
                        continue
                    # 条件2: 对于单字符后缀（如 -a, -o, -y），如果原词本身是有效单词则不切分
                    # 这可以避免 "hello" 被切 "-o" 剩下 "hell"，或 "piano" 被切 "-o" 剩下 "pian"
                    if len(s_clean) <= 1 and is_valid_word is not None and is_valid_word(remaining):
                        continue
                    result["suffix"] = s
                    remaining = new_remaining
                    break

        result["final_stem"] = remaining
        return result


# 全局单例
_loader: AffixLoader | None = None


def get_affix_loader() -> AffixLoader:
    """获取全局 AffixLoader 实例（延迟加载）"""
    global _loader
    if _loader is None:
        _loader = AffixLoader()
    return _loader


if __name__ == "__main__":
    loader = AffixLoader()
    print(f"前缀数: {len(loader.prefixes)}")
    print(f"后缀数: {len(loader.suffixes)}")

    # 模拟一个简单的有效词判断（用于测试）
    common_words = {
        "happy", "believe", "sleep", "write", "agree", "beauty",
        "child", "possible", "nation", "view", "splice", "hello",
        "able", "lock", "build", "paid", "dark", "work", "teach",
        "quick", "slow", "friend", "hope", "use", "joy", "large",
        "enjoy", "beautiful",
    }

    def is_valid(w):
        return w in common_words

    test_words = ["unhappiness", "unbelievable", "asleep", "rewrite",
                  "disagreement", "beautiful", "childhood", "impossible",
                  "international", "preview", "splice", "hello",
                  "unable", "unlock", "rebuild", "prepaid",
                  "happiness", "darkness", "worker", "teacher",
                  "quickly", "slowly", "friendly", "national",
                  "hopeless", "useless", "enjoy", "enlarge"]
    for w in test_words:
        r = loader.analyze(w, is_valid_word=is_valid)
        if r:
            parts = []
            if r["prefix"]:
                parts.append(f"前缀={r['prefix']}")
            if r["suffix"]:
                parts.append(f"后缀={r['suffix']}")
            if parts:
                print(f"{w:20s} -> {' + '.join(parts)}, 词干={r['final_stem']}")
            else:
                print(f"{w:20s} -> 无匹配")
