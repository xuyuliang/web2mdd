import sys
sys.path.insert(0, ".")

import ety
from app.morphemes_loader import MorphemesLoader


def load_gre_words(path="tests/GRE-words.txt"):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


loader = MorphemesLoader()
words = load_gre_words()

print(f"{'Word':<20} {'Ety Origins':<50} {'Morph Segmentation':<40} {'Score':>6}")
print("-" * 120)

for w in words:
    origins = ety.origins(w)
    ety_str = ", ".join(f"{o.word}({o.language.iso})" for o in origins) if origins else "(none)"

    result = loader.analyze(w)
    morph_str = ""
    score_str = ""
    if result:
        p = result["primary"]
        morph_str = p["result"]
        score_str = f"{p['score']:.1f}"

    print(f"{w:<20} {ety_str:<50} {morph_str:<40} {score_str:>6}")

print(f"\nTotal words: {len(words)}")
