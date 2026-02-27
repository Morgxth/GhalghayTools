"""
OCR и извлечение данных из словаря Мерешкова (скан, 2024).

Это фразеологический словарь — большинство статей многословные.
Поэтому делаем два действия:
  1. Все ингушские слова из фраз → ingush_words.txt
  2. Однословные записи вида «слово. перевод.» → ingush_translations.json

Формат статей (по OCR):
  ИнгушскаяФраза. [Букв.: «...».] Русский перевод.
  (пример использования в скобках)

Палочка в OCR распознаётся как Г/г/ТI/I → нормализуем отдельно.
"""

import fitz
import pytesseract
import re
import json
import os
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ['TESSDATA_PREFIX'] = r"C:\Users\goygo\tessdata"

PDF_PATH        = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Мерешков С.  Краткий Ингушско-русский  краткий фразеологический словарь. 2024 год..pdf"
WORDS_PATH      = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"
TRANSLATIONS_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"

START_PAGE = 3  # пропускаем обложку/титул


# ---------------------------------------------------------------------------
# Нормализация палочки в OCR-тексте
# Tesseract читает ӏ как: Г, г, ТI, I (после согласных)
# ---------------------------------------------------------------------------
def normalize_palochka_ocr(text: str) -> str:
    # Стандартная нормализация
    text = text.replace('\u04C0', 'ӏ')
    # В OCR палочка часто появляется как "Г" после ингушских согласных
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])Г(?=[аеёиоуыьъяюАЕЁИОУЫЪЯЮ])',
                  'ӏ', text, flags=re.IGNORECASE)
    # Как "1" внутри слова
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёА-ЯЁ])', 'ӏ', text)
    # Как "I" (латинская) после согласных
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I(?=[а-яёА-ЯЁ])', 'ӏ', text)
    return text


def clean_ingush_word(word: str) -> str:
    word = re.sub(r'\d+$', '', word).lower().strip('-.,')
    return word


# ---------------------------------------------------------------------------
# Определяем: слово ингушское или русское?
# Эвристика: ингушские слова содержат характерные сочетания,
# или в словаре (но проще — просто собираем ВСЕ кириллические слова
# из ингушской части записи, т.е. до первого явно русского предложения)
# ---------------------------------------------------------------------------

# Слова, которые точно русские — по ним отсекаем начало перевода
RUSSIAN_MARKERS = re.compile(
    r'\b(Букв|букв|О\s+[а-я]|Как\s|Если\s|Когда\s|Во\s|В\s+[а-яё]{3,}|'
    r'Сделать|Будучи|Дружная|Смелый|Вороватый|Без\s|Прямо|Это\s|Сильную|'
    r'Доли|Сделай|От\s+[а-я]|Для\s)\b'
)


def split_entry(text: str) -> tuple[str, str]:
    """
    Разбивает запись на (ингушская_часть, русский_перевод).
    Ищем первый переход с Ingush на Russian.
    """
    # Разбиваем по предложениям (по точке + заглавная буква)
    sentences = re.split(r'(?<=\.)\s+', text.strip())
    ingush_parts = []
    russian_parts = []
    switched = False

    for sent in sentences:
        if switched:
            russian_parts.append(sent)
            continue
        # Если предложение начинается с русского маркера — это уже перевод
        if RUSSIAN_MARKERS.match(sent):
            switched = True
            russian_parts.append(sent)
        # Если содержит много строчных русских слов — вероятно перевод
        elif re.search(r'\b(это|как|без|от|во|в|с|и|а|но|для|при|на)\b', sent):
            switched = True
            russian_parts.append(sent)
        else:
            ingush_parts.append(sent)

    ingush = ' '.join(ingush_parts).strip()
    russian = ' '.join(russian_parts).strip()
    return ingush, russian


def extract_ingush_words(text: str) -> set[str]:
    """Извлекает ингушские слова из произвольного текста."""
    words = set()
    for w in re.findall(r'[а-яёӏА-ЯЁ][а-яёӏА-ЯЁ\-]{1,}', text):
        w = clean_ingush_word(w)
        if len(w) >= 2:
            words.add(w)
    return words


def ocr_page(page: fitz.Page) -> str:
    mat = fitz.Matrix(3.0, 3.0)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    text = pytesseract.image_to_string(img, lang='rus', config='--psm 6')
    return normalize_palochka_ocr(text)


def parse_entries(page_text: str) -> list[tuple[str, str]]:
    """
    Разбивает страницу на словарные статьи.
    Статьи разделены пустыми строками.
    Возвращает список (ингушская_часть, русский_перевод).
    """
    # Убираем заголовки секций (одиночные буквы на строке)
    page_text = re.sub(r'(?m)^\s*[А-ЯЁ][А-ЯЁ]?\s*$', '', page_text)

    blocks = re.split(r'\n{2,}', page_text.strip())
    entries = []
    for block in blocks:
        block = block.strip()
        if len(block) < 5:
            continue
        # Объединяем строки внутри блока (убираем переносы)
        block = re.sub(r'-\n', '', block)
        block = re.sub(r'\n', ' ', block)
        ingush, russian = split_entry(block)
        if ingush and russian:
            entries.append((ingush, russian))
    return entries


def is_single_word(text: str) -> str | None:
    """Если ингушская часть — одно слово, возвращает его, иначе None."""
    words = text.strip().rstrip('.').split()
    if len(words) == 1:
        w = clean_ingush_word(words[0])
        if len(w) >= 2:
            return w
    return None


def clean_translation(tr: str) -> str:
    # Убираем "Букв.: «...»." из перевода
    tr = re.sub(r'Букв\.:?\s*«[^»]+»\.?\s*', '', tr)
    # Берём первое предложение
    tr = tr.split('.')[0].strip()
    # Убираем скобки с примерами
    tr = re.sub(r'\s*\([^)]{10,}\)', '', tr).strip()
    return tr.rstrip('.,').strip()


# ---------------------------------------------------------------------------
# Основной поток
# ---------------------------------------------------------------------------
def main():
    doc = fitz.open(PDF_PATH)
    total = doc.page_count
    print(f"Страниц: {total}")

    all_ingush_words: set[str] = set()
    single_word_translations: dict[str, str] = {}

    for page_num in range(START_PAGE, total):
        page_text = ocr_page(doc[page_num])
        entries = parse_entries(page_text)

        for ingush_part, russian_part in entries:
            # Все ингушские слова в словарь
            words = extract_ingush_words(ingush_part)
            all_ingush_words.update(words)

            # Однословные записи — в переводы
            single = is_single_word(ingush_part)
            if single:
                tr = clean_translation(russian_part)
                if len(tr) >= 3 and single not in single_word_translations:
                    single_word_translations[single] = tr

        if (page_num + 1) % 10 == 0:
            print(f"  стр.{page_num + 1}/{total}  |  слов: {len(all_ingush_words)}  |  переводов: {len(single_word_translations)}")

    print(f"\nИтого:")
    print(f"  Ингушских слов из фраз: {len(all_ingush_words)}")
    print(f"  Однословных переводов:  {len(single_word_translations)}")

    # --- Слова → ingush_words.txt ---
    existing_words: set[str] = set()
    with open(WORDS_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                existing_words.add(line)

    new_words = all_ingush_words - existing_words
    print(f"\nНовых слов для словаря: {len(new_words)}")

    # --- Переводы → ingush_translations.json ---
    with open(TRANSLATIONS_PATH, encoding='utf-8') as f:
        existing_tr = json.load(f)

    new_tr = {k: v for k, v in single_word_translations.items()
              if k not in existing_tr}
    print(f"Новых переводов: {len(new_tr)}")

    if new_tr:
        print("\nПримеры переводов:")
        for w, t in list(new_tr.items())[:15]:
            print(f"  {w:25s} -> {t}")

    save = input("\nСохранить? (y/n): ").strip().lower()
    if save == 'y':
        with open(WORDS_PATH, 'a', encoding='utf-8') as f:
            f.write('\n# Мерешков (фразеологический словарь, 2024)\n')
            for w in sorted(new_words):
                f.write(w + '\n')

        merged_tr = {**existing_tr, **new_tr}
        with open(TRANSLATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged_tr, f, ensure_ascii=False, indent=2)

        print(f"Слов в словаре: {len(existing_words) + len(new_words)}")
        print(f"Переводов в базе: {len(merged_tr)}")
    else:
        print("Не сохранено.")


if __name__ == '__main__':
    main()
