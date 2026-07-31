"""从 splits.json 提取手工切分段，统计每个段出现在多少个不同单词中。"""
import json
import sys

src = "数据资料\\splits.json"
dst = "数据资料\\segment-freqs.json"

with open(src, encoding="utf-8") as f:
    splits = json.load(f)

words_by_seg = {}
for word, info in splits.items():
    split = info.get("split") or ""
    if not split:
        continue
    seen = set()
    for seg in split.split("."):
        seg = seg.strip().lower()
        if not seg or seg in seen:
            continue
        seen.add(seg)
        words_by_seg.setdefault(seg, set()).add(word)

counts = {seg: len(ws) for seg, ws in words_by_seg.items()}
out = {seg: n for seg, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))}
ge3 = sum(1 for n in out.values() if n >= 3)
print(f"Segments total: {len(out)}, >=3 words: {ge3}", file=sys.stderr)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Written to {dst}", file=sys.stderr)
