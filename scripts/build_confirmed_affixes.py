"""从词素身份表（allomorph_groups.json）投影，按"词根词缀身份"归并频次，输出 anki_highfreq.json。

每一条目以表面形（variant）为主键：
  - affix=表面形、次数=该表面形在语料对应位置的真实出现次数（不虚高）；
  - merged_count=所属身份的合并总次数（≥ MIN_COUNT 才放行整个组，故家族确认用合并数）；
  - variants/canonical=身份表；edge_types=保留全部边类型（含 roots_form）。
消费端 word_cutter 按表面形精确查表拿加分；分数反映真实频率，冷门变体（如实为 0 次）不再拿到合并加分。
仅收录"确认身份"：组内至少一个变体是手工前后缀（high-freq-affixes.json）或词根（roots.json）。
"""
import json
import sys

GROUPS_PATH = "data\\allomorph_groups.json"
HF_PATH = "data\\high-freq-affixes.json"
ROOTS_PATH = "data\\roots.json"
SEG_PATH = "数据资料\\segment-freqs.json"
DST = "data\\anki_highfreq.json"
MIN_COUNT = 1

# 身份表 pos -> segment-freqs 的位置键
POS_KEY = {"prefix": "first", "suffix": "last", "root": "middle"}


def clean(f):
    return (f or "").strip("-").strip().lower()


def main():
    with open(GROUPS_PATH, encoding="utf-8") as f:
        groups = json.load(f)["groups"]
    with open(HF_PATH, encoding="utf-8") as f:
        hf = json.load(f)
    with open(ROOTS_PATH, encoding="utf-8") as f:
        roots = json.load(f)
    with open(SEG_PATH, encoding="utf-8") as f:
        segs = json.load(f)

    manual = {}          # form -> entry（取首个）
    manual_forms = set()
    for e in hf:
        form = clean(e.get("affix"))
        if len(form) < 2:
            continue
        manual_forms.add(form)
        manual.setdefault(form, e)

    root_forms = set()
    for entry in roots["entries"].values():
        for form in entry.get("forms", {}):
            form = form.lower()
            if len(form) >= 2:
                root_forms.add(form)

    pos_type = {"prefix": "prefix", "suffix": "suffix", "root": ""}

    out = []
    seen = {}
    emitted_groups = 0
    for g in groups:
        if g.get("count", 0) < MIN_COUNT:
            continue
        variants = [v for v in g.get("variants", []) if len(v) >= 2]
        if not variants:
            continue
        if not any(v in manual_forms or v in root_forms for v in variants):
            continue
        emitted_groups += 1
        ttype = pos_type.get(g.get("pos", ""), "")
        pk = POS_KEY.get(g.get("pos", ""), "middle")
        merged_count = g.get("count", 0)
        edge_types = list(g.get("edge_types", []))
        for v in variants:
            m = manual.get(v)
            info = segs.get(v, {})
            positions = info.get("positions", {}) if isinstance(info, dict) else {}
            real_count = positions.get(pk, 0)
            if real_count is None:
                real_count = 0
            item = {
                "affix": v,
                "type": (m.get("type") if m else "") or ttype,
                "meaning": (m.get("meaning") if m else "") or (g.get("gloss") or ""),
                "example": (m.get("example") if m else "") or "",
                "次数": real_count,
                "merged_count": merged_count,
                "canonical": g.get("canonical", v),
                "variants": g.get("variants", [v]),
                "gloss_src": g.get("gloss_src", ""),
                "edge_types": edge_types,
            }
            key = (v, item["type"])
            prev = seen.get(key)
            if prev is None or item["次数"] > prev["次数"]:
                seen[key] = item

    out = list(seen.values())
    out.sort(key=lambda x: (-x["次数"], x["affix"]))

    print(f"Groups emitted: {emitted_groups} / {len(groups)}", file=sys.stderr)
    print(f"Entries: {len(out)}", file=sys.stderr)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Written to {DST}", file=sys.stderr)


if __name__ == "__main__":
    main()
