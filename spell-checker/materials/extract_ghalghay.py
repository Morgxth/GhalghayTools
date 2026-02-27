"""
Извлечение ингушских слов и переводов из словаря ghalghay.github.io/doshlorg.html
Источник: https://ghalghay.github.io/src/data.js

Формат записи:
  {"a": "<kod18>...", "b": "<li><b>слово</b> <m>(~аш)</m> <c>(д)</c>", "c": "грам.пометы", "d": "<li>перевод", "e": "тема"}

Поля:
  b — ингушское слово (заголовочная форма)
  c — грамматические пометы (часть речи и т.д.)
  d — перевод/определение на русском
"""

import re
import json
import urllib.request
import os

DATA_URL = "https://ghalghay.github.io/src/data.js"
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
WORDS_FILE       = os.path.join(OUT_DIR, "ghalghay_words.txt")
TRANSL_FILE      = os.path.join(OUT_DIR, "ghalghay_translations.json")

# ── Загрузка ──────────────────────────────────────────────────────────────────
print("Загружаю data.js …")
with urllib.request.urlopen(DATA_URL) as resp:
    raw = resp.read().decode("utf-8-sig")

# Убираем JS-обёртку: "var allData = [ … ];"
raw = raw.strip()
if raw.startswith("var allData"):
    raw = raw[raw.index("["):]
if raw.endswith(";"):
    raw = raw[:-1]

print(f"Размер данных: {len(raw):,} байт")

# data.js — JS-массив с невалидным JSON: \{ \}, trailing comma.
# Парсим построчно: каждая строка содержит один объект {...},
data = []
ENTRY_RE = re.compile(r"^\s*(\{.*\}),?\s*$")
for line in raw.splitlines():
    m = ENTRY_RE.match(line)
    if m:
        obj_str = m.group(1)
        # Исправляем невалидные экранирования \{ и \}
        obj_str = obj_str.replace(r"\{", "{").replace(r"\}", "}")
        try:
            data.append(json.loads(obj_str))
        except json.JSONDecodeError:
            pass  # пропускаем битые строки

print(f"Записей: {len(data):,}")


# ── Утилиты очистки HTML ──────────────────────────────────────────────────────
TAG_RE  = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

def strip_html(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    s = s.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return SPACE_RE.sub(" ", s).strip()

# Регулярка для вытаскивания заголовочного слова из поля b.
# Слово — первый <b>…</b> в строке.
HEADWORD_RE = re.compile(r"<b>([^<]+)</b>")

# Убираем скобочные пометы: (сущ.), (глаг.), (~наш) и т.д.
PARENS_RE = re.compile(r"\([^)]*\)")
TILDE_RE  = re.compile(r"[{}\[\]<>]")

def clean_word(raw_b: str) -> str | None:
    """Извлекаем чистую заголовочную форму слова из поля b."""
    m = HEADWORD_RE.search(raw_b)
    if not m:
        return None
    w = m.group(1).strip()
    # Убираем HTML-сущности, скобки, тильды
    w = strip_html(w)
    w = PARENS_RE.sub("", w).strip()
    w = TILDE_RE.sub("", w).strip()
    # Убираем цифровые надстрочные индексы: слово¹ → слово
    w = re.sub(r"[\u00B9\u00B2\u00B3\u2070-\u2079]", "", w)
    # Убираем метки ударения (знак акцента) и похожие диакритики
    w = re.sub(r"[\u0300-\u036f\u0301\u0300\u0306]", "", w)
    # Нормализуем пробелы, берём первое слово если их несколько
    # (Некоторые записи содержат варианты через / или ,)
    parts = re.split(r"[,/]", w)
    w = parts[0].strip()
    # Должны остаться только кириллица + пробелы + палочка
    w = re.sub(r"[^\u0400-\u04FF\u04CF\s\-]", "", w).strip().lower()
    if len(w) < 2:
        return None
    return w

def clean_translation(raw_d: str) -> str:
    """Извлекаем первое значение из поля d (русский перевод)."""
    t = strip_html(raw_d)
    # Берём первый пункт (до следующего «•» или цифры с точкой)
    t = re.split(r"\d+\.", t)[0].strip()
    # Убираем скобки с уточнениями вида (мед.), (уст.) и т.д.
    t = PARENS_RE.sub("", t).strip()
    # Убираем курсив-примеры в квадратных скобках
    t = re.sub(r"\[.*?\]", "", t).strip()
    # Чистим артефакты
    t = SPACE_RE.sub(" ", t).strip(" .,;:")
    return t if len(t) > 1 else ""


# ── Основной проход ───────────────────────────────────────────────────────────
words_set:    set[str]          = set()
translations: dict[str, str]   = {}

skip_no_word = 0
skip_too_short = 0

for entry in data:
    raw_b = entry.get("b", "")
    raw_d = entry.get("d", "")

    word = clean_word(raw_b)
    if not word:
        skip_no_word += 1
        continue
    if len(word) < 2:
        skip_too_short += 1
        continue

    words_set.add(word)

    # Перевод берём только если поле d содержит русский текст (кириллица)
    if word not in translations and raw_d:
        t = clean_translation(raw_d)
        if t and re.search(r"[а-яёА-ЯЁ]", t):
            translations[word] = t

print(f"\nУникальных словоформ: {len(words_set):,}")
print(f"Слов с переводами:    {len(translations):,}")
print(f"Пропущено (нет слова):      {skip_no_word:,}")
print(f"Пропущено (слишком короткое): {skip_too_short:,}")

# ── Запись ────────────────────────────────────────────────────────────────────
words_sorted = sorted(words_set)

with open(WORDS_FILE, "w", encoding="utf-8") as f:
    f.write("# Словарь ингушского языка. Источник: ghalghay.github.io/doshlorg.html\n")
    f.write(f"# Записей: {len(words_sorted)}\n")
    for w in words_sorted:
        f.write(w + "\n")

with open(TRANSL_FILE, "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, indent=2)

print(f"\nСохранено:")
print(f"  Слова:    {WORDS_FILE}")
print(f"  Переводы: {TRANSL_FILE}")

# ── Примеры ───────────────────────────────────────────────────────────────────
print("\nПервые 20 слов:")
for w in words_sorted[:20]:
    print(f"  {w:30s}  {translations.get(w, '(нет перевода)')}")
