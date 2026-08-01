import random
from pathlib import Path

from config import (
    COCA_PATH, RANGE_LO, RANGE_HI, WORDS_ALL, PILOT_WORDS, SEED,
)

def load_coca():
    return [l.strip().lower() for l in COCA_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

def select_words():
    lines = load_coca()
    sel = lines[RANGE_LO - 1:RANGE_HI]
    seen = set()
    words = []
    for w in sel:
        if "-" in w:
            continue
        if w in seen:
            continue
        seen.add(w)
        words.append(w)
    WORDS_ALL.write_text("\n".join(words) + "\n", encoding="utf-8")
    return words

def length_band(w):
    n = len(w)
    if n <= 6:
        return 0
    if n <= 9:
        return 1
    return 2

def pilot_sample(words, n=300, seed=SEED):
    rng = random.Random(seed)
    groups = {0: [], 1: [], 2: []}
    for w in words:
        groups[length_band(w)].append(w)
    picked = []
    for g in (0, 1, 2):
        pool = groups[g]
        per = round(n * len(pool) / max(len(words), 1))
        if g == 2:
            per = n - len(picked)
        picked.extend(rng.sample(pool, min(per, len(pool))))
    rng.shuffle(picked)
    picked = picked[:n]
    PILOT_WORDS.write_text("\n".join(picked) + "\n", encoding="utf-8")
    return picked

def words_from_file(path):
    if isinstance(path, str):
        path = Path(path)
    return [l.strip().lower() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

if __name__ == "__main__":
    words = select_words()
    print("words_all:", len(words))
    counts = {b: 0 for b in (0, 1, 2)}
    for w in words:
        counts[length_band(w)] += 1
    print("band counts (<=6/7-9/10+):", counts)
    pilot = pilot_sample(words)
    print("pilot:", len(pilot))
    pc = {b: 0 for b in (0, 1, 2)}
    for w in pilot:
        pc[length_band(w)] += 1
    print("pilot bands:", pc)
