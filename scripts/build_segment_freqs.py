"""从 data/anki_splits.json 提取手工切分段，统计每段的单词数与位置分布。

位置按 split 串的 "." 边界判定：
  first   词首段（可作前缀）
  last    词尾段（可作后缀）
  middle  中段（一般作词根）
"""
import json
import sys

src = "data\\anki_splits.json"
dst = "数据资料\\segment-freqs.json"

with open(src, encoding="utf-8") as f:
    splits = json.load(f)

words_by_seg = {}
pos_count = {}

for word, info in splits.items():
    split = info.get("split") or ""
    if not split:
        continue
    segs = [s.strip().lower() for s in split.split(".")]
    segs = [s for s in segs if s]
    n = len(segs)
    seen = set()
    for i, seg in enumerate(segs):
        if seg in seen:
            continue
        seen.add(seg)
        if seg not in words_by_seg:
            words_by_seg[seg] = set()
        words_by_seg[seg].add(word)
        pos = "first" if i == 0 else ("last" if i == n - 1 else "middle")
        pc = pos_count.setdefault(seg, {"first": 0, "last": 0, "middle": 0})
        pc[pos] += 1

out = {}
for seg, ws in words_by_seg.items():
    out[seg] = {"count": len(ws), "positions": pos_count[seg]}

sorted_out = {seg: out[seg] for seg, _ in sorted(out.items(), key=lambda x: (-x[1]["count"], x[0]))}
ge3 = sum(1 for seg in sorted_out if sorted_out[seg]["count"] >= 3)
print(f"Segments total: {len(sorted_out)}, >=3 words: {ge3}", file=sys.stderr)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(sorted_out, f, ensure_ascii=False, indent=2)

print(f"Written to {dst}", file=sys.stderr)
