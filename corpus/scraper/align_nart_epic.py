"""
align_nart_epic.py — Выравнивание «Нартский эпос ингушей» (2017)

Структура книги:
  [~10k]    Предисловие, библиография
  [10852]   1. ДАРЗА-НАЬНА ВОРХӀ ВОЙ   ← начало ингушской части
  [547130]  1. СЕМЬ СЫНОВЕЙ ВЬЮГИ       ← начало русской части
  [1082000] Примечания, оглавление

Алгоритм:
  1. Делим текст на ингушскую и русскую половины
  2. В каждой половине извлекаем секции по номеру: "N. ЗАГОЛОВОК ... текст ..."
  3. Совмещаем по номеру → пара (ing, rus)
  4. Пишем в parallel_ing_rus.jsonl

Запуск:
    python align_nart_epic.py              # dry-run: статистика без записи
    python align_nart_epic.py --write      # записать результат
    python align_nart_epic.py --write --append  # дописать к существующему файлу
"""

import re
import json
import sys
import argparse
from pathlib import Path

CORPUS_DIR  = Path(__file__).parent.parent
TEXT_FILE   = CORPUS_DIR / "text" / "nartskij-epos-ingushej-sost-kodzoev-n-d-matiev-m-a-2017.txt"
OUT_FILE    = CORPUS_DIR / "dataset" / "parallel_ing_rus.jsonl"
SOURCE_SLUG = "nartskij-epos-ingushej-2017"

# Позиции начала каждой части (найдены вручную по анализу)
ING_START = 10852    # "1. ДАРЗА-НАЬНА ВОРХӀ ВОЙ"
RUS_START = 547130   # "1. СЕМЬ СЫНОВЕЙ ВЬЮГИ"
RUS_END   = 1082000  # конец русской части (до примечаний)


def extract_sections(text: str) -> dict[int, dict]:
    """
    Извлекает нумерованные секции из текста.
    Заголовок: строка вида "N. ТЕКСТ ЗАГОЛОВКА" (капслок или обычный).
    Возвращает {номер: {"title": ..., "body": ...}}
    """
    # Паттерн: начало строки, число, точка, пробел, непустой текст
    pattern = re.compile(
        r'(?:^|\n)(\d{1,3})\.\s+([^\n]{3,120})\n(.*?)(?=\n\d{1,3}\.\s+[^\n]{3}|\Z)',
        re.DOTALL
    )

    sections = {}
    for m in pattern.finditer(text):
        num   = int(m.group(1))
        title = m.group(2).strip()
        body  = m.group(3).strip()

        # Пропускаем если тело слишком короткое (скорее всего оглавление/сноска)
        if len(body) < 30:
            continue

        # Если номер уже есть — берём длиннее (основной текст длиннее оглавления)
        if num not in sections or len(body) > len(sections[num]["body"]):
            sections[num] = {"title": title, "body": body}

    return sections


def clean(text: str) -> str:
    """Базовая нормализация текста."""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def main():
    args = parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    print(f"Читаю файл: {TEXT_FILE.name}")
    full = TEXT_FILE.read_text(encoding='utf-8')
    print(f"Размер: {len(full):,} символов")

    ing_text = full[ING_START:RUS_START]
    rus_text = full[RUS_START:RUS_END]
    print(f"Ингушская часть: {len(ing_text):,} симв  |  Русская часть: {len(rus_text):,} симв")

    print("\nИзвлекаю секции...")
    ing_sections = extract_sections(ing_text)
    rus_sections = extract_sections(rus_text)
    print(f"  Ингушских: {len(ing_sections)}  |  Русских: {len(rus_sections)}")

    # Общие номера
    common = sorted(set(ing_sections) & set(rus_sections))
    only_ing = sorted(set(ing_sections) - set(rus_sections))
    only_rus = sorted(set(rus_sections) - set(ing_sections))
    print(f"  Совпадают по номеру: {len(common)}")
    if only_ing:
        print(f"  Только ингушские: {only_ing[:10]}{'...' if len(only_ing)>10 else ''}")
    if only_rus:
        print(f"  Только русские: {only_rus[:10]}{'...' if len(only_rus)>10 else ''}")

    # Показываем примеры
    print("\n--- Примеры пар ---")
    for n in common[:3]:
        i = ing_sections[n]
        r = rus_sections[n]
        print(f"\n#{n}. ING: {i['title']}")
        print(f"    {i['body'][:120].replace(chr(10),' ')}…")
        print(f"    RUS: {r['title']}")
        print(f"    {r['body'][:120].replace(chr(10),' ')}…")

    if not args.write:
        print(f"\n[dry-run] Будет записано {len(common)} пар. Запусти с --write для записи.")
        return

    # Собираем записи
    pairs = []
    for n in common:
        i = ing_sections[n]
        r = rus_sections[n]
        ing_full = clean(f"{i['title']}\n\n{i['body']}")
        rus_full = clean(f"{r['title']}\n\n{r['body']}")
        pairs.append({
            "ing":    ing_full,
            "rus":    rus_full,
            "source": SOURCE_SLUG,
            "type":   "story",
            "num":    n,
        })

    mode = "a" if args.append else "w"
    with open(OUT_FILE, mode, encoding='utf-8') as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    action = "Дописано" if args.append else "Записано"
    print(f"\n{action} {len(pairs)} пар → {OUT_FILE}")
    chars_ing = sum(len(p['ing']) for p in pairs)
    chars_rus = sum(len(p['rus']) for p in pairs)
    print(f"Символов (инг): {chars_ing:,}  |  символов (рус): {chars_rus:,}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--write',  action='store_true', help='Записать результат в файл')
    p.add_argument('--append', action='store_true', help='Дописать к существующему (не перезаписывать)')
    return p.parse_args()


if __name__ == "__main__":
    main()
