"""从 data/anki_splits.json 提取手工切分段，统计每段的单词数与位置分布。

位置按 split 串的 "." 边界判定：
  first   词首段（可作前缀）
  last    词尾段（可作后缀）
  middle  中段（一般作词根）

改动 A（2026-08-04）：并入第二语料 蒸馏计划2完整词根/output/rules_clean.jsonl
  口径（已拍板，勿改）：
    1. 两源计进同一 segment-freqs.json，count=合计。
    2. 共存词 anki 优先：同词在两源只取 anki_splits 切分；rules 只补 anki 没有的词。
    3. 单段整词不计段：rules 中 len(segments)==1 跳过；anki 侧单段词照计。
    4. 段定位：下标 0→first、末→last、余→middle；每词每段去重计 1 次；段 .lower()。
"""
import json
import os
import sys
import time

SRC = "data\\anki_splits.json"
RULES_SRC = "蒸馏计划2完整词根\\output\\rules_clean.jsonl"
DST = "数据资料\\segment-freqs.json"


def _agg_segment(seg, pos, word, words_by_seg, pos_count, seen):
    if seg in seen:
        return
    seen.add(seg)
    words_by_seg.setdefault(seg, set()).add(word)
    pc = pos_count.setdefault(seg, {"first": 0, "last": 0, "middle": 0})
    pc[pos] += 1


def count_anki(anki_splits):
    """仅 anki 源逐词累加（原逻辑，单段照计）。返回 (words_by_seg, pos_count, word_count)。"""
    words_by_seg = {}
    pos_count = {}
    nwords = 0
    t0 = time.time()
    for word, info in anki_splits.items():
        split = info.get("split") or ""
        if not split:
            continue
        segs = [s.strip().lower() for s in split.split(".")]
        segs = [s for s in segs if s]
        if not segs:
            continue
        nwords += 1
        n = len(segs)
        seen = set()
        for i, seg in enumerate(segs):
            pos = "first" if i == 0 else ("last" if i == n - 1 else "middle")
            _agg_segment(seg, pos, word, words_by_seg, pos_count, seen)
    print(f"[merge] anki words parsed={nwords} time={time.time() - t0:.2f}s", file=sys.stderr)
    return words_by_seg, pos_count, nwords


def count_rules(rules_path, words_by_seg, pos_count, anki_words):
    """rules 源只补 anki 没有的词；跳过单段整词。就地累加。返回处理统计。"""
    stats = {"lines": 0, "single_skip": 0, "coexist_skip": 0, "parsed": 0}
    t0 = time.time()
    with open(rules_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            stats["lines"] += 1
            w = (o.get("word") or "").lower()
            segs = o.get("segments") or []
            if not w or not segs:
                continue
            if w in anki_words:
                stats["coexist_skip"] += 1
                continue
            if len(segs) == 1:
                stats["single_skip"] += 1
                continue
            stats["parsed"] += 1
            n = len(segs)
            segs = [s.strip().lower() for s in segs]
            seen = set()
            for i, seg in enumerate(segs):
                if not seg:
                    continue
                pos = "first" if i == 0 else ("last" if i == n - 1 else "middle")
                _agg_segment(seg, pos, w, words_by_seg, pos_count, seen)
    print(f"[merge] rules parsed={stats['parsed']} coexist_skip={stats['coexist_skip']} "
          f"single_skip={stats['single_skip']} lines={stats['lines']} "
          f"time={time.time() - t0:.2f}s", file=sys.stderr)
    return stats


def build(anki_splits, rules_path, anki_words):
    words_by_seg, pos_count, _ = count_anki(anki_splits)
    count_rules(rules_path, words_by_seg, pos_count, anki_words)
    out = {}
    for seg, ws in words_by_seg.items():
        c = len(ws)
        # positions 中 middle 只对词根计数，count 为去重词数（含各位置）
        out[seg] = {"count": c, "positions": pos_count[seg]}
    return out


def main():
    with open(SRC, encoding="utf-8") as f:
        splits = json.load(f)
    anki_words = {w.lower() for w, v in splits.items()}
    out = build(splits, RULES_SRC, anki_words)

    sorted_out = {seg: out[seg] for seg, _ in sorted(out.items(), key=lambda x: (-x[1]["count"], x[0]))}
    ge3 = sum(1 for seg in sorted_out if sorted_out[seg]["count"] >= 3)
    print(f"Segments total: {len(sorted_out)}, >=3 words: {ge3}", file=sys.stderr)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(sorted_out, f, ensure_ascii=False, indent=2)
    print(f"Written to {DST}", file=sys.stderr)


if __name__ == "__main__":
    main()