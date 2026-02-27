"""
Объединение текущего словаря (Куркиев 2005) с новым (ghalghay.github.io).
Фильтрация: только чистые кириллические слова без пробелов.
"""

import re
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES  = os.path.join(BASE, "src", "main", "resources", "dictionary")

CURRENT_WORDS  = os.path.join(RES, "ingush_words.txt")
CURRENT_TRANSL = os.path.join(RES, "ingush_translations.json")

NEW_WORDS  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghalghay_words.txt")
NEW_TRANSL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghalghay_translations.json")

# Допустимые символы в слове: кириллица + палочка + дефис
VALID_WORD = re.compile(r"^[а-яёӀӏ\-]+$")

def load_words(path):
    words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w and not w.startswith("#"):
                words.add(w.lower())
    return words

# ── Загрузка ──────────────────────────────────────────────────────────────────
print("Загружаю текущий словарь …")
current_words = load_words(CURRENT_WORDS)
print(f"  Текущий словарь:  {len(current_words):,} слов")

with open(CURRENT_TRANSL, encoding="utf-8") as f:
    current_transl = json.load(f)
print(f"  Текущие переводы: {len(current_transl):,}")

print("Загружаю новый словарь ghalghay …")
new_words_raw = load_words(NEW_WORDS)
with open(NEW_TRANSL, encoding="utf-8") as f:
    new_transl = json.load(f)
print(f"  Новый словарь:  {len(new_words_raw):,} слов")

# ── Фильтрация новых слов ─────────────────────────────────────────────────────
new_words_filtered = set()
skipped = 0
for w in new_words_raw:
    # Убираем: со пробелами, с дефисом в начале, слишком короткие
    if " " in w or w.startswith("-") or len(w) < 2:
        skipped += 1
        continue
    if not VALID_WORD.match(w):
        skipped += 1
        continue
    new_words_filtered.add(w)

print(f"  Новых после фильтра: {len(new_words_filtered):,} (отфильтровано: {skipped:,})")

# ── Мерж ──────────────────────────────────────────────────────────────────────
added_words = new_words_filtered - current_words
merged_words = current_words | new_words_filtered

added_transl = 0
for w, t in new_transl.items():
    if w not in current_transl and w in merged_words:
        current_transl[w] = t
        added_transl += 1

print(f"\nДобавлено новых слов:    {len(added_words):,}")
print(f"Добавлено переводов:      {added_transl:,}")
print(f"Итоговый словарь:         {len(merged_words):,} слов")

# ── Запись ────────────────────────────────────────────────────────────────────
merged_sorted = sorted(merged_words)

with open(CURRENT_WORDS, "w", encoding="utf-8") as f:
    f.write("# Ингушский словарь — Куркиев А.С. (2005) + ghalghay.github.io/doshlorg.html\n")
    f.write(f"# Слов: {len(merged_sorted)}\n")
    f.write("# Формат: одно слово на строку, нижний регистр\n")
    f.write("# Строки начинающиеся с # — комментарии\n")
    for w in merged_sorted:
        f.write(w + "\n")

with open(CURRENT_TRANSL, "w", encoding="utf-8") as f:
    json.dump(current_transl, f, ensure_ascii=False, indent=2)

print(f"\nСохранено в {CURRENT_WORDS}")
print(f"Сохранено в {CURRENT_TRANSL}")

# Примеры добавленных слов
print("\nПримеры добавленных слов:")
for w in sorted(added_words)[:20]:
    print(f"  {w:30s}  {current_transl.get(w, '—')}")
