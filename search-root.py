import sys
import re
from app.word_cutter import WordCutter


def glob_to_regex(pattern):
    parts = []
    for ch in pattern:
        if ch == '*':
            parts.append('.*')
        elif ch in '.^${}[]()\\+?|':
            parts.append('\\' + ch)
        else:
            parts.append(ch)
    return re.compile('^' + ''.join(parts) + '$', re.IGNORECASE)


def main():
    if len(sys.argv) < 2:
        print("用法: python search-root.py <pattern>")
        print("示例: python search-root.py mod*")
        print("      python search-root.py *tion")
        print("      python search-root.py *duc*")
        sys.exit(1)

    pattern = sys.argv[1]
    regex = glob_to_regex(pattern)
    wc = WordCutter()

    results = []
    for r in wc.root_index:
        if regex.match(r[0]):
            results.append({
                "root": r[0],
                "meaning": r[2],
                "original": r[3],
                "langCode": r[1],
                "source": r[4] if len(r) > 4 else "",
            })

    results.sort(key=lambda x: x["root"])

    if not results:
        print(f"未找到匹配 '{pattern}' 的词根")
        return

    src_label_map = {"dict": "词根", "affix": "词缀"}
    print(f"找到 {len(results)} 个匹配词根:\n")
    for r in results:
        label = src_label_map.get(r["source"], r["source"])
        print(f"  {r['root']:<20} [{r['langCode']:<2}] {label}  {r['meaning']}")


if __name__ == "__main__":
    main()
