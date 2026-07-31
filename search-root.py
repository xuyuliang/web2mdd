import sys
import re
import json
import os
from app.word_cutter import WordCutter

SRC_LABEL = {"dict": "词根", "affix": "词缀"}
POS_LABEL = {"prefix": "前缀", "suffix": "后缀", "root": "根"}
HIGH_FREQ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "high-freq-affixes.json")


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


def load_high_freq():
    with open(HIGH_FREQ_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    lookup = {}
    for e in entries:
        aff = e.get("affix", "")
        form = aff.strip("-").strip().lower()
        if not form:
            continue
        lookup.setdefault(form, []).append({
            "affix": aff,
            "type": e.get("type", ""),
            "meaning": e.get("meaning", ""),
            "example": e.get("example", ""),
        })
    return lookup


def format_pos(pos_set):
    if not pos_set:
        return "-"
    return "/".join(POS_LABEL[p] if p in POS_LABEL else p for p in sorted(pos_set))


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
    high_freq = load_high_freq()

    root_results = []
    for form, interps in wc.root_index.items():
        if not regex.match(form):
            continue
        for interp in interps:
            root_results.append({
                "form": form,
                "base": interp["base"],
                "opt": interp["opt"],
                "pos": interp["pos"],
                "meaning": interp["meaning"],
                "lang": interp["lang"],
                "src": interp["src"],
                "hf": form in high_freq,
            })

    hf_results = []
    for form, items in high_freq.items():
        if not regex.match(form):
            continue
        for item in items:
            hf_results.append({
                "form": form,
                "affix": item["affix"],
                "type": item["type"],
                "meaning": item["meaning"],
                "example": item["example"],
            })

    root_results.sort(key=lambda x: (x["form"], x["base"], x["src"]))
    hf_results.sort(key=lambda x: (x["form"], x["affix"]))

    total = len(root_results) + len(hf_results)
    if not total:
        print(f"未找到匹配 '{pattern}' 的词形")
        return

    n_forms = len(set(r["form"] for r in root_results) | set(r["form"] for r in hf_results))
    print(f"找到 {total} 个匹配（{n_forms} 个不同词形）：\n")

    for r in root_results:
        src = SRC_LABEL.get(r["src"], r["src"])
        opt = "可选" if r["opt"] else "固有"
        hf_note = "  <高频词缀>" if r["hf"] else ""
        print(
            f"  {r['form']:<16} [词根库:{src}] {format_pos(r['pos']):<9} "
            f"基础={r['base']}  {opt}  ({r['lang']})  {r['meaning']}{hf_note}"
        )

    for r in hf_results:
        label = "前缀" if r["type"] == "prefix" else ("后缀" if r["type"] == "suffix" else r["type"])
        ex = f"  例: {r['example']}" if r["example"] else ""
        print(
            f"  {r['affix']:<16} [高频词缀] {label:<9} {r['meaning']}{ex}"
        )


if __name__ == "__main__":
    main()
