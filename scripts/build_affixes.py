"""从 morphemes.json 提取前后缀，去重（与 etym-dictionary 冲突的跳过）。"""
import json
import sys


def get_main_root(roots_str):
    parts = [r.strip() for r in roots_str.split(",")]
    return parts[0] if parts else ""


def load_ety_roots(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    all_roots = set()
    for e in data["entries"]:
        main = get_main_root(e["roots"])
        if main:
            all_roots.add(main)
    return all_roots


def clean_morpheme_root(root):
    return root.strip("-").strip()


morphemes_src = "数据资料\\morphemes.json"
ety_src = "data\\etym-dictionary.json"
dst = "data\\affixes.json"

print(f"Loading {ety_src} ...", file=sys.stderr)
ety_roots = load_ety_roots(ety_src)
print(f"Etym-dictionary roots: {len(ety_roots)}", file=sys.stderr)

print(f"Loading {morphemes_src} ...", file=sys.stderr)
with open(morphemes_src, encoding="utf-8") as f:
    morphemes = json.load(f)

entries = []
skip_count = 0
add_count = 0

for key, entry in morphemes.items():
    for form in entry.get("forms", []):
        loc = form.get("loc")
        if loc not in ("prefix", "suffix"):
            continue

        root = form.get("root", "")
        cleaned = clean_morpheme_root(root)
        if not cleaned or len(cleaned) < 2:
            continue

        if cleaned in ety_roots:
            skip_count += 1
            continue

        meaning = entry.get("meaning", [""])
        meaning_str = meaning[0] if meaning else ""
        origin = entry.get("origin", "") or ""

        entries.append({
            "roots": root,
            "langCode": origin[:2].upper() if origin else "?",
            "meaning": meaning_str
        })
        add_count += 1

print(f"Skipped (conflict with etym-dictionary): {skip_count}", file=sys.stderr)
print(f"Added affixes: {add_count}", file=sys.stderr)

# Deduplicate by roots
seen = set()
deduped = []
for e in entries:
    if e["roots"] not in seen:
        seen.add(e["roots"])
        deduped.append(e)

out = {"entries": deduped}
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Written to {dst} ({len(deduped)} unique entries)", file=sys.stderr)
