"""从 etym-dictionary.json 与 affixes.json 合并生成统一词根数据结构 data/roots.json。

设计（已定稿）：
  数据源以"基础根"为键，每个条目持有 ety 的扩展标示（ext）与释义（ety_meaning），
  以及 affix 的位置信息（forms[form].pos）与合并后的展示释义（meaning）。

  entries[base] = {
    "ext": "-in =en",      # ety 扩展标示（- 可选 / = 固有 / * 变体），原样保留语义
    "meaning": "...",      # 展示释义：affix 优先，否则 ety
    "lang": "...",         # 展示语系
    "ety_meaning": "...",  # ety 释义（两边都不丢）
    "ety_lang": "...",
    "forms": {
      "abdom":   {"opt": false, "pos": ["prefix", "root", "suffix"]},
      "abdomin": {"opt": true,  "pos": ["prefix"]},
      "abdomen": {"opt": false, "pos": ["prefix", "suffix"]}
    }
  }

  opt: true = 可选扩展（-/*），false = 本尊、固有扩展（=）或 affix 独立形式
  pos: 由 affix 破折号形态推断的位置（prefix/root/suffix）；缺省 = 无位置约束

  pos 推断规则：
    "xxx-"  -> prefix   "-xxx-" -> root   "-xxx" -> suffix   "xxx" -> 无
    （"xxx- " 等尾随空格先 strip 再判定）

  归属规则：
    - affix 词形若落在某个 ety 基础根的变体集合内，则并入该基础根的 forms，
      不单独立条目（例如 abdomin 并入 abdom，而不是独立的 abdomin 基础根）。
    - 其余 affix 词形成为独立基础根条目。
    - ety 基础根本身（如 acti）无论是否也是他人变体，都保留自己的条目。
"""
import json
import re
import sys
from collections import defaultdict

ETYM_SRC = "data\\etym-dictionary.json"
AFFIX_SRC = "data\\affixes.json"
DST = "data\\roots.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_ety_roots(roots_str):
    """解析 ety 的 roots 字符串。

    返回 (base, [(form, opt), ...], [ext_token, ...])。
    基础根提取首个逗号段的字母前缀；扩展变体须 isalpha() 才收录，
    以过滤 "=us (G)· A rein" 等混排脏数据。
    """
    roots_str = roots_str.lstrip("\u2022")
    parts = [p.strip() for p in roots_str.split(",")]
    if not parts or not parts[0]:
        return None, [], []

    m = re.match(r"[A-Za-z]+", parts[0].lstrip("-*="))
    if not m:
        return None, [], []
    base = m.group(0)

    forms = []
    ext = []
    seen = set()
    for p in parts[1:]:
        p = p.strip()
        if not p:
            continue
        if p.startswith(("=", "-", "*")):
            form = base + p[1:]
            opt = p[0] in ("-", "*")
            if form not in seen and form.isalpha():
                forms.append((form, opt))
                seen.add(form)
            if p not in ext:
                ext.append(p)
        else:
            q = p.strip("-*").strip()
            if q and q.isalpha() and q not in seen:
                forms.append((q, False))
                seen.add(q)
    return base, forms, ext


def affix_pos(dashed):
    """从 affix 的破折号形态推断位置；无标记返回 None。"""
    d = dashed.strip()
    left = d.startswith("-")
    right = d.endswith("-")
    if left and right:
        return "root"
    if left:
        return "suffix"
    if right:
        return "prefix"
    return None


def join_langs(langs):
    """合并语系；存在真实语系时丢弃占位的 '?'。"""
    real = sorted(x for x in langs if x and x != "?")
    if real:
        return "; ".join(real)
    if langs:
        return "?"
    return ""


def main():
    ety = load_json(ETYM_SRC)["entries"]
    affixes = load_json(AFFIX_SRC)["entries"]
    print(f"ety: {len(ety)}  entries, affix: {len(affixes)}  entries", file=sys.stderr)

    # ── ety 侧：按基础根分组 ─────────────────────────────────────
    ety_bases = defaultdict(
        lambda: {"ext": [], "ext_set": set(), "meanings": set(),
                 "langs": set(), "forms": {}}
    )
    variant_owners = defaultdict(set)

    for en in ety:
        base, forms, ext = parse_ety_roots(en["roots"])
        if not base:
            continue
        b = ety_bases[base]
        if en.get("meaning"):
            b["meanings"].add(en["meaning"])
        if en.get("langCode"):
            b["langs"].add(en["langCode"])
        for t in ext:
            if t not in b["ext_set"]:
                b["ext_set"].add(t)
                b["ext"].append(t)
        b["forms"][base] = False
        for f, opt in forms:
            b["forms"][f] = b["forms"].get(f, False) or opt
            if f != base:
                variant_owners[f].add(base)

    # ── affix 侧：按干净词形聚合位置与释义 ───────────────────────
    affix_forms = defaultdict(
        lambda: {"pos": set(), "meanings": set(), "langs": set()}
    )
    for en in affixes:
        dashed = en["roots"]
        clean = dashed.strip().strip("-")
        if not clean:
            continue
        a = affix_forms[clean]
        pos = affix_pos(dashed)
        if pos:
            a["pos"].add(pos)
        if en.get("meaning"):
            a["meanings"].add(en["meaning"])
        if en.get("langCode"):
            a["langs"].add(en["langCode"])

    # ── 合并 ────────────────────────────────────────────────────
    entries = {}
    for base in sorted(set(ety_bases)):
        b = ety_bases[base]
        aff = affix_forms.get(base)

        all_aff_meanings = set()
        all_aff_langs = set()
        if aff:
            all_aff_meanings |= aff["meanings"]
            all_aff_langs |= aff["langs"]
        for f in b["forms"]:
            va = affix_forms.get(f)
            if va:
                all_aff_meanings |= va["meanings"]
                all_aff_langs |= va["langs"]

        ety_meaning = "; ".join(sorted(b["meanings"]))
        ety_lang = join_langs(b["langs"])
        if all_aff_meanings:
            meaning = "; ".join(sorted(all_aff_meanings))
            lang = join_langs(all_aff_langs) or ety_lang
        else:
            meaning = ety_meaning
            lang = ety_lang

        forms = {}
        for f, opt in b["forms"].items():
            meta = {"opt": opt}
            fa = affix_forms.get(f)
            if fa and fa["pos"]:
                meta["pos"] = sorted(fa["pos"])
            forms[f] = meta

        entry = {
            "meaning": meaning,
            "lang": lang or "?",
            "forms": forms,
        }
        if b["ext"]:
            entry["ext"] = " ".join(b["ext"])
        if b["meanings"]:
            entry["ety_meaning"] = ety_meaning
            entry["ety_lang"] = ety_lang or "?"
        entries[base] = entry

    # ── 纯 affix 独立基础根（非他人变体） ────────────────────────
    standalone = 0
    for base in sorted(affix_forms):
        if base in ety_bases or base in variant_owners:
            continue
        a = affix_forms[base]
        pos_list = sorted(a["pos"]) if a["pos"] else []
        meta = {"opt": False, "pos": pos_list} if pos_list else {"opt": False}
        forms = {base: meta}
        entries[base] = {
            "meaning": "; ".join(sorted(a["meanings"])) if a["meanings"] else "",
            "lang": join_langs(a["langs"]),
            "forms": forms,
        }
        standalone += 1

    out = {
        "meta": {
            "version": 1,
            "sources": ["etym-dictionary.json", "affixes.json"],
        },
        "entries": entries,
    }
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    form_count = sum(len(e["forms"]) for e in entries.values())
    print(f"bases: {len(entries)} (standalone affix-only: {standalone})", file=sys.stderr)
    print(f"ety groups merged: {len(ety_bases)}, affix clean forms: {len(affix_forms)}", file=sys.stderr)
    print(f"total forms in entries: {form_count}", file=sys.stderr)
    print(f"written to {DST}", file=sys.stderr)


if __name__ == "__main__":
    main()
