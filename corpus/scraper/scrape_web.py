"""
scrape_web.py — Скрапинг веб-источников ингушского текста

Источники:
1. Ингушская Википедия (inh.wikipedia.org) — 2500+ статей, MediaWiki API
2. Газета «Сердало» (serdalo.ru/inh) — 940+ статей, HTML

Сохраняет тексты в corpus/text/wiki_*.txt и corpus/text/serdalo_*.txt
Добавляет записи в corpus/catalog.jsonl (не дублирует уже существующие)

Запуск:
    python scrape_web.py                        # оба источника
    python scrape_web.py --source wikipedia     # только Вики
    python scrape_web.py --source serdalo       # только Сердало
    python scrape_web.py --limit 50             # первые 50 статей (тест)
"""

import re
import json
import time
import argparse
import logging
import sys
import unicodedata
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, urlparse, urljoin
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

CORPUS_DIR   = Path(__file__).parent.parent
TEXT_DIR     = CORPUS_DIR / "text"
CATALOG_FILE = CORPUS_DIR / "catalog.jsonl"

WIKI_API   = "https://inh.wikipedia.org/w/api.php"
SERDALO_BASE = "https://serdalo.ru"
SERDALO_ING  = "https://serdalo.ru/inh"

REQUEST_DELAY = 1.0   # секунд между запросами
USER_AGENT    = "GhalghayTools/1.0 (ingush-corpus; educational research)"

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def fetch(url: str, as_json: bool = True, retries: int = 3):
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=30) as r:
                data = r.read()
            if as_json:
                return json.loads(data.decode("utf-8"))
            else:
                return data.decode("utf-8", errors="replace")
        except (HTTPError, URLError, Exception) as e:
            if attempt == retries - 1:
                logging.warning(f"  Ошибка {url}: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def slugify(text: str, prefix: str = "") -> str:
    """Превращает заголовок статьи в безопасное имя файла."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s_]+', '-', text.strip())
    text = text[:80].strip('-').lower()
    if prefix:
        return f"{prefix}_{text}"
    return text


def load_existing_slugs() -> set:
    """Читает slug'и уже существующих записей в catalog.jsonl."""
    slugs = set()
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    slugs.add(json.loads(line)["slug"])
                except Exception:
                    pass
    return slugs


def append_catalog(record: dict):
    with open(CATALOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_text(slug: str, text: str):
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = TEXT_DIR / f"{slug}.txt"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Источник 1: Ингушская Википедия
# ---------------------------------------------------------------------------

def wiki_get_all_page_ids(limit: int = 0) -> list[dict]:
    """Возвращает список {pageid, title} всех статей через API allpages."""
    pages = []
    apcontinue = None
    batch = 500

    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": str(batch),
            "apnamespace": "0",
            "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        url = WIKI_API + "?" + urlencode(params)
        data = fetch(url)
        if not data:
            break

        batch_pages = data["query"]["allpages"]
        pages.extend(batch_pages)

        if limit and len(pages) >= limit:
            pages = pages[:limit]
            break

        cont = data.get("continue", {})
        apcontinue = cont.get("apcontinue")
        if not apcontinue:
            break

        time.sleep(REQUEST_DELAY)

    return pages


def wiki_get_extracts(page_ids: list[int]) -> dict:
    """
    Получает plain-text extract для группы страниц.
    API ограничивает 20 страниц за раз при exintro=false.
    """
    ids_str = "|".join(str(i) for i in page_ids)
    params = {
        "action": "query",
        "pageids": ids_str,
        "prop": "extracts",
        "explaintext": "1",
        "exsectionformat": "plain",
        "format": "json",
    }
    url = WIKI_API + "?" + urlencode(params)
    data = fetch(url)
    if not data:
        return {}
    return data.get("query", {}).get("pages", {})


def scrape_wikipedia(limit: int = 0) -> int:
    """Скрапит ингушскую Вики. Возвращает число новых статей."""
    existing = load_existing_slugs()
    logging.info(f"[Wikipedia] Получаю список статей...")
    pages = wiki_get_all_page_ids(limit)
    logging.info(f"[Wikipedia] Всего статей: {len(pages)}")

    saved = 0
    batch_size = 20

    for i in range(0, len(pages), batch_size):
        batch = pages[i:i + batch_size]
        ids = [p["pageid"] for p in batch]

        extracts = wiki_get_extracts(ids)
        time.sleep(REQUEST_DELAY)

        for page_info in batch:
            pid = str(page_info["pageid"])
            title = page_info["title"]
            slug = slugify(title, prefix="wiki")

            if slug in existing:
                continue

            page_data = extracts.get(pid, {})
            text = page_data.get("extract", "").strip()

            if len(text) < 100:
                continue

            save_text(slug, text)
            append_catalog({
                "slug": slug,
                "title": title,
                "url": f"https://inh.wikipedia.org/wiki/{quote(title)}",
                "source": "wikipedia",
                "category_slug": "na-ingushskom",
                "priority": 1,
                "lang": "ing",
            })
            existing.add(slug)
            saved += 1

        if saved % 100 == 0 and saved > 0:
            logging.info(f"  {saved}/{len(pages)} статей сохранено...")

    logging.info(f"[Wikipedia] Готово: {saved} новых статей")
    return saved


# ---------------------------------------------------------------------------
# Источник 2: Газета «Сердало»
# ---------------------------------------------------------------------------

class SerdaloListParser(HTMLParser):
    """Парсит страницу списка статей /inh/, собирает ссылки на статьи."""
    def __init__(self):
        super().__init__()
        self.links = []
        self._in_article = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        # Статьи обёрнуты в <article> или блоки с классами типа news-item, post, entry
        classes = attrs.get("class", "")
        if tag in ("article", "div") and any(
            c in classes for c in ("news-item", "post", "entry", "item", "material")
        ):
            self._in_article = True
        if tag == "a" and self._in_article:
            href = attrs.get("href", "")
            if href and "/inh/" in href and href not in self.links:
                self.links.append(href)
                self._in_article = False

    def handle_endtag(self, tag):
        if tag in ("article", "div"):
            self._in_article = False


class SerdaloArticleParser(HTMLParser):
    """Парсит страницу статьи, извлекает заголовок и текст."""
    def __init__(self):
        super().__init__()
        self.title = ""
        self.text_parts = []
        self._in_title = False
        self._in_content = False
        self._depth = 0
        self._content_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        classes = attrs_d.get("class", "")

        if tag in ("h1", "h2") and not self.title:
            self._in_title = True

        if tag in ("div", "section", "article") and any(
            c in classes for c in ("article-content", "post-content", "entry-content",
                                    "content", "text", "body", "article__text",
                                    "news-full", "full-text")
        ):
            self._in_content = True
            self._content_depth = self._depth

        if self._in_content and tag == "p":
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in ("h1", "h2"):
            self._in_title = False
        if self._in_content and tag in ("div", "section", "article"):
            if self._depth <= self._content_depth:
                self._in_content = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        if self._in_title and not self.title:
            self.title = data
        if self._in_content:
            self.text_parts.append(data)

    def get_text(self) -> str:
        return "\n\n".join(
            p for p in self.text_parts
            if len(p) > 20
        )


SERDALO_SECTIONS = [
    f"{SERDALO_ING}/materials",
    f"{SERDALO_ING}/news",
    f"{SERDALO_ING}/journalism",
]

def serdalo_get_article_urls(limit: int = 0) -> list[str]:
    """
    Собирает ссылки на статьи через постраничный обход разделов.
    URL статьи: https://serdalo.ru/inh/material/SLUG
    Пагинация: ?page=N
    """
    all_urls = []
    seen = set()

    for section in SERDALO_SECTIONS:
        page = 1
        empty_pages = 0

        while True:
            url = f"{section}?page={page}" if page > 1 else section
            html = fetch(url, as_json=False)
            if not html:
                break

            # Ищем ссылки на статьи: /inh/material/SLUG
            found = re.findall(
                r'href=["\'](' + re.escape(SERDALO_BASE) + r'/inh/material/[^"\'#?]+)["\']',
                html
            )
            found += [
                urljoin(SERDALO_BASE, m)
                for m in re.findall(r'href=["\'](/inh/material/[^"\'#?]+)["\']', html)
            ]

            new = [u for u in found if u not in seen]
            if not new:
                empty_pages += 1
                if empty_pages >= 2:
                    break
            else:
                empty_pages = 0
                for u in new:
                    seen.add(u)
                    all_urls.append(u)
                logging.info(f"  [{section.split('/')[-1]}] стр.{page}: +{len(new)} (всего {len(all_urls)})")

            if limit and len(all_urls) >= limit:
                return all_urls

            page += 1
            time.sleep(REQUEST_DELAY)

    return all_urls


def serdalo_parse_article(url: str) -> tuple[str, str]:
    """
    Скачивает и парсит статью. Возвращает (title, text).
    Если не получилось — возвращает ("", "").
    """
    html = fetch(url, as_json=False)
    if not html:
        return "", ""

    # Заголовок — первый <h1>
    title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""

    # Текст: собираем все <p> с содержательным текстом
    # Убираем скрипты и стили
    html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)

    paras = re.findall(r'<p[^>]*>(.*?)</p>', html_clean, re.DOTALL | re.IGNORECASE)
    parts = []
    for p in paras:
        p = re.sub(r'<[^>]+>', '', p).strip()
        p = re.sub(r'\s+', ' ', p)
        if len(p) > 30:
            parts.append(p)

    text = "\n\n".join(parts)
    return title, text


def scrape_serdalo(limit: int = 0) -> int:
    """Скрапит /inh/ раздел serdalo.ru. Возвращает число новых статей."""
    existing = load_existing_slugs()
    logging.info(f"[Serdalo] Собираю ссылки на статьи...")

    urls = serdalo_get_article_urls(limit)
    logging.info(f"[Serdalo] Найдено ссылок: {len(urls)}")

    saved = 0
    for i, url in enumerate(urls):
        # slug из URL
        path = urlparse(url).path.rstrip("/")
        url_slug = path.split("/")[-1] or f"article-{i}"
        slug = f"serdalo_{url_slug[:70]}"

        if slug in existing:
            continue

        title, text = serdalo_parse_article(url)
        time.sleep(REQUEST_DELAY)

        if len(text) < 100:
            logging.debug(f"  Пропускаю {url}: текст короткий ({len(text)} симв.)")
            continue

        save_text(slug, text)
        append_catalog({
            "slug": slug,
            "title": title or url_slug,
            "url": url,
            "source": "serdalo",
            "category_slug": "na-ingushskom",
            "priority": 1,
            "lang": "ing",
        })
        existing.add(slug)
        saved += 1

        if saved % 50 == 0:
            logging.info(f"  {i+1}/{len(urls)} обработано, {saved} сохранено")

    logging.info(f"[Serdalo] Готово: {saved} новых статей")
    return saved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Скрапинг веб-источников ингушского текста")
    p.add_argument("--source", choices=["wikipedia", "serdalo", "all"], default="all")
    p.add_argument("--limit", type=int, default=0,
                   help="Максимум статей на источник (0 = все)")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0

    if args.source in ("wikipedia", "all"):
        total += scrape_wikipedia(args.limit)

    if args.source in ("serdalo", "all"):
        total += scrape_serdalo(args.limit)

    logging.info(f"\nВсего новых статей: {total}")


if __name__ == "__main__":
    main()
