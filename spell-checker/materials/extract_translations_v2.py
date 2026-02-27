"""
Извлечение пар «ингушское слово → русский перевод» из словаря Куркиева (2005).

Подход: get_text("words") даёт позицию каждого слова на странице.
Это позволяет найти точный y каждого заголовочного слова и сопоставить его
с ближайшим блоком перевода из правой колонки.

Заголовочные слова — первые слова строки в левой колонке.
Переводы — текст в правой колонке, начинающийся с "— ".
"""

import fitz
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Куркиев А.С. Ингушско-русский словарь (2005).pdf"
OUT_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"
START_PAGE = 18

HEADWORD_RE = re.compile(r'^([а-яёА-ЯЁӏ][а-яёА-ЯЁӏъь\-]{1,})\d*$')


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def clean_headword(word: str) -> str:
    return re.sub(r'\d+$', '', word).lower().strip('-')


def clean_translation(tr: str) -> str:
    tr = tr.replace('\xad', '')
    tr = tr.split('\n')[0].split(';')[0]
    tr = re.sub(r'\s*\([^)]{1,25}\)\s*$', '', tr)
    return tr.strip().rstrip('.,')


def extract_page(page: fitz.Page, mid: float) -> dict[str, str]:
    # --- Заголовочные слова: первые слова каждой строки в левой колонке ---
    # get_text("words") -> (x0, y0, x1, y1, word, block_no, line_no, word_no)
    words_data = page.get_text("words")

    # Группируем слова по (block_no, line_no) чтобы найти word_no == 0
    headwords_with_y: list[tuple[float, str]] = []  # (y0, word)

    for x0, y0, x1, y1, word, block_no, line_no, word_no in words_data:
        if x0 >= mid:
            continue  # правая колонка — не заголовки
        if word_no != 0:
            continue  # не первое слово строки
        word = normalize_palochka(word)
        m = HEADWORD_RE.match(word)
        if not m:
            continue
        hw = clean_headword(m.group(1))
        if len(hw) >= 2:
            headwords_with_y.append((y0, hw))

    if not headwords_with_y:
        return {}

    # Сортируем по y
    headwords_with_y.sort(key=lambda x: x[0])

    # --- Переводы: блоки правой колонки, начинающиеся с "—" ---
    raw_blocks = page.get_text("blocks")
    right_translations: list[tuple[float, list[str]]] = []  # (y0, [tr1, tr2, ...])

    for x0, y0, x1, y1, text, *_ in raw_blocks:
        if x0 < mid:
            continue
        if not text.strip().startswith('—'):
            continue
        # Разбиваем блок на отдельные переводы
        parts = re.split(r'(?m)^—\s*', text)
        trs = []
        for part in parts:
            tr = clean_translation(part)
            if len(tr) >= 2:
                trs.append(tr)
        if trs:
            right_translations.append((y0, trs))

    if not right_translations:
        return {}

    # --- Сопоставление: для каждого блока переводов находим ближайшее ---
    # заголовочное слово ВЫШЕ (y_headword <= y_translation)
    hw_ys  = [h[0] for h in headwords_with_y]
    hw_words = [h[1] for h in headwords_with_y]

    result: dict[str, str] = {}

    for tr_y, trs in right_translations:
        # Ищем последний headword с y <= tr_y
        idx = None
        for i, hy in enumerate(hw_ys):
            if hy <= tr_y + 5:  # +5 pt допуск
                idx = i
            else:
                break

        if idx is None:
            continue

        # Назначаем переводы начиная с найденного headword
        for j, tr in enumerate(trs):
            hw_idx = idx + j
            if hw_idx >= len(hw_words):
                break
            word = hw_words[hw_idx]
            if word not in result:
                result[word] = tr

    return result


def main():
    doc = fitz.open(PDF_PATH)
    total = doc.page_count
    result: dict[str, str] = {}

    for page_num in range(START_PAGE, total):
        page = doc[page_num]
        mid = page.rect.width / 2
        page_result = extract_page(page, mid)
        for word, tr in page_result.items():
            if word not in result:
                result[word] = tr

        if (page_num + 1 - START_PAGE) % 50 == 0:
            done = page_num + 1 - START_PAGE
            print(f"  Страниц: {done}/{total - START_PAGE}, пар: {len(result)}")

    return result


if __name__ == '__main__':
    print("Читаю PDF Куркиева (v2)...")
    translations = main()
    print(f"\nИзвлечено пар: {len(translations)}")

    # Показываем сэмпл для проверки качества
    items = list(translations.items())
    print("\nПервые 40 пар:")
    for word, tr in items[:40]:
        print(f"  {word:25s} -> {tr}")

    print("\nСлова на 'аг' для проверки:")
    ag = [(w, t) for w, t in items if w.startswith('аг')]
    for word, tr in ag[:15]:
        print(f"  {word:25s} -> {tr}")

    save = input("\nСохранить в translations.json? (y/n): ").strip().lower()
    if save == 'y':
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: {OUT_PATH}")
    else:
        print("Не сохранено.")
