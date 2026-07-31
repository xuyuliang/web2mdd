import os
import sys
sys.path.insert(0, '.')
from app.word_cutter import WordCutter

SRC_LABEL = {"dict": "d", "affix": "a"}
DEFAULT_WORDS = os.path.join("tests", "GRE-words.txt")


def format_seg(segments):
    parts = []
    for s in segments:
        text = s["text"]
        if s.get("meaning"):
            src = SRC_LABEL.get(s.get("source", ""), "")
            if src:
                parts.append(f"{text}{{{src}}}")
            else:
                parts.append(text)
        else:
            parts.append(f"[{text}]")
    return ".".join(parts)


def load_words(path):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run_batch(wc, words, title=None):
    if title:
        print(f"\n=== {title} ({len(words)} 词) ===\n")
    print(f"{'Word':<20} {'Stage1 Crosstem':<48} {'Stage2 Pipeline  {d}=dict {a}=affix'}")
    print("-" * 125)

    pipeline_found = 0
    for w in words:
        r = wc.segment(w)
        crosstem_str = r["stage1"] if r["stage1"] else "(not found)"
        pipeline_str = format_seg(r["parts"])
        has_roots = any(p.get("meaning") for p in r["parts"])
        if has_roots:
            pipeline_found += 1
        print(f"{w:<20} {crosstem_str:<48} {pipeline_str}")

    print(f"\n总计: {len(words)}  |  Stage2 命中词根: {pipeline_found}")


def run_single(wc, word):
    WordCutter.debug = True
    print(f"\n=== {word} ===\n")
    r = wc.segment(word)
    print(f"\nStage1: {r['stage1'] or '(not found)'}")
    print(f"Result: {format_seg(r['parts'])}")


def main():
    wc = WordCutter()
    args = sys.argv[1:]

    if not args:
        run_batch(wc, load_words(DEFAULT_WORDS), "GRE-words")
        return

    arg = args[0]
    if os.path.isfile(arg) or arg.lower().endswith(".txt"):
        path = arg if os.path.isfile(arg) else os.path.join("tests", arg)
        if not os.path.isfile(path):
            print(f"找不到文件: {path}")
            sys.exit(1)
        run_batch(wc, load_words(path), os.path.basename(path))
        return

    run_single(wc, arg)


if __name__ == "__main__":
    main()
