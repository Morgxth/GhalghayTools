"""
Извлекает пары «ингушское слово → русский перевод» из словаря Куркиева (2005).
Структура PDF: левая колонка — ингушские слова, правая — русские переводы (каждый с «—»).
"""

import fitz
import re
import json

PDF_PATH   = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Куркиев А.С. Ингушско-русский словарь (2005).pdf"
OUT_PATH   = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"
START_PAGE = 18


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def is_ingush_headword(word: str) -> bool:
    if len(word) < 2:
        return False
    if not re.search(r'[а-яёА-ЯЁӏ]', word):
        return False
    if re.search(r'[a-zA-Z]{2,}', word):
        return False
    return True


def extract_headwords_from_block(text: str) -> list[str]:
    """Извлекает все заголовочные слова из блока левой колонки."""
    words = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        # Заголовочное слово — первый токен строки до пробела/скобки
        m = re.match(r'^([а-яёА-ЯЁӏ][а-яёА-ЯЁӏъь\-]*)', line)
        if not m:
            continue
        word = m.group(1).strip('-')
        # Убираем цифры омонимов в конце: баьри1 → баьри
        word = re.sub(r'\d+$', '', word).lower()
        if is_ingush_headword(word) and len(word) >= 2:
            words.append(word)
    return words


def extract_translations_from_block(text: str) -> list[str]:
    """Разбивает блок правой колонки на отдельные переводы по символу '—'."""
    # Нормализуем разные виды тире
    text = text.replace('—', '—').replace('–', '—')
    parts = re.split(r'(?m)^—\s*', text)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Берём только первую строку (до переноса или скобки с пометой)
        first_line = part.split('\n')[0].strip()
        # Убираем пометы в скобках: (прил.), (гл.) и т.д.
        first_line = re.sub(r'\s*\([^)]{0,15}\)\s*$', '', first_line).strip()
        # Убираем мягкий перенос
        first_line = first_line.replace('\xad', '')
        # Обрезаем если слишком длинно
        if len(first_line) > 60:
            first_line = first_line[:60].rsplit(',', 1)[0].strip()
        if len(first_line) >= 2:
            result.append(first_line)
    return result


def extract_page(page: fitz.Page, mid: float) -> tuple[list[str], list[str]]:
    """Возвращает (заголовочные слова, переводы) для страницы."""
    # Собираем блоки, сортируем по вертикали
    left_blocks  = sorted(
        [(y0, text) for x0, y0, x1, y1, text, *_ in page.get_text("blocks") if x0 < mid],
        key=lambda b: b[0]
    )
    right_blocks = sorted(
        [(y0, text) for x0, y0, x1, y1, text, *_ in page.get_text("blocks") if x0 >= mid],
        key=lambda b: b[0]
    )

    headwords    = []
    translations = []

    for _, text in left_blocks:
        text = normalize_palochka(text)
        headwords.extend(extract_headwords_from_block(text))

    for _, text in right_blocks:
        translations.extend(extract_translations_from_block(text))

    return headwords, translations


def main():
    doc    = fitz.open(PDF_PATH)
    total  = doc.page_count
    result : dict[str, str] = {}

    for page_num in range(START_PAGE, total):
        page = doc[page_num]
        mid  = page.rect.width / 2

        headwords, translations = extract_page(page, mid)

        # Сопоставляем по порядку — у каждого слова свой перевод
        for word, tr in zip(headwords, translations):
            if word not in result:   # первое вхождение приоритетнее
                result[word] = tr

        if (page_num + 1 - START_PAGE) % 50 == 0:
            print(f"  Страниц: {page_num + 1 - START_PAGE}/{total - START_PAGE}, пар: {len(result)}")

    return result


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("Читаю PDF Куркиева...")
    translations = main()
    print(f"\nИзвлечено пар: {len(translations)}")

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {OUT_PATH}")

    print("\nПримеры:")
    for word, tr in list(translations.items())[200:220]:
        print(f"  {word:25s} -> {tr}")
