"""
Извлечение данных из «Русско-ингушского словаря антонимов» Тариевой (2017).

Словарь русско-ингушский, но в каждой статье есть ингушский эквивалент
с грамматической пометой. Разворачиваем: ИнгушскоеСлово → РусскийЗаголовок.

Формат блока:
  Русское слово (прил.) –            ← русский заголовок
  русское определение...
  пример.
  ИнгушскоеСлово (белг.) –          ← ингушский эквивалент
  ингушское определение...

Русские пометы:  (прил.), (сущ.), (нареч.), (гл.) и т.д.
Ингушские пометы: (белг.), (цIерд.), (куцд.), (глг.) и т.д.
"""

import fitz
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH          = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Тариева Л.У. Русско-ингушский словарь антонимов (2017).pdf"
WORDS_PATH        = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"
TRANSLATIONS_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"

START_PAGE = 22  # пропускаем введение

# Ингушские грамматические пометы
INGUSH_POS_RE = re.compile(
    r'^(.+?)\s*\((белг|цIерд|куцд|глг|хьехам|вешт|дош|сIалам|цIерметд)[\.\)]',
    re.MULTILINE
)

# Русские грамматические пометы
RUSSIAN_POS_RE = re.compile(
    r'^([А-ЯЁа-яё][А-ЯЁа-яё\s\-]+?)\s*\((прил|сущ|нареч|гл|межд|числ|мест|кратк|предл)[\.\)]',
    re.MULTILINE
)


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04C0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    return text


def clean_word(word: str) -> str:
    return re.sub(r'\d+$', '', word).lower().strip('-., ')


def extract_ingush_words(text: str) -> set[str]:
    """Все ингушские слова из произвольного текста (только кириллица + ӏ)."""
    words = set()
    for w in re.findall(r'[а-яёӏА-ЯЁ][а-яёӏА-ЯЁ\-]{1,}', text):
        w = clean_word(w)
        if len(w) >= 2:
            words.add(w)
    return words


def process_block(block_text: str) -> list[tuple[str, str]]:
    """
    Извлекает пары (ингушское_слово, русский_перевод) из одного блока.
    В блоке может быть несколько пар.
    """
    block_text = normalize_palochka(block_text)
    pairs = []

    # Ищем все русские заголовки в блоке
    russian_matches = list(RUSSIAN_POS_RE.finditer(block_text))
    # Ищем все ингушские заголовки в блоке
    ingush_matches = list(INGUSH_POS_RE.finditer(block_text))

    # Для каждого ингушского заголовка ищем предшествующий русский
    for ing_m in ingush_matches:
        ing_word_raw = ing_m.group(1).strip()
        ing_pos_start = ing_m.start()

        # Последний русский заголовок ДО этого ингушского
        best_rus = None
        for rus_m in russian_matches:
            if rus_m.start() < ing_pos_start:
                best_rus = rus_m
            else:
                break

        if best_rus is None:
            continue

        rus_word = best_rus.group(1).strip()
        # Берём только первое слово русского заголовка (без составных)
        rus_first = rus_word.split()[0].lower()

        # Ингушский заголовок может быть фразой (напр. "Сий дола")
        # Добавляем каждое слово, но в переводы кладём только однословные
        ing_words = ing_word_raw.strip().split()

        for iw in ing_words:
            cw = clean_word(iw)
            if len(cw) >= 2:
                pairs.append((cw, rus_first))

    return pairs


def main():
    doc = fitz.open(PDF_PATH)
    total = doc.page_count
    print(f"Страниц: {total}, обрабатываем с {START_PAGE+1}")

    all_ingush_words: set[str] = set()
    translation_candidates: dict[str, list[str]] = {}  # слово → [русские варианты]

    for page_num in range(START_PAGE, total):
        page = doc[page_num]
        blocks = page.get_text("blocks")

        for x0, y0, x1, y1, text, *_ in blocks:
            text = text.strip()
            if len(text) < 10:
                continue

            # Слова для словаря — из ВСЕГО блока
            all_ingush_words.update(extract_ingush_words(normalize_palochka(text)))

            # Пары только из блоков, где есть обе пометы
            if re.search(r'\((?:белг|цIерд|куцд|глг)', text):
                pairs = process_block(text)
                for ing_word, rus_word in pairs:
                    if ing_word not in translation_candidates:
                        translation_candidates[ing_word] = []
                    if rus_word not in translation_candidates[ing_word]:
                        translation_candidates[ing_word].append(rus_word)

    # Берём наиболее частый перевод для каждого слова
    translations: dict[str, str] = {}
    for word, candidates in translation_candidates.items():
        # Самый частый вариант
        best = max(set(candidates), key=candidates.count)
        translations[word] = best

    print(f"\nИзвлечено ингушских слов:  {len(all_ingush_words)}")
    print(f"Пар слово→перевод:         {len(translations)}")

    # --- Новые слова ---
    existing_words: set[str] = set()
    with open(WORDS_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                existing_words.add(line)

    new_words = all_ingush_words - existing_words
    print(f"Новых слов для словаря:    {len(new_words)}")

    # --- Новые переводы ---
    with open(TRANSLATIONS_PATH, encoding='utf-8') as f:
        existing_tr = json.load(f)

    new_tr = {k: v for k, v in translations.items() if k not in existing_tr}
    print(f"Новых переводов:           {len(new_tr)}")

    print("\nПримеры переводов:")
    for w, t in list(new_tr.items())[:20]:
        print(f"  {w:25s} -> {t}")

    save = input("\nСохранить? (y/n): ").strip().lower()
    if save == 'y':
        with open(WORDS_PATH, 'a', encoding='utf-8') as f:
            f.write('\n# Тариева (русско-ингушский словарь антонимов, 2017)\n')
            for w in sorted(new_words):
                f.write(w + '\n')

        merged = {**existing_tr, **new_tr}
        with open(TRANSLATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        print(f"Сохранено. Слов: {len(existing_words)+len(new_words)}, переводов: {len(merged)}")
    else:
        print("Не сохранено.")


if __name__ == '__main__':
    main()
