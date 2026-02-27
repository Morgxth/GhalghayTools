"""
Извлекает ингушские слова из словаря Куркиева (2005).
Использует координаты PDF блоков чтобы брать только левую колонку (ингушские слова).
Запуск: python3 extract_words.py
"""

import fitz
import re

PDF_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Куркиев А.С. Ингушско-русский словарь (2005).pdf"
OUTPUT_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"

# Строки которые точно не слова
SKIP_PATTERNS = re.compile(
    r'^(\s*[-—]|д\.\s|д\.\s*т|ф\.\s|прил\.|нареч\.|сущ\.|гл\.|мест\.)',
    re.IGNORECASE
)


def normalize_palochka(text: str) -> str:
    """
    Нормализует все варианты палочки к единому символу ӏ (U+04CF).
    Палочка в разных документах встречается как:
      - ӏ (U+04CF) — правильный Unicode
      - Ӏ (U+04C0) — заглавная форма
      - 1 (цифра один) после согласных г, к, х, ч, т, п, б, д
      - I (латинская I) в аналогичных позициях
    """
    # U+04C0 → U+04CF
    text = text.replace('\u04c0', 'ӏ')
    # Латинская I после согласных → палочка
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    # Цифра 1 после согласных → палочка (только внутри слов)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def is_likely_ingush_word(word: str) -> bool:
    """Проверяет что слово похоже на ингушское (не русское)."""
    if len(word) < 2:
        return False
    if not re.search(r'[а-яёА-ЯЁӏ]', word):
        return False
    return True


def extract_headword(line: str) -> str | None:
    """Извлекает заголовочное слово из строки словарной статьи."""
    line = line.strip()

    if not line or SKIP_PATTERNS.match(line):
        return None

    match = re.match(r'^([^\s(,;—–]+)', line)
    if not match:
        return None

    word = match.group(1)
    word = word.strip('.,;:!?»«"\'")1234567890')
    word = word.rstrip('-')

    # Убираем нумерацию омонимов в конце: баьри1 → баьри
    word = re.sub(r'\d+$', '', word)

    return word if is_likely_ingush_word(word) else None


def get_page_midpoint(page: fitz.Page) -> float:
    """Возвращает горизонтальную середину страницы."""
    return page.rect.width / 2


def extract_from_pdf(pdf_path: str) -> set[str]:
    doc = fitz.open(pdf_path)
    words = set()
    total_pages = doc.page_count

    # Словарные статьи начинаются примерно со страницы 20
    START_PAGE = 18

    for page_num in range(START_PAGE, total_pages):
        page = doc[page_num]
        midpoint = get_page_midpoint(page)

        # Получаем блоки текста с координатами
        blocks = page.get_text("blocks")

        for block in blocks:
            x0, y0, x1, y1, text, *_ = block

            # Берём только левую половину страницы (ингушские слова)
            if x0 > midpoint:
                continue

            text = normalize_palochka(text)

            for line in text.split('\n'):
                word = extract_headword(line)
                if word:
                    words.add(word.lower())

        if (page_num + 1) % 50 == 0:
            print(f"  Обработано страниц: {page_num + 1 - START_PAGE}/{total_pages - START_PAGE}")

    return words


def save_wordlist(words: set[str], output_path: str):
    header = """\
# Ингушский словарь — извлечён из: Куркиев А.С. Ингушско-русский словарь (2005)
# Слов: {count}
# Формат: одно слово на строку, нижний регистр
# Строки начинающиеся с # — комментарии

""".format(count=len(words))

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header)
        for word in sorted(words):
            f.write(word + '\n')


if __name__ == '__main__':
    print("Читаю PDF...")
    words = extract_from_pdf(PDF_PATH)
    print(f"\nНайдено уникальных слов: {len(words)}")

    print("Сохраняю в словарь...")
    save_wordlist(words, OUTPUT_PATH)

    print(f"Готово! Файл: {OUTPUT_PATH}")

    # Показываем примеры
    sample = sorted(list(words))[:30]
    print(f"\nПервые 30 слов:")
    for w in sample:
        print(f"  {w}")
