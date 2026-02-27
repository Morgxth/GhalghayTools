"""Диагностика: смотрим что реально загружается на странице."""
import asyncio, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Открываю страницу...")
        await page.goto(
            "https://dzurdzuki.com/biblioteka/?wpdmc=na-ingushskom",
            wait_until='domcontentloaded',
            timeout=60000
        )
        print("Страница загружена (domcontentloaded)")

        # Ждём 5 секунд для JS
        await page.wait_for_timeout(5000)

        # Смотрим что есть на странице
        title = await page.title()
        print(f"Заголовок: {title}")

        # Ищем таблицы
        tables = await page.query_selector_all('table')
        print(f"Таблиц на странице: {len(tables)}")

        # Ищем любые ссылки с href
        all_links = await page.query_selector_all('a[href]')
        print(f"Всего ссылок: {len(all_links)}")

        # Ищем ссылки на PDF или скачивание
        pdf_links = []
        for link in all_links:
            href = await link.get_attribute('href') or ''
            cls = await link.get_attribute('class') or ''
            if '.pdf' in href.lower() or 'download' in href.lower() or 'wpdm' in cls:
                text = (await link.inner_text()).strip()[:60]
                pdf_links.append(f"  {text!r} → {href[:80]}")

        print(f"\nСсылок на файлы/скачивание: {len(pdf_links)}")
        for l in pdf_links[:10]:
            print(l)

        # Сохраним HTML для анализа
        html = await page.content()
        with open(r'C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\nHTML сохранён ({len(html)} символов)")

        await browser.close()

asyncio.run(main())
