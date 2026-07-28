import json
import sys


def load_gre_words(path="tests/GRE-words.txt"):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


print("Loading eng_derivations.json (70 MB) ...", file=sys.stderr)
with open("data/eng_derivations.json", encoding="utf-8") as f:
    deriv = json.load(f)
print(f"Loaded: {len(deriv)} entries", file=sys.stderr)

# Build reverse index: derived_word -> (base_word, affix, affix_type)
print("Building reverse index ...", file=sys.stderr)
rev_index = {}
for base_word, entry in deriv.items():
    for derived_word, info in entry.get("derives_to", {}).items():
        rev_index[derived_word] = {
            "base": base_word,
            "affix": info["affix"],
            "affix_type": info["affix_type"]
        }
print(f"Reverse index: {len(rev_index)} entries", file=sys.stderr)


def trace_derivation(word, rev_index, deriv, depth=0, max_depth=10):
    """Recursively trace derivation chain using reverse index."""
    if depth >= max_depth:
        return None

    # Prefer explicit derived_from, fall back to reverse index
    entry = deriv.get(word)
    base_word = None
    affix_info = None

    if entry:
        df = entry.get("derived_from")
        if df:
            keys = list(df.keys())
            if keys:
                base_word = keys[0]
                affix_info = df[base_word]

    if base_word is None and word in rev_index:
        base_word = rev_index[word]["base"]
        affix_info = rev_index[word]
    else:
        pass

    if base_word is None:
        return None

    inner = trace_derivation(base_word, rev_index, deriv, depth + 1, max_depth)

    affix = affix_info["affix"]
    affix_type = affix_info["affix_type"]

    if affix_type == "suffix":
        if inner:
            return inner + [affix]
        return [base_word, affix]
    else:
        if inner:
            return [affix] + inner
        return [affix, base_word]


words = load_gre_words()

# Count reverse index coverage
rev_covered = sum(1 for w in words if w in rev_index)
df_covered = sum(1 for w in words if w in deriv and deriv[w].get("derived_from"))
print(f"GRE words with reverse index entry: {rev_covered}", file=sys.stderr)
print(f"GRE words with explicit derived_from: {df_covered}", file=sys.stderr)
print(file=sys.stderr)

print(f"{'Word':<20} {'Segmentation':<50} {'Chain'}")
print("-" * 105)

found = 0
for w in words:
    parts = trace_derivation(w, rev_index, deriv)
    if parts:
        found += 1
        seg = ".".join(parts)
        chain = " <- ".join(reversed(parts))
        print(f"{w:<20} {seg:<50} {chain}")
    else:
        print(f"{w:<20} (no derivation info)")

print(f"\n总计: {len(words)}  |  可追溯派生: {found}  |  无信息: {len(words) - found}")
