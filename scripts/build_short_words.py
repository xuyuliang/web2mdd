"""从 oldCOCA60000.txt 提取 3-5 字母常见单词。"""
import json
import sys

src = "数据资料\\oldCOCA60000.txt"
dst = "data\\short_words.json"

words = set()
with open(src, encoding="utf-8") as f:
    for line in f:
        w = line.strip().lower()
        if 3 <= len(w) <= 5:
            words.add(w)

out = {w: True for w in sorted(words)}
print(f"Short words (3-5 letters): {len(out)}", file=sys.stderr)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(f"Written to {dst}", file=sys.stderr)
