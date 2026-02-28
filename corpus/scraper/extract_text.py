"""
extract_text.py — Извлечение текста из PDF/DjVu корпуса

Стратегия:
  1. PyMuPDF (fitz) — пробуем встроенный текстовый слой
  2. Если качество плохое (скан) — OCR через Tesseract с rus.traineddata
  3. Пост-обработка: нормализация палочки, очистка мусора

Запуск:
    python extract_text.py                  # всё
    python extract_text.py --method text    # только текстовый слой (быстро)
    python extract_text.py --method ocr     # только сканы через OCR (долго)
    python extract_text.py --limit 20       # первые 20 файлов
    python extract_text.py --slug some-slug # один конкретный файл

Результат:
    corpus/text/{slug}.txt              — извлечённый текст
    corpus/extract_state.jsonl          — метаданные каждой обработки
"""

import sys
import os
import re
import json
import time
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

CORPUS_DIR      = Path(__file__).parent.parent
RAW_DIR         = CORPUS_DIR / "raw"
TEXT_DIR        = CORPUS_DIR / "text"
CATALOG_FILE    = CORPUS_DIR / "catalog.jsonl"
STATE_FILE      = CORPUS_DIR / "extract_state.jsonl"

TESSERACT_CMD   = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR    = str(CORPUS_DIR.parent / "spell-checker" / "materials")
DJVUTXT_CMD     = r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe"

# Порог: если меньше N символов на страницу — считаем сканом
TEXT_LAYER_MIN_CHARS_PER_PAGE = 40

# OCR: разрешение рендеринга (zoom фактор)
OCR_ZOOM = 2.5   # ~180 dpi — хороший баланс скорость/качество

# Минимум текста чтобы считать извлечение успешным
MIN_USEFUL_CHARS = 200

# ---------------------------------------------------------------------------
# Нормализация палочки
# ---------------------------------------------------------------------------

# Ингушская палочка (Ӏ/ӏ) часто OCR/шрифт кодируют как I, 1, l, |
# Применяем после согласных ингушского алфавита

_CONSONANTS = r'[гкхчщшцжнмлрйбвдзсфтпГКХЧЩШЦЖНМЛРЙБВДЗСФТП]'

def normalize_palochka(text: str) -> str:
    """
    Восстанавливает палочку (ӏ) из типичных артефактов OCR/шрифта.
    Применяет несколько правил последовательно.
    """
    # 1. Явная заглавная Ӏ → строчная ӏ (после нижнего регистра)
    text = text.replace('\u04c0', 'ӏ')

    # 2. Латинская I после согласной → ӏ
    # Примеры: гI → гӏ, кI → кӏ, хI → хӏ, tI → хӏ
    text = re.sub(rf'({_CONSONANTS})I(?=[а-яёӏ\s,\.!?\-]|$)', r'\1ӏ', text)
    text = re.sub(rf'({_CONSONANTS})I(?=[А-ЯЁ])', r'\1ӏ', text)

    # 3. Цифра 1 после согласной + перед гласной → ӏ
    # Примеры: г1а → гӏа, х1ара → хӏара
    _VOWELS = r'[аеёиоуыьъэюяАЕЁИОУЫЬЪЭЮЯаьеьоьуь]'
    text = re.sub(rf'({_CONSONANTS})1(?=[аеёиоуыьэюяАЕЁИОУЫЬЭЮЯ])', r'\1ӏ', text)

    # 4. Вертикальная черта | после согласной → ӏ
    text = re.sub(rf'({_CONSONANTS})\|', r'\1ӏ', text)

    # 5. Типичные ингушские комбинации с ошибочным символом в середине
    # гIа/кIа/хIа (самые частые)
    for wrong in ['I', '1', 'l', '|']:
        for cons in ['г', 'к', 'х', 'Г', 'К', 'Х']:
            text = text.replace(f'{cons}{wrong}а', f'{cons}ӏа')
            text = text.replace(f'{cons}{wrong}е', f'{cons}ӏе')
            text = text.replace(f'{cons}{wrong}о', f'{cons}ӏо')

    return text


# ---------------------------------------------------------------------------
# Чистка текста
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Убирает типичный мусор OCR и шрифтов."""
    # Лишние пробелы внутри строк
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Тройные и более переносы строк → двойной
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Дефисы переноса строк (мягкий перенос)
    text = re.sub(r'-\n(?=[а-яёӏА-ЯЁ])', '', text)
    # Странные символы (не кириллица, не латиница, не знаки препинания)
    text = re.sub(r'[^\u0400-\u04FF\u0020-\u007E\u00A0\n\t]', '', text)
    # Одиночные буквы на отдельной строке (артефакты OCR)
    text = re.sub(r'^\s*[А-ЯЁа-яё]\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


# ---------------------------------------------------------------------------
# Структура результата
# ---------------------------------------------------------------------------

@dataclass
class ExtractResult:
    slug: str
    status: str          # "ok_text" | "ok_ocr" | "scan_skip" | "error"
    method: str          # "fitz_text" | "ocr" | "none"
    pages_total: int
    pages_extracted: int
    chars_total: int
    chars_per_page: float
    local_text_path: str
    error: str = ""


def load_extract_state() -> set[str]:
    """Возвращает множество slug которые уже обработаны успешно."""
    done: set[str] = set()
    if not STATE_FILE.exists():
        return done
    with open(STATE_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get("status", "").startswith("ok"):
                    done.add(d["slug"])
            except (json.JSONDecodeError, TypeError):
                pass
    return done


def save_result(result: ExtractResult) -> None:
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Извлечение: текстовый слой
# ---------------------------------------------------------------------------

def extract_text_layer(doc) -> tuple[str, int]:
    """
    Извлекает текст из встроенного текстового слоя.
    Возвращает (текст, количество страниц с текстом).
    """
    pages_text = []
    pages_with_text = 0
    for page in doc:
        t = page.get_text("text")
        if len(t.strip()) > 10:
            pages_with_text += 1
        pages_text.append(t)
    return "\n\n".join(pages_text), pages_with_text


def has_good_text_layer(doc) -> tuple[bool, float]:
    """
    Проверяет качество текстового слоя.
    Возвращает (есть_текст, chars_per_page).
    """
    sample_pages = min(10, len(doc))
    total_chars = sum(
        len(doc[i].get_text())
        for i in range(sample_pages)
    )
    cpp = total_chars / max(sample_pages, 1)
    return cpp >= TEXT_LAYER_MIN_CHARS_PER_PAGE, cpp


# ---------------------------------------------------------------------------
# Извлечение: OCR
# ---------------------------------------------------------------------------

def ocr_document(doc, slug: str) -> tuple[str, int]:
    """
    Рендерит страницы через fitz и прогоняет Tesseract OCR.
    Возвращает (текст, кол-во страниц с результатом).
    """
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

    pages_text  = []
    pages_done  = 0
    total_pages = len(doc)

    for page_num, page in enumerate(doc):
        try:
            # Рендерим страницу как серое изображение
            mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            img = Image.frombytes("L", [pix.width, pix.height], pix.samples)

            # OCR
            text = pytesseract.image_to_string(
                img,
                lang="rus",
                config="--psm 1 --oem 1",
            )
            if len(text.strip()) > 20:
                pages_text.append(text)
                pages_done += 1

        except Exception as e:
            logging.debug(f"  OCR page {page_num}: {e}")
            continue

        # Лог прогресса каждые 20 страниц
        if (page_num + 1) % 20 == 0:
            logging.info(f"  OCR: {page_num+1}/{total_pages} страниц...")

    return "\n\n".join(pages_text), pages_done


# ---------------------------------------------------------------------------
# Извлечение: DjVu через djvutxt
# ---------------------------------------------------------------------------

def extract_djvu(file_path: Path) -> tuple[str, int]:
    """
    Извлекает текст из DjVu файла через djvutxt.
    Возвращает (текст, страниц).
    """
    import subprocess, tempfile

    if not Path(DJVUTXT_CMD).exists():
        raise RuntimeError(
            f"djvutxt не найден: {DJVUTXT_CMD}\n"
            "Установи: winget install DjVuLibre.DjView"
        )

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        r = subprocess.run(
            [DJVUTXT_CMD, str(file_path), tmp_path],
            capture_output=True, timeout=120,
        )
        if r.returncode not in (0, 1):  # 1 = partial success
            raise RuntimeError(f"djvutxt вернул код {r.returncode}")

        text = Path(tmp_path).read_text(encoding="utf-8", errors="replace")
        pages = text.count("\x0c") + 1  # form-feed = разделитель страниц
        return text, pages
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Основная функция обработки одного файла
# ---------------------------------------------------------------------------

def process_file(
    slug: str,
    file_path: Path,
    method_override: Optional[str] = None,
) -> ExtractResult:
    """
    Обрабатывает один файл: извлекает текст, нормализует, сохраняет.
    method_override: "text" | "ocr" | None (авто)
    """
    import fitz as _fitz  # локальный import для понятности

    rel_text = f"text/{slug}.txt"
    dest = TEXT_DIR / f"{slug}.txt"

    # DjVu — отдельная ветка (fitz не умеет)
    if file_path.suffix.lower() == ".djvu":
        try:
            logging.info(f"DJVU {slug[:45]}")
            raw_text, pages_done = extract_djvu(file_path)
            method = "djvutxt"
            pages_total = pages_done
        except Exception as e:
            logging.error(f"FAIL djvu {file_path.name}: {e}")
            return ExtractResult(
                slug=slug, status="error", method="djvutxt",
                pages_total=0, pages_extracted=0,
                chars_total=0, chars_per_page=0.0,
                local_text_path=rel_text, error=str(e),
            )
        # Пост-обработка и сохранение (минуя блок ниже)
        text = normalize_palochka(raw_text)
        text = clean_text(text)
        chars_total = len(text)
        if text:
            TEXT_DIR.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        status = "ok_djvutxt" if chars_total >= MIN_USEFUL_CHARS else "scan_skip"
        return ExtractResult(
            slug=slug, status=status, method=method,
            pages_total=pages_total, pages_extracted=pages_done,
            chars_total=chars_total,
            chars_per_page=round(chars_total / max(pages_done, 1), 1),
            local_text_path=rel_text,
        )

    try:
        doc = _fitz.open(str(file_path))
    except Exception as e:
        logging.error(f"FAIL открыть {file_path.name}: {e}")
        return ExtractResult(
            slug=slug, status="error", method="none",
            pages_total=0, pages_extracted=0,
            chars_total=0, chars_per_page=0.0,
            local_text_path=rel_text, error=str(e),
        )

    pages_total = len(doc)
    raw_text    = ""
    method      = "none"
    pages_done  = 0

    # Определяем метод
    if method_override == "text" or method_override is None:
        good, cpp = has_good_text_layer(doc)
        if good or method_override == "text":
            raw_text, pages_done = extract_text_layer(doc)
            method = "fitz_text"
            logging.info(
                f"TEXT {slug[:45]} | {pages_total}pp | {cpp:.0f} ch/p"
            )

    if (not raw_text or len(raw_text.strip()) < MIN_USEFUL_CHARS) \
            and method_override != "text":
        # Скан — пробуем OCR
        if method_override == "ocr" or method_override is None:
            logging.info(f"OCR  {slug[:45]} | {pages_total} страниц...")
            raw_text, pages_done = ocr_document(doc, slug)
            method = "ocr"

    doc.close()

    # Постобработка
    if raw_text:
        text = normalize_palochka(raw_text)
        text = clean_text(text)
    else:
        text = ""

    chars_total = len(text)
    cpp_final   = chars_total / max(pages_done, 1)

    # Решение по качеству
    if chars_total < MIN_USEFUL_CHARS:
        status = "scan_skip"
        logging.warning(f"SKIP {slug[:45]} — мало текста ({chars_total} символов)")
        doc_close_save = False
    else:
        status = f"ok_{method.replace('fitz_', '')}"
        doc_close_save = True

    # Сохраняем даже scan_skip с тем что есть (для последующего анализа)
    if text:
        TEXT_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")

    return ExtractResult(
        slug=slug,
        status=status,
        method=method,
        pages_total=pages_total,
        pages_extracted=pages_done,
        chars_total=chars_total,
        chars_per_page=round(cpp_final, 1),
        local_text_path=rel_text,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Извлечение текста из PDF корпуса")
    p.add_argument("--method", choices=["text", "ocr", "auto"], default="auto",
                   help="text=только текстовый слой, ocr=только OCR, auto=авто")
    p.add_argument("--priority", type=int, choices=[1, 2, 3],
                   help="Обрабатывать только указанный приоритет")
    p.add_argument("--category", type=str, help="Только указанная категория")
    p.add_argument("--slug", type=str, help="Один конкретный slug")
    p.add_argument("--limit", type=int, help="Максимум файлов")
    p.add_argument("--force", action="store_true", help="Переобработать уже готовые")
    return p.parse_args()


def main():
    global fitz
    import fitz

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(CORPUS_DIR / "extract.log", encoding="utf-8"),
        ],
    )

    args = parse_args()
    method = None if args.method == "auto" else args.method

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Загружаем каталог
    if not CATALOG_FILE.exists():
        logging.error("Сначала запустите crawl_catalog.py")
        sys.exit(1)

    with open(CATALOG_FILE, encoding="utf-8") as f:
        catalog = {json.loads(l)["slug"]: json.loads(l) for l in open(CATALOG_FILE, encoding="utf-8")}

    # Все доступные файлы
    raw_files: dict[str, Path] = {}
    for ext in (".pdf", ".djvu", ".bin"):
        for f in RAW_DIR.glob(f"*{ext}"):
            if f.stem not in raw_files:
                raw_files[f.stem] = f

    logging.info(f"Файлов в corpus/raw: {len(raw_files)}")

    # Фильтрация
    slugs = list(raw_files.keys())

    if args.slug:
        slugs = [s for s in slugs if s == args.slug]
    else:
        if args.priority:
            slugs = [s for s in slugs if catalog.get(s, {}).get("priority") == args.priority]
        if args.category:
            slugs = [s for s in slugs if catalog.get(s, {}).get("category_slug") == args.category]

    # Сортировка: приоритет 1 → больше скачиваний → первые
    slugs.sort(key=lambda s: (
        catalog.get(s, {}).get("priority", 9),
        -catalog.get(s, {}).get("download_count", 0),
    ))

    # Убираем уже обработанные
    if not args.force:
        done = load_extract_state()
        before = len(slugs)
        slugs = [s for s in slugs if s not in done]
        if before > len(slugs):
            logging.info(f"Пропускаем уже обработанные: {before - len(slugs)}")

    if args.limit:
        slugs = slugs[:args.limit]

    if not slugs:
        logging.info("Нечего обрабатывать.")
        return

    logging.info(f"Будет обработано: {len(slugs)} файлов\n")

    # Обработка
    stats: dict[str, int] = {}

    for i, slug in enumerate(slugs, 1):
        file_path = raw_files[slug]
        cat = catalog.get(slug, {}).get("category_slug", "?")
        logging.info(f"[{i}/{len(slugs)}] {slug[:50]} [{cat}]")

        result = process_file(slug, file_path, method_override=method)
        save_result(result)
        stats[result.status] = stats.get(result.status, 0) + 1

    # Итог
    ok_total = sum(v for k, v in stats.items() if k.startswith("ok_"))
    logging.info(f"\n{'='*55}")
    logging.info(f"Результаты ({len(slugs)} файлов):")
    for status, count in sorted(stats.items()):
        logging.info(f"  {status:<15}: {count}")

    # Сводка по объёму
    total_chars = sum(
        Path(TEXT_DIR / f"{s}.txt").stat().st_size
        for s in slugs
        if (TEXT_DIR / f"{s}.txt").exists()
    )
    logging.info(f"  Всего текста: {total_chars // 1024} KB")


if __name__ == "__main__":
    main()
