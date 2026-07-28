"""从 eng_derivations.json 提取逆向索引，以分列压缩格式保存。"""
import json
import sys

src = "data\\eng_derivations.json"
dst = "data\\word_derivations.json"

print(f"Loading {src} ...", file=sys.stderr)
with open(src, encoding="utf-8") as f:
    deriv = json.load(f)

print(f"Loaded: {len(deriv)} entries", file=sys.stderr)

words = []
bases = []
affixes = []
types = []

for base_word, entry in deriv.items():
    for derived_word, info in entry.get("derives_to", {}).items():
        words.append(derived_word)
        bases.append(base_word)
        affixes.append(info["affix"])
        types.append("s" if info["affix_type"] == "suffix" else "p")

out = {"w": words, "b": bases, "a": affixes, "t": types}
print(f"Reverse index: {len(words)} mappings", file=sys.stderr)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(f"Written to {dst}", file=sys.stderr)
