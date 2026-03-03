"""
Чистка параллельного датасета. Два прохода:

Проход 1 (--pass1): автоматические исправления
  - Исправить HTML-сущности (&mdash; → —, &nbsp; → пробел и т.д.)
  - Удалить пары где любая сторона < MIN_LEN символов
  - Удалить дубликаты по ингушской стороне (оставить первое вхождение)

Проход 2 (--pass2): LaBSE re-scoring
  - Переоценить все пары моделью lingtrain/labse-ingush
  - Удалить пары с cosine similarity < THRESHOLD
  - Исключить из re-scoring: verse-пары (Библия) — они выравнены по ID,
    не по семантике, и низкий score может быть ложным сигналом

Usage:
  python clean_dataset.py --pass1 [--min-len 15] [--dry-run]
  python clean_dataset.py --pass2 [--threshold 0.25] [--dry-run]
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"

# Источники с выравниванием по ID (не по семантике) — исключить из re-scoring
VERSE_SOURCES = {
    "bible-genesis", "bible-luke", "bible-proverbs", "bible-john",
    "bible-esther", "bible-ruth", "bible-jonah",
}

# ─── Утилиты ──────────────────────────────────────────────────────────────────

HTML_ENTITIES = [
    ("&mdash;", "—"), ("&ndash;", "–"), ("&nbsp;", " "),
    ("&laquo;", "«"), ("&raquo;", "»"), ("&hellip;", "…"),
    ("&amp;", "&"),  ("&lt;", "<"),   ("&gt;", ">"),
    ("&quot;", '"'),
]

def fix_html(text: str) -> str:
    for ent, rep in HTML_ENTITIES:
        text = text.replace(ent, rep)
    # Остатки тегов (на всякий случай)
    text = re.sub(r"<[^>]{1,30}>", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def load_dataset():
    rows = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append(json.loads(line))
    return rows


def save_dataset(rows):
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ─── Проход 1: автоматическая чистка ──────────────────────────────────────────

def pass1(min_len: int, dry_run: bool):
    rows = load_dataset()
    original_count = len(rows)
    removed = Counter()
    clean = []
    seen_ing = set()

    for row in rows:
        ing = fix_html(row["ing"])
        rus = fix_html(row["rus"])

        # Слишком короткие
        if len(ing) < min_len or len(rus) < min_len:
            removed["too_short"] += 1
            continue

        # Дубликаты по ингушской стороне
        if ing in seen_ing:
            removed["duplicate"] += 1
            continue
        seen_ing.add(ing)

        row["ing"] = ing
        row["rus"] = rus
        clean.append(row)

    removed_total = original_count - len(clean)
    print(f"Было:    {original_count:,}")
    print(f"Стало:   {len(clean):,}")
    print(f"Удалено: {removed_total:,}")
    for reason, cnt in removed.items():
        print(f"  {reason}: {cnt}")

    if dry_run:
        print("\nDry run — датасет не изменён.")
        return

    save_dataset(clean)
    print(f"\nСохранено: {len(clean):,} пар")


# ─── Проход 2: LaBSE re-scoring ───────────────────────────────────────────────

def pass2(threshold: float, dry_run: bool):
    from sentence_transformers import SentenceTransformer

    rows = load_dataset()
    original_count = len(rows)

    # Разделяем на verse (пропускаем) и остальные (проверяем)
    verse_rows = [r for r in rows if r.get("source") in VERSE_SOURCES]
    check_rows = [r for r in rows if r.get("source") not in VERSE_SOURCES]

    print(f"Всего пар:         {original_count:,}")
    print(f"Verse (пропуск):   {len(verse_rows):,}")
    print(f"К проверке:        {len(check_rows):,}")

    print(f"\nЗагрузка lingtrain/labse-ingush...", file=sys.stderr)
    model = SentenceTransformer("lingtrain/labse-ingush")

    ing_sents = [r["ing"] for r in check_rows]
    rus_sents = [r["rus"] for r in check_rows]

    print("Эмбеддинг ингушских предложений...", file=sys.stderr)
    ing_emb = model.encode(ing_sents, batch_size=128, normalize_embeddings=True,
                           show_progress_bar=True)
    print("Эмбеддинг русских предложений...", file=sys.stderr)
    rus_emb = model.encode(rus_sents, batch_size=128, normalize_embeddings=True,
                           show_progress_bar=True)

    # Cosine similarity для каждой пары (поэлементно)
    scores = np.sum(ing_emb * rus_emb, axis=1)

    kept_check = []
    removed_by_source = Counter()
    score_dist = {"<0.20": 0, "0.20-0.25": 0, "0.25-0.30": 0,
                  "0.30-0.35": 0, "0.35-0.40": 0, ">=0.40": 0}

    for i, (row, score) in enumerate(zip(check_rows, scores)):
        s = float(score)
        if s < 0.20:      score_dist["<0.20"] += 1
        elif s < 0.25:    score_dist["0.20-0.25"] += 1
        elif s < 0.30:    score_dist["0.25-0.30"] += 1
        elif s < 0.35:    score_dist["0.30-0.35"] += 1
        elif s < 0.40:    score_dist["0.35-0.40"] += 1
        else:             score_dist[">=0.40"] += 1

        if s >= threshold:
            row["_score"] = round(s, 4)
            kept_check.append(row)
        else:
            removed_by_source[row.get("source", "?")] += 1

    print(f"\n=== Распределение score ===")
    for bucket, cnt in score_dist.items():
        bar = "#" * (cnt // 10)
        print(f"  {bucket:12s}: {cnt:5d}  {bar}")

    print(f"\n=== Удалено по источникам (score < {threshold}) ===")
    for src, cnt in removed_by_source.most_common(20):
        print(f"  {src:45s}: {cnt}")

    final = verse_rows + kept_check
    removed_total = original_count - len(final)

    print(f"\nБыло:    {original_count:,}")
    print(f"Стало:   {len(final):,}")
    print(f"Удалено: {removed_total:,} ({removed_total/original_count*100:.1f}%)")

    # Показать примеры удалённых
    print("\n--- Примеры удалённых пар (самые низкие score) ---")
    removed_examples = [(i, float(scores[i])) for i in range(len(check_rows))
                        if float(scores[i]) < threshold]
    removed_examples.sort(key=lambda x: x[1])
    for idx, score in removed_examples[:8]:
        r = check_rows[idx]
        print(f"  [{score:.3f}] [{r['source']}]")
        print(f"    ING: {r['ing'][:80]}")
        print(f"    RUS: {r['rus'][:80]}")

    if dry_run:
        print("\nDry run — датасет не изменён.")
        return

    # Убрать временный _score перед сохранением
    for row in final:
        row.pop("_score", None)

    save_dataset(final)
    print(f"\nСохранено: {len(final):,} пар")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pass1", action="store_true")
    group.add_argument("--pass2", action="store_true")
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.pass1:
        pass1(args.min_len, args.dry_run)
    elif args.pass2:
        pass2(args.threshold, args.dry_run)


if __name__ == "__main__":
    main()
