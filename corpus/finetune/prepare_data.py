"""
Подготовка датасета для файнтюна NLLB-200.

Разбивает parallel_ing_rus.jsonl на train/dev/test (90/5/5),
создаёт пары в обоих направлениях (ing→rus и rus→ing).

Выход (в той же папке):
  train.jsonl, dev.jsonl, test.jsonl

Формат строки:
  {"src": "...", "tgt": "...", "src_lang": "inh_Cyrl", "tgt_lang": "rus_Cyrl"}

Usage:
  python prepare_data.py [--seed 42] [--dev 5] [--test 5]
"""

import argparse
import json
import random
from pathlib import Path

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
OUT_DIR = Path(__file__).parent

ING_LANG = "inh_Cyrl"
RUS_LANG = "rus_Cyrl"


def load_pairs():
    pairs = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            row = json.loads(line)
            ing = row["ing"].strip()
            rus = row["rus"].strip()
            if ing and rus:
                pairs.append((ing, rus))
    return pairs


def make_bilingual(pairs):
    """Both directions from each pair."""
    result = []
    for ing, rus in pairs:
        result.append({"src": ing, "tgt": rus, "src_lang": ING_LANG, "tgt_lang": RUS_LANG})
        result.append({"src": rus, "tgt": ing, "src_lang": RUS_LANG, "tgt_lang": ING_LANG})
    return result


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  {path.name}: {len(rows):,} examples")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev", type=float, default=5.0, help="Dev split (percent)")
    parser.add_argument("--test", type=float, default=5.0, help="Test split (percent)")
    args = parser.parse_args()

    pairs = load_pairs()
    print(f"Загружено пар: {len(pairs):,}")

    random.seed(args.seed)
    random.shuffle(pairs)

    n = len(pairs)
    n_test = max(100, int(n * args.test / 100))
    n_dev  = max(100, int(n * args.dev / 100))
    n_train = n - n_dev - n_test

    train_pairs = pairs[:n_train]
    dev_pairs   = pairs[n_train:n_train + n_dev]
    test_pairs  = pairs[n_train + n_dev:]

    print(f"Train: {len(train_pairs):,} par  ->  {len(train_pairs)*2:,} examples (x2 directions)")
    print(f"Dev:   {len(dev_pairs):,} par  ->  {len(dev_pairs)*2:,} examples")
    print(f"Test:  {len(test_pairs):,} par  ->  {len(test_pairs)*2:,} examples")

    print("\nСохранение...")
    write_jsonl(OUT_DIR / "train.jsonl", make_bilingual(train_pairs))
    write_jsonl(OUT_DIR / "dev.jsonl",   make_bilingual(dev_pairs))
    write_jsonl(OUT_DIR / "test.jsonl",  make_bilingual(test_pairs))

    print("\nГотово.")


if __name__ == "__main__":
    main()
