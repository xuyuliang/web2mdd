"""从 segment-freqs.json 提取 >=3 次的段，与 high-freq-affixes.json、roots.json 比对，输出 highfreq.json。"""
import json
import sys

SEG_PATH = "数据资料\\segment-freqs.json"
HF_PATH = "data\\high-freq-affixes.json"
ROOTS_PATH = "data\\roots.json"
DST = "data\\anki_highfreq.json"
MIN_COUNT = 3


def main():
    with open(SEG_PATH, encoding="utf-8") as f:
        segs = json.load(f)
    with open(HF_PATH, encoding="utf-8") as f:
        hf = json.load(f)
    with open(ROOTS_PATH, encoding="utf-8") as f:
        roots = json.load(f)

    hf_forms = {}
    for e in hf:
        form = (e.get("affix") or "").strip("-").strip().lower()
        if len(form) < 2:
            continue
        hf_forms.setdefault(form, []).append(e)

    root_forms = {}
    for base, entry in roots["entries"].items():
        for form, meta in entry.get("forms", {}).items():
            form = form.lower()
            if len(form) < 2:
                continue
            root_forms.setdefault(form, []).append((base, entry, meta))

    out = []
    for seg, n in segs.items():
        if n < MIN_COUNT:
            continue
        if seg in hf_forms:
            for e in hf_forms[seg]:
                item = dict(e)
                item["次数"] = n
                out.append(item)
        elif seg in root_forms:
            _, entry, meta = root_forms[seg][0]
            pos = meta.get("pos", [])
            item = {
                "affix": seg,
                "type": pos[0] if len(pos) == 1 else "",
                "meaning": entry.get("ety_meaning") or entry.get("meaning") or "",
                "example": "",
                "次数": n,
            }
            out.append(item)

    out.sort(key=lambda x: (-x["次数"], x["affix"]))

    print(f"Entries: {len(out)}", file=sys.stderr)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Written to {DST}", file=sys.stderr)


if __name__ == "__main__":
    main()
