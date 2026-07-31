"""从 morphemes.json 提取前后缀与嵌入词根，重建 affixes.json。

范围: loc in (prefix, suffix, embedded)
不去重: 与 etym-dictionary 冲突时全部收录（由合并逻辑读两侧性质）
同 roots 多条形式合并 meaning 与 langCode
"""
import json
import sys
from collections import defaultdict


def clean_morpheme_root(root):
    return root.strip("-").strip()


morphemes_src = "数据资料\\morphemes.json"
dst = "data\\affixes.json"

print(f"Loading {morphemes_src} ...", file=sys.stderr)
with open(morphemes_src, encoding="utf-8") as f:
    morphemes = json.load(f)

# roots -> {"meanings": set, "langs": set}
grouped = defaultdict(lambda: {"meanings": set(), "langs": set()})
form_count = 0

for key, entry in morphemes.items():
    for form in entry.get("forms", []):
        loc = form.get("loc")
        if loc not in ("prefix", "suffix", "embedded"):
            continue

        root = form.get("root", "")
        cleaned = clean_morpheme_root(root)
        if not cleaned:
            continue

        form_count += 1
        for m in entry.get("meaning", []):
            if m:
                grouped[root]["meanings"].add(m)
        origin = entry.get("origin", "") or ""
        if origin:
            grouped[root]["langs"].add(origin[:2].upper())

entries = []
for root in sorted(grouped):
    meanings = "; ".join(sorted(grouped[root]["meanings"]))
    langs = sorted(grouped[root]["langs"])
    lang_code = "; ".join(langs) if langs else "?"
    entries.append({
        "roots": root,
        "langCode": lang_code,
        "meaning": meanings
    })

out = {"entries": entries}
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Forms collected: {form_count}", file=sys.stderr)
print(f"Unique roots: {len(entries)}", file=sys.stderr)
print(f"Written to {dst}", file=sys.stderr)
