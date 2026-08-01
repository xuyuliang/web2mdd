import json
import random

from config import (
    CLEAN, TRAIN_JSONL, VAL_JSONL, TEST_JSONL, SEED, SPLIT_TRAIN, SPLIT_VAL,
)


def write(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    records = []
    with open(CLEAN, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    rng = random.Random(SEED)
    rng.shuffle(records)
    n = len(records)
    n_train = int(n * SPLIT_TRAIN)
    n_val = int(n * SPLIT_VAL)
    train = records[:n_train]
    val = records[n_train:n_train + n_val]
    test = records[n_train + n_val:]
    write(TRAIN_JSONL, train)
    write(VAL_JSONL, val)
    write(TEST_JSONL, test)
    print(f"total {n}  train {len(train)}  val {len(val)}  test {len(test)}")


if __name__ == "__main__":
    main()
