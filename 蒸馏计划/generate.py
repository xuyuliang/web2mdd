import argparse
import json
import re
import sys
from pathlib import Path

from config import BATCH_SIZE
from agnes_client import chat
from prompt import build_prompt
from select_words import words_from_file

LINE_RE = re.compile(r"^\s*(\S+?)\s*(?:->|:)\s*([a-z][a-z.]*[a-z.])\s*$", re.I)


def parse_response(content, words):
    results = {}
    for line in (content or "").splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower().strip(".,;:")
        val = m.group(2).strip()
        if key in results:
            continue
        results[key] = val
    out = []
    for w in words:
        val = results.get(w)
        if val:
            segs = [s for s in val.split(".") if s]
            out.append({"word": w, "ok": True, "segments": segs, "raw": val})
        else:
            out.append({"word": w, "ok": False, "segments": [], "raw": None})
    return out


def existing_keys(path):
    keys = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    keys.add(json.loads(line)["word"])
                except Exception:
                    pass
    return keys


def generate(words, out_path, batch_size=BATCH_SIZE, start_batch=None, end_batch=None):
    done = existing_keys(out_path)
    todo = [w for w in words if w not in done]
    print(f"total {len(words)}, already done {len(words) - len(todo)}, to generate {len(todo)}")

    if start_batch is not None and start_batch > 0:
        todo = todo[start_batch:]
    if end_batch is not None:
        todo = todo[:end_batch]

    fh = open(out_path, "a", encoding="utf-8")
    try:
        for i in range(0, len(todo), batch_size):
            batch = todo[i:i + batch_size]
            prompt = build_prompt(batch)
            resp = chat(prompt)
            meta = {
                "reasoning_tokens": resp.get("reasoning_tokens", 0),
                "completion_tokens": resp.get("completion_tokens", 0),
                "elapsed": resp.get("elapsed", 0),
                "error": resp.get("error"),
            }
            parsed = parse_response(resp["content"], batch) if resp["ok"] else [
                {"word": w, "ok": False, "segments": [], "raw": None} for w in batch
            ]
            for p in parsed:
                rec = {"word": p["word"], "ok": p["ok"], "segments": p["segments"],
                       "raw": p["raw"], "meta": meta}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            ok_count = sum(1 for p in parsed if p["ok"])
            print(f"[{i + len(batch)}/{len(todo)}] batch ok={ok_count}/{len(batch)} "
                  f"rt={meta['reasoning_tokens']} ct={meta['completion_tokens']} "
                  f"{meta['elapsed']:.1f}s" + (f" ERR={resp.get('error')}" if not resp["ok"] else ""))
    finally:
        fh.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=BATCH_SIZE)
    ap.add_argument("--start-batch", type=int, default=None)
    ap.add_argument("--end-batch", type=int, default=None)
    args = ap.parse_args()
    words = words_from_file(args.words)
    generate(words, Path(args.out), batch_size=args.batch,
             start_batch=args.start_batch, end_batch=args.end_batch)


if __name__ == "__main__":
    main()
