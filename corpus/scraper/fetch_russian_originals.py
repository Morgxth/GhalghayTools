"""
fetch_russian_originals.py — Скачивает русские оригиналы для произведений,
переведённых на ингушский язык.

Источники: lib.ru (koi8-r/cp1251) и WikiSource (UTF-8 wikitext → plaintext)
Маппинг: corpus/russian_originals/mapping.json
Результат: corpus/russian_originals/{slug}_rus.txt

Запуск:
    python fetch_russian_originals.py            # всё
    python fetch_russian_originals.py --force    # перезаписывать существующие
    python fetch_russian_originals.py --list     # показать маппинг без скачивания
"""

import re
import json
import time
import logging
import sys
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

CORPUS_DIR  = Path(__file__).parent.parent
OUT_DIR     = CORPUS_DIR / "russian_originals"
MAPPING_FILE = OUT_DIR / "mapping.json"

USER_AGENT    = "GhalghayTools/1.0 (ingush-corpus; educational research)"
REQUEST_DELAY = 1.5

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def fetch_raw(url: str, encoding: str = "utf-8", retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=40) as r:
                return r.read().decode(encoding, errors="replace")
        except (HTTPError, URLError, Exception) as e:
            if attempt == retries - 1:
                logging.warning(f"  Ошибка [{url[:70]}]: {e}")
                return None
            time.sleep(2 ** attempt)
    return None

# ---------------------------------------------------------------------------
# Источник 1: lib.ru (plain .txt или .shtml)
# ---------------------------------------------------------------------------

def fetch_libru(url: str, encoding: str = "koi8-r") -> str | None:
    text = fetch_raw(url, encoding=encoding)
    if not text:
        return None
    # Если HTML — вырезаем теги
    if re.search(r'<html', text, re.IGNORECASE):
        # Ищем содержимое <pre> (lib.ru часто оборачивает текст в <pre>)
        pre = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
        if pre:
            text = pre.group(1)
        else:
            # Грубая очистка HTML
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>',  '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
    # HTML-сущности
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    # Нормализуем переносы строк
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ---------------------------------------------------------------------------
# Источник 2: WikiSource (wikitext → plaintext)
# ---------------------------------------------------------------------------

def fetch_wikisource(url: str) -> str | None:
    """
    Скачивает raw wikitext со страницы WikiSource (?action=raw)
    и конвертирует в plain text.
    """
    # Если передан обычный URL без action=raw — добавляем
    if "action=raw" not in url:
        url = url.rstrip("/") + ("&" if "?" in url else "?") + "action=raw"

    text = fetch_raw(url, encoding="utf-8")
    if not text:
        return None
    return clean_wikitext(text)


def clean_wikitext(text: str) -> str:
    """Конвертирует вики-разметку в plain text."""
    # Убираем noinclude/includeonly блоки
    text = re.sub(r'<noinclude>.*?</noinclude>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<includeonly>.*?</includeonly>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Убираем категории и интервики
    text = re.sub(r'\[\[Категория:[^\]]+\]\]', '', text)
    text = re.sub(r'\[\[[a-z]{2,3}:[^\]]+\]\]', '', text)
    # Шаблоны {{...}} — несколько проходов для вложенных
    for _ in range(6):
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)
    # [[ссылка|текст]] → текст, [[ссылка]] → ссылка
    text = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # Внешние ссылки
    text = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', text)
    text = re.sub(r'\[https?://\S+\]', '', text)
    # HTML теги
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Заголовки == ... == → текст
    text = re.sub(r'={2,6}\s*(.*?)\s*={2,6}', r'\n\n\1\n', text)
    # Жирный/курсив
    text = re.sub(r"'{2,3}", '', text)
    # HTML-сущности
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = re.sub(r'&#\d+;', '', text)
    # Нормализуем пробелы и переносы
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------

def extract_local(entry: dict) -> str | None:
    """Извлекает текст из локального PDF/DJVU файла."""
    local_path = CORPUS_DIR / entry["local_file"]
    method     = entry.get("extract_method", "fitz")
    start_page = entry.get("text_start_page", 0)

    if not local_path.exists():
        logging.warning(f"  Локальный файл не найден: {local_path}")
        return None

    if method == "djvutxt":
        import subprocess
        djvutxt = r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe"
        result = subprocess.run([djvutxt, str(local_path)], capture_output=True)
        if result.returncode != 0:
            logging.warning(f"  djvutxt ошибка: {result.stderr[:100]}")
            return None
        text = result.stdout.decode("utf-8", errors="replace")

    elif method == "fitz":
        try:
            import fitz as pymupdf
        except ImportError:
            logging.warning("  PyMuPDF не установлен")
            return None
        doc = pymupdf.open(str(local_path))
        parts = []
        for i in range(start_page, len(doc)):
            t = doc[i].get_text().strip()
            if t:
                parts.append(t)
        doc.close()
        text = "\n\n".join(parts)
    else:
        logging.warning(f"  Неизвестный метод: {method}")
        return None

    # Нормализуем
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_entry(slug: str, entry: dict) -> str | None:
    source = entry.get("source")
    url    = entry.get("url", "")
    enc    = entry.get("encoding", "utf-8")

    if entry.get("type") in ("internal", "skip"):
        return None

    if entry.get("type") == "local":
        return extract_local(entry)

    if source == "libru":
        return fetch_libru(url, encoding=enc)
    elif source == "wikisource":
        return fetch_wikisource(url)
    else:
        logging.warning(f"  Неизвестный источник: {source}")
        return None


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAPPING_FILE, encoding="utf-8") as f:
        mapping = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    if args.list:
        print(f"{'Slug':<55} {'Тип':<10} {'Название'}")
        print("-" * 90)
        for slug, entry in mapping.items():
            t = entry.get("type", "?")
            print(f"  {slug:<55} {t:<10} {entry.get('rus_author','?')} — {entry.get('rus_title','?')}")
        return

    ok, fail, skip = 0, 0, 0

    for slug, entry in mapping.items():
        if entry.get("type") in ("internal", "skip"):
            logging.info(f"[{entry.get('type')}]  {slug[:50]}")
            skip += 1
            continue

        out_path = OUT_DIR / f"{slug}_rus.txt"
        if out_path.exists() and not args.force:
            logging.info(f"[exists]   {slug[:50]}")
            skip += 1
            continue

        logging.info(f"[fetch]    {entry['rus_author']} — {entry['rus_title']}")
        text = fetch_entry(slug, entry)
        time.sleep(REQUEST_DELAY)

        if not text or len(text) < 500:
            logging.warning(f"  FAIL: текст пустой или слишком короткий ({len(text) if text else 0} симв.)")
            fail += 1
            continue

        out_path.write_text(text, encoding="utf-8")
        logging.info(f"  OK: {out_path.name} ({len(text):,} симв.)")
        ok += 1

    logging.info(f"\n{'='*50}")
    logging.info(f"Скачано: {ok}  |  Ошибок: {fail}  |  Пропущено: {skip}")


def parse_args():
    p = argparse.ArgumentParser(description="Загрузка русских оригиналов")
    p.add_argument("--force", action="store_true", help="Перезаписывать существующие файлы")
    p.add_argument("--list",  action="store_true", help="Показать маппинг и выйти")
    return p.parse_args()


if __name__ == "__main__":
    main()
