"""
OCR для сканированных фразеологических словарей.
Извлекает ингушские слова и добавляет их в словарь.
Запуск: python3 ocr_dictionaries.py
"""

import fitz
import pytesseract
import re
import sys
import io
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_PREFIX = r"C:\Users\goygo\tessdata"
os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX

DICTIONARY_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"

SCANNED_PDFS = [
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Мерешков С.  Краткий Ингушско-русский  краткий фразеологический словарь. 2024 год..pdf",
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Оздоева Ф.Г. Ингушско-русский фразеологический словарь (2003).pdf",
]

SKIP_LINE = re.compile(
    r'^(\s*[-—\d]|д\.\s|прил\.|нареч\.|сущ\.|гл\.)',
    re.IGNORECASE
)


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def extract_words_from_text(text: str) -> set[str]:
    words = set()
    text = normalize_palochka(text)
    for line in text.split('\n'):
        line = line.strip()
        if not line or SKIP_LINE.match(line):
            continue
        # Берём все слова из строки (не только первое — фразеологизмы многословные)
        for word in re.findall(r'[а-яёӏА-ЯЁ][а-яёӏА-ЯЁ\-]*', line):
            word = word.lower().strip('-')
            if len(word) >= 2:
                words.add(word)
    return words


def ocr_pdf(pdf_path: str) -> set[str]:
    doc = fitz.open(pdf_path)
    all_words = set()
    total = doc.page_count

    # Пропускаем первые 3 страницы (обложка, титул)
    for page_num in range(3, total):
        page = doc[page_num]

        # Рендерим страницу в изображение с высоким разрешением
        mat = fitz.Matrix(2.5, 2.5)  # 2.5x = ~180 DPI → лучше для OCR
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # OCR с русским языком
        import os
        env = os.environ.copy()
        env['TESSDATA_PREFIX'] = TESSDATA_PREFIX
        config = r'--psm 6 -l rus'
        text = pytesseract.image_to_string(img, config=config, lang='rus')

        words = extract_words_from_text(text)
        all_words.update(words)

        if (page_num + 1) % 10 == 0:
            print(f"  Страница {page_num + 1}/{total}, слов найдено: {len(all_words)}")

    return all_words


def load_existing_words(path: str) -> set[str]:
    words = set()
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    words.add(line)
    except FileNotFoundError:
        pass
    return words


def append_new_words(path: str, new_words: set[str], existing: set[str], source: str):
    added = new_words - existing
    if not added:
        print(f"  Новых слов из {source}: 0")
        return 0

    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'\n# Добавлено из: {source}\n')
        for word in sorted(added):
            f.write(word + '\n')

    print(f"  Новых слов из {source}: {len(added)}")
    return len(added)


if __name__ == '__main__':
    print("Загружаю существующий словарь...")
    existing = load_existing_words(DICTIONARY_PATH)
    print(f"Слов в словаре: {len(existing)}")

    total_added = 0
    for pdf_path in SCANNED_PDFS:
        name = pdf_path.split('\\')[-1][:50]
        print(f"\nOCR: {name}...")
        words = ocr_pdf(pdf_path)
        print(f"Извлечено слов: {len(words)}")
        added = append_new_words(DICTIONARY_PATH, words, existing, name)
        existing.update(words)
        total_added += added

    print(f"\nГотово! Добавлено новых слов: {total_added}")
    print(f"Итого в словаре: {len(existing)}")
