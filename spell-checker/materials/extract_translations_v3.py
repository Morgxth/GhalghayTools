"""
Извлечение пар «ингушское слово → русский перевод» из словарей:
  - Барахоева и др. «Ингушско-русский словарь терминов» (2016)
  - Кодзоев «Астрономические термины» (2014)

Формат записей (одинаков в обоих):
  ингушское_слово (-формы) (класс) – русский перевод (пометы)

Разделитель: ' – ' (em-dash с пробелами).
Берём только первую строку перевода (для Кодзоева описания длинные).
Результат мержится с существующим ingush_translations.json (не перезаписывает).
"""

import fitz
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

TRANSLATIONS_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"

SOURCES = [
    {
        "name": "Барахоева (термины 2016)",
        "path": r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Ингушско-русский словарь терминов (сост. Барахоева Н.М., Кодзоев Н.Д., Хайров Б.А.) (2016).pdf",
        "start_page": 9,   # пропускаем введение
    },
    {
        "name": "Кодзоев (астрономия 2014)",
        "path": r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Кодзоев Н.Д. Астрономические термины (ингушско-русский и русско-ингушский словари) (2014).pdf",
        "start_page": 9,
        "stop_page": 100,  # вторая половина книги — русско-ингушский, нам не нужна
    },
]

# Пометы в конце перевода, которые убираем: (г.), (гос.), (рес.), (с.п.), (конт.) и т.д.
TRAILING_NOTES_RE = re.compile(r'\s*\([а-яёА-ЯЁ\.\s]{1,15}\)\s*$')


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def clean_headword(word: str) -> str:
    # Убираем цифры омонимов, приводим к нижнему регистру
    return re.sub(r'\d+$', '', word).lower().strip('-')


def clean_translation(tr: str) -> str:
    tr = tr.replace('\xad', '').strip()
    # Берём только до первой скобки с грамматической пометой
    # Но оставляем скобки с уточнениями типа "(Азия)", "(спутник Земли)"
    # Берём только первое предложение / до первого '('
    # → убираем только trailing notes в конце строки
    tr = TRAILING_NOTES_RE.sub('', tr).strip()
    # Обрезаем по точке с запятой или двойному пробелу
    tr = tr.split(';')[0].strip()
    # Убираем мягкий перенос
    tr = tr.replace('\xad', '').strip()
    return tr.rstrip('.,')


def extract_from_pdf(path: str, start_page: int, stop_page: int | None = None) -> dict[str, str]:
    doc = fitz.open(path)
    end = stop_page if stop_page else doc.page_count
    result: dict[str, str] = {}

    for page_num in range(start_page, min(end, doc.page_count)):
        text = normalize_palochka(doc[page_num].get_text())
        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Ищем разделитель ' – ' (em-dash с пробелами)
            if ' – ' not in line and ' - ' not in line:
                i += 1
                continue

            # Нормализуем: заменяем дефис с пробелами на em-dash
            line = line.replace(' - ', ' – ')

            # Может быть несколько альтернатив через '//'
            # Берём только первый вариант
            left_part = line.split(' – ')[0]
            right_parts = line.split(' – ', 1)
            if len(right_parts) < 2:
                i += 1
                continue

            right = right_parts[1]

            # Если перевод продолжается на следующей строке (оборванная строка)
            # — дополняем, но берём только первые ~80 символов
            if len(right.strip()) < 5 and i + 1 < len(lines):
                right += ' ' + lines[i + 1].strip()

            # Извлекаем ингушское слово (первый токен до скобки или пробела)
            # Игнорируем строки с цифрой страницы или латиницей
            left_clean = left_part.split('//')[0].strip()  # убираем альтернативы
            m = re.match(r'^([а-яёА-ЯЁӏIі][а-яёА-ЯЁӏIіъь\-]*)', left_clean)
            if not m:
                i += 1
                continue

            word = clean_headword(m.group(1))
            if len(word) < 2:
                i += 1
                continue

            tr = clean_translation(right)
            if len(tr) < 2:
                i += 1
                continue

            if word not in result:
                result[word] = tr

            i += 1

    return result


def main():
    # Загружаем существующие переводы
    try:
        with open(TRANSLATIONS_PATH, encoding='utf-8') as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = {}

    print(f"Существующих переводов: {len(existing)}")

    all_new: dict[str, str] = {}

    for src in SOURCES:
        print(f"\nОбрабатываю: {src['name']}...")
        extracted = extract_from_pdf(
            src['path'],
            src['start_page'],
            src.get('stop_page'),
        )
        print(f"  Извлечено: {len(extracted)} пар")

        # Показываем примеры
        print("  Примеры:")
        for word, tr in list(extracted.items())[:10]:
            print(f"    {word:30s} -> {tr}")

        # Мержим: новые не перезаписывают существующие
        for word, tr in extracted.items():
            if word not in existing and word not in all_new:
                all_new[word] = tr

    print(f"\nНовых пар (не было в базе): {len(all_new)}")

    if not all_new:
        print("Нечего добавлять.")
        return

    save = input("\nДобавить в translations.json? (y/n): ").strip().lower()
    if save == 'y':
        merged = {**existing, **all_new}
        with open(TRANSLATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print(f"Сохранено. Итого в базе: {len(merged)} пар")
    else:
        print("Не сохранено.")


if __name__ == '__main__':
    main()
