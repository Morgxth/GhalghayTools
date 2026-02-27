"""
Очистка ingush_translations.json в два прохода:
  1. Rule-based: убираем очевидный мусор без API
  2. API-based: Claude проверяет подозрительные пары батчами

Запуск:
  set ANTHROPIC_API_KEY=sk-ant-...
  python materials/clean_translations.py
"""

import json
import os
import re
import sys
import time

import anthropic

sys.stdout.reconfigure(encoding="utf-8")

TRANSLATIONS_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations.json"
OUTPUT_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_translations_clean.json"

# -------------------------------------------------------------------------
# Rule-based filters
# -------------------------------------------------------------------------

# Шаблон грамматических помет с базовым словом: "понуд. ф. от айхьаза (..."
# Допускаем ведущие символы "- ", "– " перед пометой
DERIVED_FORM_RE = re.compile(
    r"^[\-–\s]*(?:понуд|прич|деепр|масд|кратк|доп|сравн|превосх)[\.\s].*?от\s+([а-яёӏ\-]+)",
    re.IGNORECASE,
)

# Пометы без базового слова (например, просто "кратк. прил.")
BARE_GRAMMAR_RE = re.compile(
    r"^[\-–\s]*(?:понуд|прич|деепр|масд|кратк|доп|сравн|превосх)[\.\s]",
    re.IGNORECASE,
)


def resolve_derived(translation: str, all_translations: dict[str, str]) -> str | None:
    """
    Если перевод — грамматическая помета вида "понуд. ф. от базСлово",
    пытается вытащить перевод базового слова.
    Возвращает строку-перевод или None если база не найдена.
    """
    m = DERIVED_FORM_RE.search(translation)
    if not m:
        return None
    base = m.group(1).strip().lower()
    base_tr = all_translations.get(base)
    return base_tr  # None если нет в базе


def rule_based_clean(
    pairs: list[tuple[str, str]], all_translations: dict[str, str]
) -> tuple[dict, dict, dict]:
    """
    Returns:
      good    — пары, которые оставляем (включая восстановленные из производных)
      bad     — пары, которые удаляем
      suspect — пары для проверки через API
    """
    good: dict[str, str] = {}
    bad: dict[str, str] = {}
    suspect: dict[str, str] = {}

    for word, translation in pairs:
        # 1. Одинаковые слова — заимствования, перевод бесполезен
        if word.lower() == translation.lower():
            bad[word] = translation
            continue

        # 2. Грамматические производные — пробуем восстановить через базовое слово
        if DERIVED_FORM_RE.search(translation):
            resolved = resolve_derived(translation, all_translations)
            if resolved:
                good[word] = resolved  # заменяем помету на перевод базы
            else:
                bad[word] = translation  # база не найдена — удаляем
            continue

        # 3. Голые грамматические пометы без базового слова
        if BARE_GRAMMAR_RE.search(translation):
            bad[word] = translation
            continue

        # 4. Перевод слишком короткий (< 3 символов)
        if len(translation.strip()) < 3:
            bad[word] = translation
            continue

        # 5. Перевод содержит цифры — скорее всего OCR-мусор
        if re.search(r"\d", translation):
            bad[word] = translation
            continue

        # 6. Подозрительно длинный перевод (> 5 слов) — отдаём API
        if len(translation.split()) > 5:
            suspect[word] = translation
            continue

        # 7. Ингушское слово содержит латиницу (OCR-артефакт) — плохо
        if re.search(r"[a-zA-Z]", word):
            bad[word] = translation
            continue

        good[word] = translation

    return good, bad, suspect


# -------------------------------------------------------------------------
# API-based validation
# -------------------------------------------------------------------------

BATCH_SIZE = 50

SYSTEM_PROMPT = """Ты — эксперт по ингушскому языку. Тебе дают список пар:
  ингушское_слово -> русский_перевод

Для каждой пары ответь одной буквой:
  G = хороший перевод (оставить)
  B = плохой/неверный/мусор (удалить)
  S = похоже на заимствование из русского (слова звучат одинаково, перевод бесполезен)

Отвечай строго в формате JSON-массива, по одному символу на пару, например:
["G","B","G","S","G"]

Никаких объяснений — только JSON-массив."""


def validate_batch(client: anthropic.Anthropic, batch: list[tuple[str, str]]) -> list[str]:
    """Отправляет батч пар в API, возвращает список меток ['G','B','S',...]."""
    lines = "\n".join(f"{i+1}. {w} -> {t}" for i, (w, t) in enumerate(batch))
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": lines}],
    )
    raw = message.content[0].text.strip()
    # Извлекаем JSON-массив
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        print(f"  [WARN] Не удалось распарсить ответ: {raw[:100]}")
        return ["G"] * len(batch)  # при ошибке — оставляем
    labels = json.loads(match.group())
    if len(labels) != len(batch):
        print(f"  [WARN] Длина ответа {len(labels)} != {len(batch)}, оставляем всё")
        return ["G"] * len(batch)
    return labels


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Ошибка: ANTHROPIC_API_KEY не задан.")
        print("  Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    with open(TRANSLATIONS_PATH, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)

    print(f"Загружено пар: {len(data)}")

    pairs = list(data.items())
    good, bad, suspect = rule_based_clean(pairs, data)

    print(f"\nRule-based результаты:")
    print(f"  Хорошие:      {len(good)}")
    print(f"  Удалены:      {len(bad)}")
    print(f"  На проверку:  {len(suspect)}")

    print("\nПримеры удалённых:")
    for w, t in list(bad.items())[:10]:
        print(f"  {w:25s} -> {t}")

    print("\nПримеры на проверку через API:")
    for w, t in list(suspect.items())[:10]:
        print(f"  {w:25s} -> {t}")

    use_api = input(f"\nПроверить {len(suspect)} подозрительных через API? (y/n): ").strip().lower()
    if use_api != "y":
        final = good
        print("API-проверка пропущена.")
    else:
        client = anthropic.Anthropic(api_key=api_key)
        suspect_pairs = list(suspect.items())
        total_batches = (len(suspect_pairs) + BATCH_SIZE - 1) // BATCH_SIZE

        api_good: dict[str, str] = {}
        api_bad: dict[str, str] = {}

        print(f"\nОтправляем {total_batches} батчей по {BATCH_SIZE}...")
        for i in range(0, len(suspect_pairs), BATCH_SIZE):
            batch = suspect_pairs[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            print(f"  Батч {batch_num}/{total_batches}... ", end="", flush=True)

            try:
                labels = validate_batch(client, batch)
                for (w, t), label in zip(batch, labels):
                    if label == "G":
                        api_good[w] = t
                    else:
                        api_bad[w] = t
                print(f"G={labels.count('G')} B={labels.count('B')} S={labels.count('S')}")
            except Exception as e:
                print(f"ОШИБКА: {e}")
                # При ошибке — оставляем
                for w, t in batch:
                    api_good[w] = t

            time.sleep(0.3)  # небольшая пауза между запросами

        print(f"\nAPI: оставлено {len(api_good)}, удалено {len(api_bad)}")
        final = {**good, **api_good}

    print(f"\nИтог: {len(final)} пар (было {len(data)}, удалено {len(data) - len(final)})")

    preview = input("Сохранить очищенный файл? (y/n): ").strip().lower()
    if preview == "y":
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в: {OUTPUT_PATH}")
        print("Проверь файл, потом переименуй в ingush_translations.json")
    else:
        print("Не сохранено.")


if __name__ == "__main__":
    main()
