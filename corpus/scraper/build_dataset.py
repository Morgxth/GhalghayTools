"""
build_dataset.py — Сборка датасетов для обучения моделей

Из corpus/text/ собирает два датасета:

1. ingush_mono.jsonl     — монолингвальный ингушский корпус
   Для: Phi-3.5 Mini (language modeling, генерация упражнений)
   Формат: {"text": "...", "source": "slug", "category": "...", "lang_score": 0.9}

2. parallel_ing_rus.jsonl — параллельные пары ингушский↔русский
   Для: NLLB-200 1.3B fine-tuning (перевод)
   Формат: {"ing": "...", "rus": "...", "source": "slug", "type": "sentence"}

Запуск:
    python build_dataset.py
    python build_dataset.py --stats-only   # только статистика без записи
"""

import re
import json
import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

CORPUS_DIR   = Path(__file__).parent.parent
TEXT_DIR     = CORPUS_DIR / "text"
CATALOG_FILE = CORPUS_DIR / "catalog.jsonl"
DATASET_DIR  = CORPUS_DIR / "dataset"
STATE_FILE   = CORPUS_DIR / "extract_state.jsonl"

SPELL_DIR    = CORPUS_DIR.parent / "spell-checker"
DICT_SOURCES = [
    # инг→рус, 30k записей (doshlorg.html)
    SPELL_DIR / "materials" / "ghalghay_translations.json",
    # инг→рус, 21k записей (spell-checker)
    SPELL_DIR / "src" / "main" / "resources" / "dictionary" / "ingush_translations.json",
]

# Минимальная длина сегмента (символов)
MIN_SEGMENT_CHARS = 30
# Максимальная длина сегмента (токенов ~= символов/4)
MAX_SEGMENT_CHARS = 2000

# Порог «ингушскости» — доля ингушских маркеров в тексте
INGUSH_SCORE_THRESHOLD = 0.05

# ---------------------------------------------------------------------------
# Определение языка (простое, без langdetect)
# ---------------------------------------------------------------------------

# Ингушские фонетические маркеры — комбинации, характерные только для ингушского
INGUSH_MARKERS = re.compile(
    r'гӏ|кӏ|хӏ|тӏ|пӏ|цӏ|чӏ|бӏ|дӏ|зӏ|лӏ|нӏ|рӏ|сӏ|фӏ|вӏ|'
    r'хьа|хьо|хьу|хьи|'
    r'аьн|еьн|оьн|уьн|'
    r'ӏал|ӏер|ӏаь|ӏун|'
    r'гӀ|кӀ|хӀ|тӀ|пӀ|цӀ|чӀ',
    re.IGNORECASE
)

CYRILLIC = re.compile(r'[а-яёА-ЯЁ]')

def ingush_score(text: str) -> float:
    """
    Возвращает долю ингушских маркеров среди кириллических слов.
    0.0 = чистый русский, 1.0 = очень насыщенный ингушский.
    """
    cyr_words = re.findall(r'[а-яёӏА-ЯЁӀ]{2,}', text)
    if not cyr_words:
        return 0.0
    marker_count = sum(1 for w in cyr_words if INGUSH_MARKERS.search(w))
    return marker_count / len(cyr_words)


def classify_segment(text: str) -> str:
    """
    Классифицирует сегмент: 'ing' | 'rus' | 'mixed' | 'other'
    """
    score = ingush_score(text)
    cyr_ratio = len(CYRILLIC.findall(text)) / max(len(text), 1)

    if cyr_ratio < 0.3:
        return "other"
    if score >= 0.25:
        return "ing"
    if score >= 0.05:
        return "mixed"
    return "rus"


# ---------------------------------------------------------------------------
# Сегментация текста
# ---------------------------------------------------------------------------

def split_into_segments(text: str, max_chars: int = MAX_SEGMENT_CHARS) -> list[str]:
    """
    Разбивает текст на сегменты по абзацам.
    Мелкие абзацы склеивает, крупные режет по предложениям.
    """
    # Разбиваем на параграфы
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    segments = []
    current = ""

    for para in paragraphs:
        if len(para) < MIN_SEGMENT_CHARS:
            continue

        # Очень длинный параграф — режем по предложениям
        if len(para) > max_chars:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sent in sentences:
                if len(sent) < MIN_SEGMENT_CHARS:
                    continue
                if len(current) + len(sent) < max_chars:
                    current += (" " if current else "") + sent
                else:
                    if current:
                        segments.append(current.strip())
                    current = sent
            continue

        # Обычный параграф — склеиваем пока влезает
        if len(current) + len(para) < max_chars:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                segments.append(current.strip())
            current = para

    if current:
        segments.append(current.strip())

    return segments


# ---------------------------------------------------------------------------
# Загрузка словарных пар из JSON-файлов
# ---------------------------------------------------------------------------

def load_dict_pairs(stats_only: bool = False) -> list[dict]:
    """
    Загружает инг->рус пары из готовых JSON-словарей.
    Формат файлов: {"ингушское_слово": "русский_перевод", ...}
    Дедуплицирует по ингушскому ключу (первый источник приоритетен).
    """
    seen: dict[str, str] = {}  # ing -> rus
    source_counts: dict[str, int] = {}

    for dict_path in DICT_SOURCES:
        if not dict_path.exists():
            logging.warning(f"  Словарь не найден: {dict_path}")
            continue
        try:
            data = json.loads(dict_path.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning(f"  Ошибка чтения {dict_path.name}: {e}")
            continue

        source_name = dict_path.stem
        added = 0
        for ing_word, rus_trans in data.items():
            ing_word = ing_word.strip()
            rus_trans = rus_trans.strip() if isinstance(rus_trans, str) else str(rus_trans).strip()
            if not ing_word or not rus_trans:
                continue
            if ing_word not in seen:
                seen[ing_word] = rus_trans
                added += 1

        source_counts[source_name] = added
        logging.info(f"  {source_name[:50]:<50} {added:>6} пар")

    logging.info(f"  Итого уникальных пар: {len(seen)}")

    if stats_only:
        return []

    pairs = []
    for ing_word, rus_trans in seen.items():
        pairs.append({
            "ing": ing_word,
            "rus": rus_trans,
            "source": "dictionary",
            "type": "word_pair",
        })
    return pairs


# ---------------------------------------------------------------------------
# Построение монолингвального датасета
# ---------------------------------------------------------------------------

@dataclass
class MonoRecord:
    text: str
    source: str
    category: str
    lang_score: float
    chars: int


def build_mono_dataset(
    text_files: list[tuple[Path, dict]],
    stats_only: bool = False,
) -> list[dict]:
    records = []
    file_stats = {}

    for txt_path, meta in text_files:
        slug     = txt_path.stem
        category = meta.get("category_slug", "unknown")

        try:
            text = txt_path.read_text(encoding="utf-8")
        except Exception as e:
            logging.warning(f"  Не могу прочитать {txt_path.name}: {e}")
            continue

        segments = split_into_segments(text)
        good = 0

        for seg in segments:
            lang  = classify_segment(seg)
            score = ingush_score(seg)

            if lang in ("ing", "mixed") and score >= INGUSH_SCORE_THRESHOLD:
                if not stats_only:
                    records.append({
                        "text": seg,
                        "source": slug,
                        "category": category,
                        "lang": lang,
                        "lang_score": round(score, 3),
                        "chars": len(seg),
                    })
                good += 1

        file_stats[slug] = {"total": len(segments), "ingush": good, "category": category}
        if good > 0:
            logging.info(f"  {slug[:50]:<50} {good:>4}/{len(segments)} сегм.")

    return records, file_stats


# ---------------------------------------------------------------------------
# Построение параллельного датасета
# ---------------------------------------------------------------------------

def build_parallel_dataset(
    text_files: list[tuple[Path, dict]],
    stats_only: bool = False,
) -> list[dict]:
    """
    Собирает параллельные пары двумя способами:
    1. JSON-словари (word_pair) — из DICT_SOURCES (~31k чистых пар инг->рус)
    2. Смежные абзацы ing+rus (bilingual_para) — из двуязычных текстов корпуса
    """
    pairs = []

    # Метод 1: готовые JSON-словари
    logging.info("  [Dict] Загрузка JSON-словарей:")
    dict_pairs = load_dict_pairs(stats_only)
    pairs.extend(dict_pairs)

    # Метод 2: смежные абзацы рус+инг в двуязычных текстах
    logging.info("  [Corpus] Поиск bilingual параграфов в текстах:")
    for txt_path, meta in text_files:
        slug = txt_path.stem

        try:
            text = txt_path.read_text(encoding="utf-8")
        except Exception:
            continue

        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > MIN_SEGMENT_CHARS]
        i = 0
        bilingual_count = 0
        while i < len(paragraphs) - 1:
            p1 = paragraphs[i]
            p2 = paragraphs[i + 1]
            l1 = classify_segment(p1)
            l2 = classify_segment(p2)

            if (l1 == "ing" and l2 == "rus") or (l1 == "rus" and l2 == "ing"):
                ing = p1 if l1 == "ing" else p2
                rus = p1 if l1 == "rus" else p2

                ratio = len(ing) / max(len(rus), 1)
                if 0.4 < ratio < 2.5:
                    if not stats_only:
                        pairs.append({
                            "ing": ing,
                            "rus": rus,
                            "source": slug,
                            "type": "bilingual_para",
                        })
                    bilingual_count += 1
                    i += 2
                    continue
            i += 1

        if bilingual_count > 0:
            logging.info(f"    BILIN {slug[:44]:<44} {bilingual_count:>4} пар")

    return pairs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Сборка датасетов из корпуса")
    p.add_argument("--stats-only", action="store_true",
                   help="Только статистика, не писать файлы")
    return p.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    # Загружаем каталог
    catalog: dict[str, dict] = {}
    with open(CATALOG_FILE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            catalog[r["slug"]] = r

    # Загружаем список успешно извлечённых файлов
    ok_slugs: set[str] = set()
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["status"].startswith("ok"):
                    ok_slugs.add(d["slug"])

    # Собираем список (path, meta) в порядке приоритета
    text_files: list[tuple[Path, dict]] = []
    for slug in ok_slugs:
        txt = TEXT_DIR / f"{slug}.txt"
        if txt.exists() and txt.stat().st_size > 100:
            meta = catalog.get(slug, {"category_slug": "unknown", "priority": 9})
            text_files.append((txt, meta))

    # Сортировка: приоритет 1, потом по размеру файла (крупные словари вперёд)
    text_files.sort(key=lambda x: (
        x[1].get("priority", 9),
        -x[0].stat().st_size,
    ))

    logging.info(f"Файлов для обработки: {len(text_files)}")
    logging.info(f"{'='*55}")

    # --- Монолингвальный датасет ---
    logging.info("\n[1/2] МОНОЛИНГВАЛЬНЫЙ датасет (ингушский текст)")
    logging.info("-" * 55)
    mono_records, mono_stats = build_mono_dataset(text_files, args.stats_only)

    mono_total_chars = sum(r["chars"] for r in mono_records)
    logging.info(f"\n  Итого сегментов: {len(mono_records)}")
    logging.info(f"  Суммарно символов: {mono_total_chars:,} (~{mono_total_chars//1000} тыс.)")

    if not args.stats_only and mono_records:
        mono_path = DATASET_DIR / "ingush_mono.jsonl"
        with open(mono_path, "w", encoding="utf-8") as f:
            for r in mono_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logging.info(f"  Сохранено: {mono_path} ({mono_path.stat().st_size // 1024} KB)")

    # --- Параллельный датасет ---
    logging.info(f"\n[2/2] ПАРАЛЛЕЛЬНЫЙ датасет (инг <-> рус)")
    logging.info("-" * 55)
    para_records = build_parallel_dataset(text_files, args.stats_only)

    logging.info(f"\n  Итого пар: {len(para_records)}")
    by_type = {}
    for r in para_records:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    for t, n in sorted(by_type.items()):
        logging.info(f"    {t}: {n}")

    if not args.stats_only and para_records:
        para_path = DATASET_DIR / "parallel_ing_rus.jsonl"
        with open(para_path, "w", encoding="utf-8") as f:
            for r in para_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logging.info(f"  Сохранено: {para_path} ({para_path.stat().st_size // 1024} KB)")

    # --- Итоговый отчёт ---
    logging.info(f"\n{'='*55}")
    logging.info("ИТОГ:")
    logging.info(f"  ingush_mono.jsonl      : {len(mono_records):>6} сегментов  (~{mono_total_chars//1_000_000:.1f}M символов)")
    logging.info(f"  parallel_ing_rus.jsonl : {len(para_records):>6} пар")


if __name__ == "__main__":
    main()
