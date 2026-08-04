"""构建"词素身份表" data/allomorph_groups.json。

把不同来源的表层形式（surface forms）归并为同一个"词根/词缀身份"（原型词素）。

来源节点：
  1. 手工高频词缀表 high-freq-affixes.json   （释义最干净的权威，优先）
  2. roots.json 的 base+forms                  （base→form 是权威变体边，但同样过释义门）
  3. 语料段 segment-freqs.json                 （无释义，只参与既有身份的计数）

变体边（规则候选，仅 prefix/suffix 位置、同位置配对）：
  pad          长度差 1 的单字母插入/删除          ty/ity, e/ex, tion/ation
  elide        pad 的特例：插入字母补成双写 (.)\1   spell/spel, zoo/zo
  assimilation 长度相等、边界单字母替换(辅音)      ex/ef, com/con, sub/suc

安全闸（全部边统一执行）：
  - 释义相似门：按"每行释义"两两比较（CN 按标点/点号分块、EN 按词干），
    任意一行对重叠 ≥ MIN_OVERLAP 即并入；跨语言（一侧 CN 一侧 EN）视为"无法判断"。
  - 门不过或无法判断的边 → 写入 data/allomorph_review.json（人工/LLM 二审），
    绝不静默合并。因此 di/dis（希腊"二" vs 拉丁"分开"）只会进 review。
  - 无释义的语料段不做任何规则边（防 spel(cave) 误并 spell(英文)）。
"""
import json
import re
import sys
import time
from collections import defaultdict

ROOTS = "data\\roots.json"
MANUAL = "data\\high-freq-affixes.json"
SEG_FREQS = "数据资料\\segment-freqs.json"
SPLITS_PATH = "data\\anki_splits.json"
RULES_PATH = "蒸馏计划2完整词根\\output\\rules_clean.jsonl"
DST = "data\\allomorph_groups.json"
REVIEW = "data\\allomorph_review.json"

MIN_OVERLAP = 0.5
VOWELS = set("aeiouy")
EN_STOP = {
    "a", "an", "the", "to", "of", "in", "for", "on", "and", "or", "with",
    "from", "as", "by", "at", "is", "are", "be", "do", "does", "did", "have",
    "has", "it", "its", "this", "that", "these", "those", "up",
}

# (form, pos) -> node
NODES = {}
AUTHORITATIVE = []


def cn_tokens(g):
    toks = re.split(r"[；;，,。、/·\.…\s\d()（）_\-]+", g)
    return [t for t in toks if any("\u4e00" <= c <= "\u9fff" for c in t)]


def en_tokens(g):
    words = re.findall(r"[a-z]+", g.lower())
    return [w for w in words if w not in EN_STOP and len(w) > 1]


def is_cn(g):
    return any("\u4e00" <= c <= "\u9fff" for c in g)


def line_tokens(line):
    if is_cn(line):
        return "cn", cn_tokens(line)
    return "en", en_tokens(line)


def line_overlap(l1, l2):
    k1, t1 = line_tokens(l1)
    k2, t2 = line_tokens(l2)
    if k1 != k2:
        return None
    if not t1 or not t2:
        return None
    return len(set(t1) & set(t2)) / min(len(set(t1)), len(set(t2)))


def node(form, pos):
    return NODES.setdefault((form, pos), {
        "form": form,
        "pos": pos,
        "lines": [],          # 释义行（manual 优先在前）
        "gloss": None,        # 首行，供展示
        "gloss_src": None,
        "count": 0,
        "rank": 4,            # manual=0 roots_base=1 roots_form=2 corpus=3
    })


def add_line(n, line, src):
    line = (line or "").strip()
    if not line:
        return
    # manual 释义一旦存在，roots 释义不再参与判定（防 di/dis 这类 roots 混义）
    if src == "roots" and n["gloss_src"] == "manual":
        return
    # 去重；manual 行优先插入
    if src == "manual" and n["gloss_src"] != "manual":
        n["lines"] = [line] + [x for x in n["lines"] if x != line]
    else:
        if line not in n["lines"]:
            n["lines"].append(line)
    if n["gloss_src"] is None or (src == "manual" and n["gloss_src"] != "manual"):
        n["gloss"] = line
        n["gloss_src"] = src


def norm_affix(s):
    return s.strip("-").strip().lower()


def load_manual():
    with open(MANUAL, encoding="utf-8") as f:
        entries = json.load(f)
    for e in entries:
        form = norm_affix(e.get("affix") or "")
        t = (e.get("type") or "").lower()
        if t not in ("prefix", "suffix"):
            continue
        if not form or not form.isalpha():
            continue
        n = node(form, t)
        add_line(n, (e.get("meaning") or "").strip(), "manual")
        n["rank"] = min(n["rank"], 0)
        n["count"] = max(n["count"], e.get("次数") or 0)


def load_roots():
    with open(ROOTS, encoding="utf-8") as f:
        data = json.load(f)
    for base, entry in data["entries"].items():
        forms = entry.get("forms") or {}
        base_low = base.lower()
        base_pos = set()
        form_meta = []
        for fname, meta in forms.items():
            fl = fname.lower()
            pos = meta.get("pos") or ["root"]
            pos = [p.lower() for p in pos]
            base_pos |= set(pos)
            form_meta.append((fl, pos, bool(meta.get("opt", False))))
        gloss = (entry.get("ety_meaning") or entry.get("meaning") or "").strip()
        for p in (["root"] if not base_pos else list(base_pos)):
            bn = node(base_low, p)
            bn["rank"] = min(bn["rank"], 1)
            add_line(bn, gloss, "roots")
        for fname, pos_list, opt in form_meta:
            if fname == base_low:
                continue
            for p in pos_list:
                if p not in base_pos:
                    continue
                n = node(fname, p)
                n["rank"] = min(n["rank"], 2)
                add_line(n, gloss, "roots")
                AUTHORITATIVE.append((base_low, fname, p, gloss, opt))


def load_corpus():
    with open(SEG_FREQS, encoding="utf-8") as f:
        segs = json.load(f)
    pmap = {"first": "prefix", "last": "suffix", "middle": "root"}
    for form, info in segs.items():
        for p, c in info["positions"].items():
            if c <= 0:
                continue
            n = node(form, pmap[p])
            n["count"] += c
            n["rank"] = min(n["rank"], 3)
    # 方案 A：纯语料节点（无释义）继承同形式手工/词根节点的释义，
    # 让 review 里的 a_gloss/b_gloss 不再因跨位置而显示 null（如 lar@root 的"海鸥"）。
    for (f, p), n in NODES.items():
        if n["lines"]:
            continue
        for (f2, p2), m in NODES.items():
            if f2 == f and m["lines"]:
                n["lines"] = list(m["lines"])
                n["gloss"] = m["gloss"]
                n["gloss_src"] = m["gloss_src"]
                break


def load_example_index():
    """form -> [{w, seg, src, pos, trust}]，供 review 条目取例词。

    来源：
      - data/anki_splits.json（手工切分，{word:{split,source}}，field3 优先）
      - 蒸馏计划2完整词根/output/rules_clean.jsonl（{word, segments[]}，23695 条）
    位置按段在串中的位置推断（首/尾/中）。
    """
    idx = defaultdict(list)
    with open(SPLITS_PATH, encoding="utf-8") as f:
        splits = json.load(f)
    for w, v in splits.items():
        s = (v.get("split") or "").strip()
        src = v.get("source") or ""
        if not s:
            continue
        parts = [x.lower() for x in s.split(".") if x]
        if not parts:
            continue
        for i, seg in enumerate(parts):
            p = "prefix" if i == 0 else ("suffix" if i == len(parts) - 1 else "root")
            idx[seg].append({"w": w, "seg": s, "src": "anki", "pos": p, "trust": src == "field3"})
    with open(RULES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            segs = o.get("segments") or []
            w = o.get("word") or ""
            if not w or not segs:
                continue
            for i, seg in enumerate(segs):
                p = "prefix" if i == 0 else ("suffix" if i == len(segs) - 1 else "root")
                idx[seg.lower()].append({"w": w, "seg": ".".join(segs), "src": "rules", "pos": p, "trust": False})
    return idx


def pick_examples(form, pos, idx, cap=4):
    """取同位置例词：field3 > 其余 anki > rules，去重，每形上限 cap。"""
    cand = [x for x in idx.get(form.lower(), []) if x["pos"] == pos]
    cand.sort(key=lambda x: (0 if x["trust"] else (1 if x["src"] == "anki" else 2), x["w"].lower()))
    out = []
    seen = set()
    for x in cand:
        key = x["w"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"w": x["w"], "seg": x["seg"], "src": x["src"]})
        if len(out) >= cap:
            break
    return out


def ld_insdel(a, b):
    if abs(len(a) - len(b)) != 1:
        return False, "", -1, None
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    i = 0
    while i < len(shorter) and shorter[i] == longer[i]:
        i += 1
    if shorter[i:] == longer[i + 1:]:
        return True, longer, i, longer[i]
    return False, "", -1, None


CONSONANTS = set("bcdfghjklmnpqrstvwxz")


def _rule_edges_for_legacy(pos):
    """旧实验法：前缀/后缀同位置全两两配对联（仅 prefix/suffix，保留作 B 回归基准）。"""
    by_len_forms = defaultdict(list)
    for (f, p), n in NODES.items():
        if p == pos and f.isalpha():
            by_len_forms[len(f)].append(f)
    for L in by_len_forms:
        by_len_forms[L] = sorted(set(by_len_forms[L]))
    lens = sorted(by_len_forms)
    edges = []
    for L in lens:
        for f1 in by_len_forms[L]:
            for f2 in by_len_forms.get(L + 1, []):
                ok, longer, ins_pos, ins_ch = ld_insdel(f1, f2)
                if not ok or ins_ch is None:
                    continue
                sub = "elide" if (ins_pos > 0 and longer[ins_pos - 1] == ins_ch) else "pad"
                edges.append((f1, f2, sub))
    for L in lens:
        fs = by_len_forms[L]
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                diff = [k for k in range(L) if a[k] != b[k]]
                if len(diff) != 1:
                    continue
                k = diff[0]
                if k not in (0, L - 1):
                    continue
                if a[k] in VOWELS or b[k] in VOWELS:
                    continue
                edges.append((a, b, "assimilation"))
    return edges


def rule_edges_for(pos):
    """候选索引式生成 pad/elide/assimilation 候选边（等价重构，避免两两爆炸）。

    对 prefix/suffix 应产出与 _rule_edges_for_legacy 完全一致的边三元组集合。
    root 位置只探右侧变形（见 §3 词形规则）：
      - pad/elide：仅 cand == 长形删末位（右端插/删）；
      - assimilation：仅在右边界 L-1 替换辅音，不试左边界 0。
    """
    root_only_right = (pos == "root")
    by_len_set = defaultdict(set)
    for (f, p), n in NODES.items():
        if p == pos and f.isalpha():
            by_len_set[len(f)].add(f)
    lens = sorted(by_len_set)
    pad_edges = []
    # pad/elide：对每个长形用候选删除查出短形命中；sub 判定沿用 ld_insdel（与旧式一致）
    seen_pad = set()
    for L in lens:
        short_set = by_len_set.get(L)
        for longer in by_len_set.get(L + 1, ()):
            if root_only_right:
                cands = (longer[:-1],) if longer[:-1] in short_set else ()
            else:
                cands = [longer[:i] + longer[i + 1:] for i in range(len(longer))]
                cands = [c for c in cands if c in short_set]
            for cand in set(cands):
                ok, _long, ins_pos, ins_ch = ld_insdel(cand, longer)
                if not ok or ins_ch is None:
                    continue
                sub = "elide" if (ins_pos > 0 and _long[ins_pos - 1] == ins_ch) else "pad"
                edge = (cand, longer, sub)
                if edge not in seen_pad:
                    seen_pad.add(edge)
                    pad_edges.append(edge)
    # assimilation
    ass_edges = []
    seen = set()
    for L in lens:
        fs = by_len_set[L]
        positions = (L - 1,) if root_only_right else (0, L - 1)
        for f in fs:
            for k in positions:
                if k < 0:
                    continue
                if f[k] in VOWELS:
                    continue
                for c in CONSONANTS:
                    if c == f[k]:
                        continue
                    cand = f[:k] + c + f[k + 1:]
                    if cand not in fs:
                        continue
                    key = tuple(sorted((f, cand)))
                    if key in seen:
                        continue
                    seen.add(key)
                    a, b = (f, cand) if f < cand else (cand, f)
                    ass_edges.append((a, b, "assimilation"))
    return pad_edges + ass_edges


class UF:
    def __init__(self, keys):
        self.p = {k: k for k in keys}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def decide_merge(n1, n2, etype=None):
    """True=并入 / False=拒并 / None=无法判断。按释义行两两取最大重叠。

    assimilation 类额外要求共享 ≥2 个词（如 de/se 仅共享单个"离开"就拒并，
    防止 re/de/se 这类彼此仅沾"相反/离开"泛义的前缀串成一团）。
    """
    l1, l2 = n1["lines"], n2["lines"]
    if not l1 or not l2:
        return False
    any_comp = False
    for x in l1:
        for y in l2:
            ov = line_overlap(x, y)
            if ov is None:
                continue
            any_comp = True
            if etype == "assimilation":
                k1, t1 = line_tokens(x)
                k2, t2 = line_tokens(y)
                if k1 != k2:
                    continue
                shared = len(set(t1) & set(t2))
                if shared >= 2 and ov >= MIN_OVERLAP:
                    return True
            else:
                if ov >= MIN_OVERLAP:
                    return True
    if any_comp:
        return False
    return None


def main():
    load_manual()
    load_roots()
    load_corpus()

    review = []
    idx = load_example_index()

    def add_review(a, b, pos, etype, na, nb, reason):
        if reason == "no_gloss":
            return
        if min(na["rank"], nb["rank"]) > 1:
            return
        review.append({
            "a": a, "b": b, "pos": pos, "type": etype, "source": "authoritative"
            if etype == "roots_form" else "rule",
            "a_gloss": na["gloss"], "b_gloss": nb["gloss"], "reason": reason,
            "examples": {"a": pick_examples(a, pos, idx), "b": pick_examples(b, pos, idx)},
            "positive": "",
        })

    edges = []

    # 1) authoritative roots base->form（过门）
    for b, f, p, gloss, opt in AUTHORITATIVE:
        if (b, p) not in NODES or (f, p) not in NODES:
            continue
        nb, nf = NODES[(b, p)], NODES[(f, p)]
        r = decide_merge(nb, nf, "roots_form")
        if r is True:
            edges.append((b, f, p, "roots_form"))
        elif r is False or r is None:
            add_review(b, f, p, "roots_form", nb, nf, "gate" if r is False else "cross_lang")

    # 2) 规则候选边（过门）
    for p in ("prefix", "suffix", "root"):
        t0 = time.time()
        cands = rule_edges_for(p)
        merged = gated = cross = 0
        for a, b, etype in cands:
            if (a, p) not in NODES or (b, p) not in NODES:
                continue
            na, nb = NODES[(a, p)], NODES[(b, p)]
            r = decide_merge(na, nb, etype)
            if r is True:
                edges.append((a, b, p, etype))
                merged += 1
            elif r is False or r is None:
                add_review(a, b, p, etype, na, nb, "gate" if r is False else "cross_lang")
                if r is False:
                    gated += 1
                else:
                    cross += 1
        print(f"[rule_edges] pos={p} candidates={len(cands)} merged={merged} " +
              f"gated={gated} cross_lang={cross} time={time.time() - t0:.2f}s", file=sys.stderr)

    # 3) union-find
    uf = UF(list(NODES.keys()))
    for a, b, p, etype in edges:
        uf.union((a, p), (b, p))

    groups = {}
    for key in NODES:
        groups.setdefault(uf.find(key), []).append(key)

    out_groups = []
    lookup = {}
    for root, members in groups.items():
        # 规范头：rank 低优先，其次语料频次高，其次更长，其次字典序
        cand = []
        for k in members:
            n = NODES[k]
            cand.append((n["rank"], -n["count"], -len(n["form"]), n["form"], k))
        _, _, _, _, head_key = min(cand)
        head = NODES[head_key]
        variants = sorted({NODES[k]["form"] for k in members})
        edge_summary = []
        etypes = set()
        for a, b, p, etype in edges:
            if (a, p) in members and (b, p) in members:
                edge_summary.append([a, b, etype])
                etypes.add(etype)
        gloss = head["gloss"]
        if not gloss:
            for k in members:
                if NODES[k]["gloss"]:
                    gloss = NODES[k]["gloss"]
                    break
        total = sum(NODES[k]["count"] for k in members)
        out_groups.append({
            "canonical": head["form"],
            "pos": head["pos"],
            "variants": variants,
            "gloss": gloss,
            "gloss_src": head["gloss_src"],
            "rank": head["rank"],
            "count": total,
            "edge_types": sorted(etypes),
            "edges": edge_summary,
        })
        for k in members:
            lookup[f"{k[0]}@{k[1]}"] = head["form"]

    out_groups.sort(key=lambda g: (-g["count"], g["canonical"], g["pos"]))

    with open(DST, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "sources": [MANUAL, ROOTS, SEG_FREQS],
                "gate": f"min_overlap={MIN_OVERLAP}",
                "note": "无法判定或门不过的候选对被隔离到 allomorph_review.json，不自动并入",
            },
            "groups": out_groups,
            "lookup": lookup,
        }, f, ensure_ascii=False, indent=2)

    with open(REVIEW, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    print(f"nodes: {len(NODES)}  edges_merged: {len(edges)}  review: {len(review)}  groups: {len(out_groups)}", file=sys.stderr)
    interesting = [g for g in out_groups if len(g["variants"]) > 1
                   and (g["rank"] <= 1 or any(t in g["edge_types"] for t in ("pad", "elide", "assimilation")))]
    interesting.sort(key=lambda g: -g["count"])
    for g in interesting[:60]:
        print(f"  {g['canonical']:8}[{g['pos']}] x{len(g['variants'])} {g['variants']} <- {g['edge_types']} | {g['gloss_src']}", file=sys.stderr)
    print(f"Written {DST} / {REVIEW}", file=sys.stderr)


if __name__ == "__main__":
    main()
