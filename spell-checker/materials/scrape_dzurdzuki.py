"""
Скачивает тексты на ингушском языке с dzurdzuki.com/biblioteka
Использует Playwright для перехвата реальных загрузок файлов.
Запуск: python3 -u scrape_dzurdzuki.py
"""

import asyncio
import re
import os
import sys
import io
import fitz
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

CATEGORIES = {
    "na-ingushskom":    "На ингушском языке (208)",
    "folklor":          "Фольклор (59)",
    "poeziya":          "Поэзия (69)",
    "detskaya":         "Детская (29)",
    "loaman-iujre":     "Лоаман Iуйре (29)",
    "hudozhestvennaya": "Художественная (148)",
}

DOWNLOAD_DIR    = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\corpus_downloads"
DICTIONARY_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"

INGUSH_PATTERN = re.compile(
    r'(ӏ|гӏ|хь|кх|аь|еь|оь|уь|иь|ийта|аьнна|елла|овла|еннаб)',
    re.IGNORECASE
)


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def extract_ingush_words(text: str) -> set[str]:
    text = normalize_palochka(text.lower())
    words = set()
    for word in re.findall(r'[а-яёӏ][а-яёӏ\-]*', text):
        word = word.strip('-')
        if len(word) >= 2 and INGUSH_PATTERN.search(word):
            words.add(word)
    return words


def load_existing_words(path: str) -> set[str]:
    words = set()
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    words.add(line)
    except FileNotFoundError:
        pass
    return words


async def scrape_category(browser, slug: str, name: str, existing_words: set, total_added: list):
    url = f"https://dzurdzuki.com/biblioteka/?wpdmc={slug}"
    category_dir = os.path.join(DOWNLOAD_DIR, slug)
    os.makedirs(category_dir, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"Категория: {name}")

    page = await browser.new_page()
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(4000)
    except Exception as e:
        print(f"  Ошибка загрузки страницы: {e}")
        await page.close()
        return

    # Извлекаем заголовки и onclick URL из таблицы
    html = await page.content()
    onclick_urls = re.findall(
        r"wpdm-download-link[^>]+onclick=\"location\.href='([^']+)'",
        html
    )

    # Заголовки книг — берём из td с классом title или вторую колонку
    title_elements = await page.query_selector_all('td.package-title, td:nth-child(2) .package-title, td:nth-child(2) a:first-child')
    titles = []
    for el in title_elements:
        t = (await el.inner_text()).strip()
        if t and len(t) > 3:
            titles.append(t)

    # Если заголовки не нашлись — используем slug + номер
    if len(titles) < len(onclick_urls):
        titles = [f"{slug}_{i+1}" for i in range(len(onclick_urls))]

    print(f"  Найдено файлов: {len(onclick_urls)}")

    for i, dl_url in enumerate(onclick_urls):
        title = titles[i] if i < len(titles) else f"{slug}_{i+1}"
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:60]
        dest = os.path.join(category_dir, f"{i+1:03d}_{safe_title}.pdf")

        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            # Уже скачан — просто обрабатываем
            pass
        else:
            # Открываем страницу скачивания и перехватываем файл
            try:
                dl_page = await browser.new_page()
                async with dl_page.expect_download(timeout=30000) as dl_info:
                    await dl_page.goto(dl_url, timeout=30000)

                download = await dl_info.value
                await download.save_as(dest)
                await dl_page.close()
            except Exception as e:
                # Пробуем второй способ — прямой переход
                try:
                    await dl_page.close()
                except Exception:
                    pass
                try:
                    dl_page2 = await browser.new_page()
                    async with dl_page2.expect_download(timeout=20000) as dl_info2:
                        await dl_page2.evaluate(f"window.location.href = '{dl_url}'")
                    download2 = await dl_info2.value
                    await download2.save_as(dest)
                    await dl_page2.close()
                except Exception as e2:
                    print(f"  ✗ [{i+1}] {safe_title[:40]}: {e2}")
                    continue

        # Извлекаем слова
        try:
            doc = fitz.open(dest)
            text = '\n'.join(p.get_text() for p in doc)
            if len(text.strip()) < 50:
                print(f"  ⚠ [{i+1}] скан: {safe_title[:40]}")
                continue

            words = extract_ingush_words(text)
            new_words = words - existing_words
            if new_words:
                with open(DICTIONARY_PATH, 'a', encoding='utf-8') as f:
                    f.write(f'\n# {slug}: {safe_title[:50]}\n')
                    for w in sorted(new_words):
                        f.write(w + '\n')
                existing_words.update(new_words)
                total_added[0] += len(new_words)
                print(f"  ✓ [{i+1}] {safe_title[:40]} (+{len(new_words)} слов)")
            else:
                print(f"  ✓ [{i+1}] {safe_title[:40]} (новых слов нет)")
        except Exception as e:
            print(f"  ✗ [{i+1}] ошибка чтения PDF: {e}")

    await page.close()


async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print("Загружаю словарь...")
    existing_words = load_existing_words(DICTIONARY_PATH)
    print(f"Слов в словаре: {len(existing_words):,}")

    total_added = [0]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            downloads_path=DOWNLOAD_DIR,
        )
        for slug, name in CATEGORIES.items():
            await scrape_category(browser, slug, name, existing_words, total_added)

        await browser.close()

    print(f"\n{'='*55}")
    print(f"Готово! Добавлено новых слов: {total_added[0]:,}")
    print(f"Итого в словаре: {len(existing_words):,}")


if __name__ == '__main__':
    asyncio.run(main())
