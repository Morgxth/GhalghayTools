"""
download_pdfs.py — Загрузчик PDF из dzurdzuki.com

Читает corpus/catalog.jsonl, скачивает PDF по приоритету.
Поддерживает resume: уже скачанные файлы пропускаются.

Запуск:
    python download_pdfs.py                    # все записи
    python download_pdfs.py --priority 1       # только приоритет 1
    python download_pdfs.py --limit 20         # только первые 20
    python download_pdfs.py --dry-run          # показать что будет скачано

Результат:
    corpus/raw/{slug}.pdf          — PDF файлы
    corpus/download_state.jsonl    — состояние каждой загрузки
    corpus/download_errors.log     — ошибки
"""

import json
import re
import sys
import time
import logging
import hashlib
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

BASE_URL      = "https://dzurdzuki.com"
CORPUS_DIR    = Path(__file__).parent.parent       # corpus/
RAW_DIR       = CORPUS_DIR / "raw"
CATALOG_FILE  = CORPUS_DIR / "catalog.jsonl"
STATE_FILE    = CORPUS_DIR / "download_state.jsonl"
ERROR_LOG     = CORPUS_DIR / "download_errors.log"

# Задержки (секунды)
DELAY_BETWEEN_REQUESTS = 1.0   # между страницами с метаданными
DELAY_BETWEEN_DOWNLOADS = 2.0  # между загрузками файлов
RETRY_DELAYS = [5, 15, 60]     # экспоненциальный backoff при ошибках

REQUEST_TIMEOUT  = 30
DOWNLOAD_TIMEOUT = 120         # PDF может быть большим

MAX_WORKERS = 1                # последовательно — уважаем сервер

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

PDF_MAGIC  = b"%PDF"
DJVU_MAGIC = b"AT&T"

KNOWN_FORMATS = {
    b"%PDF": ".pdf",
    b"AT&T": ".djvu",    # DjVu (сканированные книги)
    b"PK\x03\x04": ".zip",
}

# ---------------------------------------------------------------------------
# Состояние загрузки
# ---------------------------------------------------------------------------

@dataclass
class DownloadState:
    slug: str
    status: str          # "ok" | "error" | "skipped"
    local_path: str      # относительный путь от corpus/
    file_size: int       # байт
    download_url: str
    method: str          # "wpdmdl" | "direct_pdf"
    error: str = ""
    md5: str = ""


def load_state() -> dict[str, DownloadState]:
    """Загружает уже сохранённое состояние (для resume)."""
    state: dict[str, DownloadState] = {}
    if not STATE_FILE.exists():
        return state
    with open(STATE_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                state[d["slug"]] = DownloadState(**d)
            except (json.JSONDecodeError, TypeError):
                pass
    return state


def save_state_entry(entry: DownloadState) -> None:
    """Дозаписывает одну запись состояния."""
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Разбор страницы книги — извлечение URL для скачивания
# ---------------------------------------------------------------------------

def extract_download_url(download_page_url: str) -> tuple[str, str]:
    """
    Возвращает (url_для_скачивания, метод).
    метод: "wpdmdl" или "direct_pdf"
    Бросает ValueError если URL не найден.
    """
    resp = requests.get(
        download_page_url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()

    # Метод 1: прямой PDF URL в HTML
    # wp-content/uploads/download-manager-files/*.pdf
    direct = re.search(
        r'(https?://dzurdzuki\.com/wp-content/uploads/download-manager-files/'
        r'[^\s"\'<>]+\.(?:pdf|PDF))',
        resp.text,
    )
    if direct:
        return direct.group(1), "direct_pdf"

    # Метод 2: onclick с ?wpdmdl=ID
    soup = BeautifulSoup(resp.text, "html.parser")
    btn = soup.find("a", class_="wpdm-download-link")
    if btn:
        onclick = btn.get("onclick", "")
        m = re.search(r"location\.href='([^']+\?wpdmdl=\d+)'", onclick)
        if m:
            return m.group(1), "wpdmdl"

    # Метод 3: ищем ?wpdmdl= в любом месте страницы
    m = re.search(
        r'(https?://dzurdzuki\.com/download/[^\s"\'<>]+\?wpdmdl=\d+)',
        resp.text,
    )
    if m:
        return m.group(1), "wpdmdl"

    # Метод 4: конструируем из file ID
    fid = re.search(r'[?&]id=(\d+)', resp.text)
    if fid:
        url = f"{download_page_url.rstrip('/')}/?wpdmdl={fid.group(1)}"
        return url, "wpdmdl"

    raise ValueError(f"Не удалось найти URL скачивания на странице {download_page_url}")


# ---------------------------------------------------------------------------
# Загрузка файла
# ---------------------------------------------------------------------------

def md5_of_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def detect_format(path: Path) -> str:
    """Определяет реальный формат по магическим байтам. Возвращает расширение."""
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
        for sig, ext in KNOWN_FORMATS.items():
            if magic.startswith(sig):
                return ext
    except OSError:
        pass
    return ".bin"


def download_file(url: str, dest_stem: Path) -> tuple[Path, int]:
    """
    Скачивает файл потоково.
    dest_stem — путь без расширения (расширение определяется по содержимому).
    Возвращает (итоговый_путь, размер_в_байтах).
    Бросает исключение при ошибке.
    """
    dest_stem.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_stem.with_suffix(".tmp")

    resp = requests.get(
        url,
        headers={**HEADERS, "Referer": BASE_URL},
        timeout=DOWNLOAD_TIMEOUT,
        stream=True,
    )
    resp.raise_for_status()

    # Проверяем Content-Type
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct:
        preview = resp.content[:300]
        raise ValueError(f"Получен HTML вместо файла. preview={preview!r}")

    size = 0
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                size += len(chunk)

    if size == 0:
        tmp.unlink(missing_ok=True)
        raise ValueError("Скачан пустой файл")

    # Определяем реальный формат и переименовываем
    real_ext = detect_format(tmp)
    dest = dest_stem.with_suffix(real_ext)
    tmp.rename(dest)
    return dest, size


# ---------------------------------------------------------------------------
# Одна задача загрузки
# ---------------------------------------------------------------------------

def process_one(record: dict, dry_run: bool) -> DownloadState:
    slug      = record["slug"]
    p_url     = record["download_page_url"]
    dest_stem = RAW_DIR / slug           # без расширения — определим по содержимому
    rel       = str(dest_stem.parent.relative_to(CORPUS_DIR) / slug)

    log_prefix = f"[{record['priority']}|{record['category_slug'][:8]}] {slug[:45]}"

    if dry_run:
        logging.info(f"DRY  {log_prefix}")
        return DownloadState(slug=slug, status="skipped", local_path=rel + ".?",
                             file_size=0, download_url="", method="dry_run")

    # Шаг 1: получить URL файла
    try:
        file_url, method = extract_download_url(p_url)
    except Exception as e:
        logging.error(f"FAIL {log_prefix} — страница: {e}")
        with open(ERROR_LOG, "a", encoding="utf-8") as ef:
            ef.write(f"PAGE_ERROR\t{slug}\t{p_url}\t{e}\n")
        return DownloadState(slug=slug, status="error", local_path=rel,
                             file_size=0, download_url=p_url, method="",
                             error=f"page: {e}")

    time.sleep(DELAY_BETWEEN_REQUESTS)

    # Шаг 2: скачать файл (с retry)
    for attempt, delay in enumerate([0] + RETRY_DELAYS, 1):
        if delay:
            logging.info(f"  Повтор {attempt} через {delay}с...")
            time.sleep(delay)
        try:
            dest, size = download_file(file_url, dest_stem)
            checksum = md5_of_file(dest)
            rel_final = str(dest.relative_to(CORPUS_DIR))
            logging.info(f"OK   {log_prefix} -> {size//1024} KB [{method}] {dest.suffix}")
            return DownloadState(slug=slug, status="ok", local_path=rel_final,
                                 file_size=size, download_url=file_url,
                                 method=method, md5=checksum)
        except Exception as e:
            logging.warning(f"  Попытка {attempt} ошибка: {e}")
            if attempt > len(RETRY_DELAYS):
                break

    logging.error(f"FAIL {log_prefix} - файл: все попытки исчерпаны")
    with open(ERROR_LOG, "a", encoding="utf-8") as ef:
        ef.write(f"DOWNLOAD_ERROR\t{slug}\t{file_url}\tвсе попытки исчерпаны\n")
    return DownloadState(slug=slug, status="error", local_path=rel + ".?",
                         file_size=0, download_url=file_url, method=method,
                         error="все попытки исчерпаны")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Загрузчик PDF из dzurdzuki.com")
    p.add_argument("--priority", type=int, choices=[1, 2, 3],
                   help="Скачать только указанный приоритет")
    p.add_argument("--category", type=str,
                   help="Скачать только указанную категорию (slug)")
    p.add_argument("--limit", type=int,
                   help="Максимальное количество файлов для скачивания")
    p.add_argument("--dry-run", action="store_true",
                   help="Показать что будет скачано без реальной загрузки")
    p.add_argument("--force", action="store_true",
                   help="Перекачать даже уже скачанные файлы")
    return p.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(CORPUS_DIR / "download.log", encoding="utf-8"),
        ],
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Загружаем каталог
    if not CATALOG_FILE.exists():
        logging.error(f"Каталог не найден: {CATALOG_FILE}")
        logging.error("Сначала запустите crawl_catalog.py")
        sys.exit(1)

    with open(CATALOG_FILE, encoding="utf-8") as f:
        all_records = [json.loads(line) for line in f]

    # Загружаем состояние (resume)
    state = load_state()

    # Фильтрация
    records = all_records
    if args.priority:
        records = [r for r in records if r["priority"] == args.priority]
    if args.category:
        records = [r for r in records if r["category_slug"] == args.category]

    # Сортируем по приоритету, потом по популярности (топ-скачиваемые первыми)
    records.sort(key=lambda r: (r["priority"], -r["download_count"]))

    # Убираем уже скачанные (если не --force)
    if not args.force:
        to_skip = []
        to_do   = []
        for r in records:
            existing = state.get(r["slug"])
            # Файл может быть .pdf или .djvu — проверяем оба
            slug = r["slug"]
            local_exists = any(
                (RAW_DIR / f"{slug}{ext}").exists()
                for ext in (".pdf", ".djvu", ".bin")
            )
            if existing and existing.status == "ok" and local_exists:
                to_skip.append(r)
            else:
                to_do.append(r)
        logging.info(f"Уже скачано: {len(to_skip)}, осталось: {len(to_do)}")
        records = to_do

    if args.limit:
        records = records[:args.limit]

    if not records:
        logging.info("Нечего скачивать — всё уже готово.")
        return

    # Сводка перед стартом
    def parse_mb(s: str) -> float:
        try:
            return float(s.split()[0])
        except (ValueError, IndexError):
            return 0.0

    total_size_hint = int(sum(
        parse_mb(r.get("file_size", "")) * 1024 * 1024
        if r.get("file_size") else 0
        for r in records
    ))
    logging.info(
        f"\nБудет скачано: {len(records)} файлов"
        + (f"  (~{total_size_hint // (1024*1024)} МБ)" if total_size_hint else "")
    )
    if args.dry_run:
        logging.info("--- DRY RUN: файлы не скачиваются ---")

    # Загружаем
    ok = err = 0
    for i, record in enumerate(records, 1):
        logging.info(f"\n[{i}/{len(records)}]")
        result = process_one(record, dry_run=args.dry_run)

        if not args.dry_run:
            save_state_entry(result)

        if result.status == "ok":
            ok += 1
        elif result.status == "error":
            err += 1

        if not args.dry_run and result.status == "ok":
            time.sleep(DELAY_BETWEEN_DOWNLOADS)

    logging.info(f"\n{'='*50}")
    logging.info(f"Готово: {ok} успешно, {err} ошибок")
    if err:
        logging.info(f"Ошибки записаны в: {ERROR_LOG}")


if __name__ == "__main__":
    main()
