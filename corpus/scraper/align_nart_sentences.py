"""
Разбивка Нарт эпоса на предложения с помощью LaBSE.

Каждая секция уже выровнена (ing_i ↔ rus_i), поэтому делаем
ЛОКАЛЬНОЕ выравнивание внутри каждой пары — намного точнее глобального.

Pipeline:
  1. Читаем 148 section-level пар из датасета
  2. Для каждой пары: split → embed → DP align (local)
  3. Пары с score >= threshold добавляем в датасет с source "nartskij-epos-ingushej-2017"
  4. Старые section-level пары удаляем (заменяем на sentence-level)

Usage:
  python align_nart_sentences.py [--threshold 0.3] [--dry-run] [--keep-sections]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
MODEL_NAME = "lingtrain/labse-ingush"
OLD_SOURCE = "nartskij-epos-ingushej-2017"
NEW_SOURCE = "nartskij-epos-ingushej-2017"  # same source, но type="sentence"

# ─── Sentence splitting ────────────────────────────────────────────────────────

_SENT_END = re.compile(
    r'(?<=[^А-ЯA-Z\d])'
    r'[.!?…]+'
    r'(?=\s+[А-ЯA-ZЁ«"\u201C]|$)',
    re.UNICODE
)


def split_sentences(text: str) -> list[str]:
    text = text.replace('\xad', '')
    text = re.sub(r'-\n', '', text)
    text = text.replace('\f', '\n').replace('\r\n', '\n')
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        words = line.split()
        if not words:
            continue
        # Пропускаем заголовки секций (все заглавные, ≤ 8 слов)
        if len(words) <= 8 and line == line.upper() and any(c.isalpha() for c in line):
            continue
        cleaned.append(line)
    text = ' '.join(cleaned)
    parts = _SENT_END.split(text)
    sentences = [p.strip() for p in parts if len(p.strip()) > 10]
    return sentences


def extract_title(text: str) -> str | None:
    """Извлечь заголовок секции (первая строка если все заглавные)."""
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        words = line.split()
        if len(words) <= 8 and line == line.upper() and any(c.isalpha() for c in line):
            return line
        break
    return None


# ─── Embedding ────────────────────────────────────────────────────────────────

def embed(model, sentences: list[str]) -> np.ndarray:
    return model.encode(sentences, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=False)


# ─── DP alignment (local — внутри одной пары) ─────────────────────────────────

def dp_align(ing_emb: np.ndarray, rus_emb: np.ndarray,
             window: int = 6) -> list[tuple[int, int, float]]:
    N, M = len(ing_emb), len(rus_emb)
    sim = ing_emb @ rus_emb.T

    NEG_INF = -1e9
    dp = np.full((N + 1, M + 1), NEG_INF)
    dp[0][0] = 0.0
    back = np.full((N + 1, M + 1, 2), -1, dtype=int)

    ratio = M / max(N, 1)

    for i in range(1, N + 1):
        expected_j = i * ratio
        j_lo = max(1, int(expected_j - window))
        j_hi = min(M, int(expected_j + window) + 1)
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            if dp[i-1][j-1] > NEG_INF:
                score = dp[i-1][j-1] + sim[i-1][j-1]
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i-1, j-1]
            if dp[i-1][j] > NEG_INF:
                score = dp[i-1][j] - 0.05
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i-1, j]
            if dp[i][j-1] > NEG_INF:
                score = dp[i][j-1] - 0.05
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i, j-1]

    if dp[N][M] == NEG_INF:
        best_j = int(np.argmax(dp[N]))
        if dp[N][best_j] == NEG_INF:
            return []
        i, j = N, best_j
    else:
        i, j = N, M

    pairs = []
    while i > 0 or j > 0:
        pi, pj = int(back[i][j][0]), int(back[i][j][1])
        if pi < 0 or pj < 0:
            break
        if pi == i - 1 and pj == j - 1:
            pairs.append((i - 1, j - 1, float(sim[i-1][j-1])))
        i, j = pi, pj

    pairs.reverse()
    return pairs


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print stats but don't modify dataset")
    parser.add_argument("--keep-sections", action="store_true",
                        help="Оставить старые section-level пары (не удалять)")
    args = parser.parse_args()

    # ── Загрузить датасет
    all_rows = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            all_rows.append(json.loads(line))

    section_pairs = [r for r in all_rows if r["source"] == OLD_SOURCE and r.get("type") == "story"]
    other_rows = [r for r in all_rows if not (r["source"] == OLD_SOURCE and r.get("type") == "story")]

    print(f"Секций для разбивки: {len(section_pairs)}", file=sys.stderr)

    # ── Загрузить модель
    print(f"Загрузка {MODEL_NAME}...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    # ── Обработать каждую секцию
    new_pairs = []
    stats = {"sections": 0, "too_short": 0, "aligned": 0, "kept": 0, "title_pairs": 0}

    for row in section_pairs:
        stats["sections"] += 1
        ing_text = row["ing"]
        rus_text = row["rus"]

        # Заголовки — выравниваем отдельно как пару
        ing_title = extract_title(ing_text)
        rus_title = extract_title(rus_text)
        if ing_title and rus_title:
            new_pairs.append({
                "ing": ing_title,
                "rus": rus_title,
                "source": NEW_SOURCE,
                "type": "sentence",
            })
            stats["title_pairs"] += 1

        ing_sents = split_sentences(ing_text)
        rus_sents = split_sentences(rus_text)

        # Слишком короткая секция — берём как есть
        if len(ing_sents) < 2 or len(rus_sents) < 2:
            stats["too_short"] += 1
            # Уже добавили через title или добавим тело как одну пару
            body_ing = re.sub(r'^[А-ЯЁ\s\-–—]+\n', '', ing_text).strip()
            body_rus = re.sub(r'^[А-ЯЁ\s\-–—]+\n', '', rus_text).strip()
            if len(body_ing) > 20 and len(body_rus) > 20:
                new_pairs.append({
                    "ing": body_ing,
                    "rus": body_rus,
                    "source": NEW_SOURCE,
                    "type": "sentence",
                })
            continue

        # Embed + DP align
        ing_emb = embed(model, ing_sents)
        rus_emb = embed(model, rus_sents)
        aligned = dp_align(ing_emb, rus_emb, window=max(4, len(ing_sents) // 4))
        stats["aligned"] += len(aligned)

        kept = [(i, j, s) for i, j, s in aligned if s >= args.threshold]
        stats["kept"] += len(kept)

        for i, j, score in kept:
            new_pairs.append({
                "ing": ing_sents[i],
                "rus": rus_sents[j],
                "source": NEW_SOURCE,
                "type": "sentence",
            })

    # ── Отчёт
    print(f"\n=== Результат ===", file=sys.stderr)
    print(f"Секций обработано:    {stats['sections']}", file=sys.stderr)
    print(f"Коротких (≤1 предл.): {stats['too_short']}", file=sys.stderr)
    print(f"Заголовочных пар:     {stats['title_pairs']}", file=sys.stderr)
    print(f"Aligned итого:        {stats['aligned']}", file=sys.stderr)
    print(f"Kept (≥{args.threshold}):          {stats['kept']}", file=sys.stderr)
    print(f"Новых пар всего:      {len(new_pairs)}", file=sys.stderr)
    print(f"Было section-пар:     {len(section_pairs)}", file=sys.stderr)
    print(f"Прирост:              +{len(new_pairs) - len(section_pairs)}", file=sys.stderr)

    # ── Превью
    print("\n--- Примеры ---", file=sys.stderr)
    for row in new_pairs[:8]:
        print(f"  ING: {row['ing'][:80]}", file=sys.stderr)
        print(f"  RUS: {row['rus'][:80]}", file=sys.stderr)
        print(file=sys.stderr)

    if args.dry_run:
        print("Dry run — датасет не изменён.", file=sys.stderr)
        return

    # ── Записать в датасет
    if args.keep_sections:
        # Оставить старые + добавить новые
        final_rows = all_rows + new_pairs
    else:
        # Заменить section-level на sentence-level
        final_rows = other_rows + new_pairs

    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for row in final_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    action = "добавлены к" if args.keep_sections else "заменены в"
    print(f"\nГотово: {len(new_pairs)} пар {action} датасету ({len(final_rows)} всего).", file=sys.stderr)


if __name__ == "__main__":
    main()
