"""
Импорт параллельных пар с ghalghay.github.io/src_parall/data.js

Структура: allData = [{b: инг_html, d: рус_html, e: источник}, ...]
Ингушский в поле "b", русский в "d", источник в "e".

Теги убираем, заголовочные строки (h4) пропускаем.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_URL    = "https://ghalghay.github.io/src_parall/data.js"
DATASET     = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
USER_AGENT  = "GhalghayTools/1.0 corpus builder"

SOURCE_MAP = {
    "КиплРикк":              "ghalghay-kipling-rikki",
    "Тургенев И. С. «Муму»": "ghalghay-turgenev-mumu",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_html(text):
    """Убрать HTML-теги и нормализовать пробелы."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;",  "<", text)
    text = re.sub(r"&gt;",  ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+",   " ", text).strip()
    return text


def parse_data_js(js_text):
    """Извлечь массив из var allData = [...]"""
    m = re.search(r"var\s+allData\s*=\s*(\[.*\])\s*;?\s*$", js_text, re.DOTALL)
    if not m:
        raise ValueError("Не найден allData в файле")
    # JS допускает trailing comma, JSON — нет
    arr_str = re.sub(r",\s*\]", "]", m.group(1))
    arr_str = re.sub(r",\s*\}", "}", arr_str)
    return json.loads(arr_str)


def is_header(text):
    """Строки с заголовками (h4, h3) — пропускаем."""
    return bool(re.search(r"<h[1-6]", text, re.IGNORECASE))


def main():
    print(f"Скачиваю {DATA_URL} ...", file=sys.stderr)
    js = fetch(DATA_URL)
    print(f"  Получено {len(js):,} байт", file=sys.stderr)

    records = parse_data_js(js)
    print(f"  Записей: {len(records)}", file=sys.stderr)

    # Уже существующие sources
    existing = set()
    if DATASET.exists():
        with open(DATASET, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        existing.add(json.loads(line)["source"])
                    except Exception:
                        pass

    stats = {}
    new_pairs = {}  # source -> list of pairs

    for rec in records:
        ing_raw = rec.get("b", "")
        rus_raw = rec.get("d", "")
        e       = rec.get("e", "unknown")
        source  = SOURCE_MAP.get(e, "ghalghay-" + re.sub(r"\W+", "-", e).strip("-").lower())

        # Пропускаем заголовки
        if is_header(ing_raw) or is_header(rus_raw):
            continue

        ing = strip_html(ing_raw)
        rus = strip_html(rus_raw)

        # Пропускаем пустые или слишком короткие
        if len(ing) < 10 or len(rus) < 10:
            continue

        if source not in new_pairs:
            new_pairs[source] = []
            stats[source] = 0

        new_pairs[source].append({"ing": ing, "rus": rus, "source": source, "type": "sentence"})
        stats[source] += 1

    # Записываем
    total_new = 0
    with open(DATASET, "a", encoding="utf-8") as f:
        for source, pairs in new_pairs.items():
            if not pairs:
                continue
            # Проверяем не дублируем ли
            already = sum(1 for p in pairs if p["source"] in existing)
            if already == len(pairs):
                print(f"  {source}: уже в датасете, пропуск", file=sys.stderr)
                continue
            f.write(f"### {source}  ({len(pairs)} пар)\n")
            for row in pairs:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            total_new += len(pairs)
            print(f"  {source}: +{len(pairs)} пар", file=sys.stderr)

    print(f"\nДобавлено пар: {total_new}", file=sys.stderr)
    if DATASET.exists():
        total = sum(
            1 for line in open(DATASET, encoding="utf-8")
            if line.strip() and not line.startswith("#")
        )
        print(f"Датасет итого: {total:,} пар", file=sys.stderr)


if __name__ == "__main__":
    main()
