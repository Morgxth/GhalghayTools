"""
crawl_catalog.py — Краулер каталога dzurdzuki.com/biblioteka/

Собирает метаданные всех книг из целевых категорий и сохраняет
в corpus/catalog.jsonl. Не скачивает PDF — только каталог.

Запуск:
    pip install requests beautifulsoup4
    python crawl_catalog.py

Результат:
    corpus/catalog.jsonl      — все записи
    corpus/catalog_report.txt — статистика по категориям
"""

import json
import time
import logging
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

BASE_URL = "https://dzurdzuki.com"
CATALOG_URL = BASE_URL + "/biblioteka/"

# Целевые категории: (wpdmc-slug, название, приоритет)
# Приоритет: 1 = критический (ингушский текст), 2 = высокий, 3 = средний
TARGET_CATEGORIES = [
    # Приоритет 1 — прямой ингушский текст или лингвистика
    ("na-ingushskom",    "На ингушском",              1),
    ("slovari",          "Словари / Языкознание",      1),  # 108 словарей/грамматик
    ("folklor",          "Фольклор",                  1),
    ("loaman-iujre",     "Альманах Лоаман Іуйре",     1),
    # Приоритет 2 — ингушский контекст, много переводов
    ("detskaya",         "Детская",                   2),
    ("poeziya",          "Поэзия",                    2),
    ("hudozhestvennaya", "Художественная",             2),
    # Приоритет 3 — исторический/справочный материал
    ("arhivnye-dokumenty", "Архивные документы",      3),
    ("sovetskaya-etnografiya", "Советская этнография", 3),  # 70 выпусков
    ("karty",            "Карты",                     3),
]

# Пауза между запросами (секунды) — уважаем сервер
REQUEST_DELAY = 1.5

# Таймаут запроса
REQUEST_TIMEOUT = 30

OUTPUT_DIR = Path(__file__).parent.parent  # corpus/
CATALOG_FILE = OUTPUT_DIR / "catalog.jsonl"
REPORT_FILE  = OUTPUT_DIR / "catalog_report.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GhalghayToolsBot/1.0; "
        "+https://github.com/goygo/GhalghayTools) "
        "research/cultural-preservation"
    ),
    "Accept-Language": "ru,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# ---------------------------------------------------------------------------
# Структура записи
# ---------------------------------------------------------------------------

@dataclass
class BookRecord:
    slug: str               # уникальный идентификатор (из URL)
    title: str              # название
    download_page_url: str  # страница /download/slug/
    category_slug: str      # wpdmc категория
    category_name: str      # человекочитаемое название
    priority: int           # 1-3
    file_size: str          # "20.92 Мб"
    download_count: int     # сколько раз скачали
    upload_date: str        # "25.02.2025"
    author: Optional[str]   # если удалось извлечь из заголовка


# ---------------------------------------------------------------------------
# Парсинг
# ---------------------------------------------------------------------------

def fetch_category_page(category_slug: str) -> Optional[BeautifulSoup]:
    """Загружает страницу категории и возвращает BeautifulSoup объект."""
    url = f"{CATALOG_URL}?wpdmc={category_slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        logging.info(f"  GET {url} → {resp.status_code} ({len(resp.content)//1024} KB)")
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        logging.error(f"  Ошибка при загрузке {url}: {e}")
        return None


def extract_slug(url: str) -> str:
    """Извлекает slug из URL: /download/some-slug/ → some-slug"""
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else url


def parse_download_count(text: str) -> int:
    """'138 загрузок' → 138"""
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def guess_author(title: str) -> Optional[str]:
    """
    Пытается извлечь автора из типичных паттернов заголовков:
    'Дахкильгов И.А. — Название книги' или 'Название — Автор'
    """
    # Паттерн: Фамилия И.О. в начале
    m = re.match(r"^([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)", title)
    if m:
        return m.group(1)
    # Паттерн: после тире
    m = re.search(r"[—–-]\s*([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)", title)
    if m:
        return m.group(1)
    return None


def parse_books(soup: BeautifulSoup, category_slug: str,
                category_name: str, priority: int) -> list[BookRecord]:
    """
    Вытаскивает все книги из HTML страницы категории.

    Реальная структура таблицы WPDM на dzurdzuki.com:
      <tr>
        <td> <a href="/download/slug/" class="package-title">Название</a>
             <span class="small-txt">20.92 Мб</span>
             <span class="small-txt">138 загрузок</span> </td>
        <td> Категория, Доп.категория </td>
        <td> </td>
        <td> 25.02.2025 </td>
        <td> </td>
      </tr>
    """
    books = []
    seen_slugs: set[str] = set()

    # Основной паттерн: a.package-title с /download/ в href
    download_links = soup.find_all(
        "a",
        class_="package-title",
        href=re.compile(r"/download/"),
    )

    # Запасной вариант (на случай если структура другая)
    if not download_links:
        download_links = soup.find_all(
            "a", href=re.compile(r"/download/[^/]+/")
        )

    for link in download_links:
        href = link.get("href", "")
        if "/download/" not in href:
            continue

        # Нормализуем URL
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.startswith("http"):
            continue

        slug = extract_slug(href)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Название — текст самого тега <a>
        title = link.get_text(strip=True) or slug

        # Ищем строку таблицы для дополнительных данных
        row = link.find_parent("tr")

        file_size = ""
        download_count = 0
        upload_date = ""

        if row:
            # small-txt spans: размер и кол-во загрузок
            for span in row.find_all("span", class_="small-txt"):
                txt = span.get_text(strip=True)
                if re.search(r"загруз|скачив", txt, re.I):
                    download_count = parse_download_count(txt)
                elif re.search(r"[кмгКМГ]б|[kmgKMG]b", txt, re.I):
                    file_size = txt

            # Дата — ячейка с форматом DD.MM.YYYY
            for td in row.find_all("td"):
                td_text = td.get_text(strip=True)
                if re.match(r"\d{2}\.\d{2}\.\d{4}", td_text):
                    upload_date = td_text
                    break

        books.append(BookRecord(
            slug=slug,
            title=title,
            download_page_url=href,
            category_slug=category_slug,
            category_name=category_name,
            priority=priority,
            file_size=file_size,
            download_count=download_count,
            upload_date=upload_date,
            author=guess_author(title),
        ))

    return books


# ---------------------------------------------------------------------------
# Дедупликация
# ---------------------------------------------------------------------------

def deduplicate(records: list[BookRecord]) -> list[BookRecord]:
    """
    Одна книга может быть в нескольких категориях.
    Оставляем запись с наивысшим приоритетом (меньший номер = выше).
    """
    best: dict[str, BookRecord] = {}
    for rec in records:
        existing = best.get(rec.slug)
        if existing is None or rec.priority < existing.priority:
            best[rec.slug] = rec
    return list(best.values())


# ---------------------------------------------------------------------------
# Отчёт
# ---------------------------------------------------------------------------

def build_report(records: list[BookRecord],
                 category_stats: dict[str, int]) -> str:
    lines = [
        "=" * 60,
        "ОТЧЁТ: Краулинг dzurdzuki.com/biblioteka/",
        "=" * 60,
        "",
        "Статистика по категориям:",
        "-" * 40,
    ]
    for slug, count in category_stats.items():
        lines.append(f"  {slug:<25} {count:>4} записей")

    lines += [
        "",
        "-" * 40,
        f"Всего уникальных записей: {len(records)}",
        "",
        "Распределение по приоритету:",
    ]
    for p in [1, 2, 3]:
        n = sum(1 for r in records if r.priority == p)
        lines.append(f"  Приоритет {p}: {n} записей")

    # Топ-10 по скачиваниям
    top = sorted(records, key=lambda r: r.download_count, reverse=True)[:10]
    lines += ["", "Топ-10 по скачиваниям:", "-" * 40]
    for r in top:
        lines.append(f"  {r.download_count:>5}x  {r.title[:55]}")

    lines += ["", "Файл каталога: corpus/catalog.jsonl"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Основной цикл
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    all_records: list[BookRecord] = []
    category_stats: dict[str, int] = {}

    # Загружаем уже собранные записи (поддержка resume)
    existing_slugs: set[str] = set()
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    existing_slugs.add(rec["slug"])
                    all_records.append(BookRecord(**rec))
                except (json.JSONDecodeError, TypeError):
                    pass
        logging.info(f"Уже в каталоге: {len(existing_slugs)} записей")

    # Краулим каждую категорию
    for cat_slug, cat_name, priority in TARGET_CATEGORIES:
        logging.info(f"\n[{priority}] Категория: {cat_name} ({cat_slug})")

        soup = fetch_category_page(cat_slug)
        if soup is None:
            logging.warning(f"  Пропускаем {cat_slug}")
            category_stats[cat_slug] = 0
            time.sleep(REQUEST_DELAY)
            continue

        books = parse_books(soup, cat_slug, cat_name, priority)
        new_books = [b for b in books if b.slug not in existing_slugs]

        logging.info(f"  Найдено: {len(books)}, новых: {len(new_books)}")
        category_stats[cat_slug] = len(books)

        all_records.extend(new_books)
        for b in new_books:
            existing_slugs.add(b.slug)

        time.sleep(REQUEST_DELAY)

    # Дедупликация
    unique = deduplicate(all_records)
    logging.info(f"\nДедупликация: {len(all_records)} → {len(unique)} записей")

    # Сохраняем
    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        for rec in sorted(unique, key=lambda r: (r.priority, r.category_slug)):
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    logging.info(f"Сохранено: {CATALOG_FILE}")

    # Отчёт
    report = build_report(unique, category_stats)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
