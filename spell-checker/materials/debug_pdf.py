"""
Смотрим как выглядит сырой текст из PDF — правая колонка, первые 5 страниц.
"""
import fitz
import sys
sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Куркиев А.С. Ингушско-русский словарь (2005).pdf"
START_PAGE = 18

doc = fitz.open(PDF_PATH)

for page_num in range(START_PAGE, START_PAGE + 3):
    page = doc[page_num]
    mid = page.rect.width / 2
    print(f"\n{'='*60}")
    print(f"СТРАНИЦА {page_num + 1}")
    print(f"{'='*60}")

    blocks = page.get_text("blocks")
    right_blocks = sorted(
        [(x0, y0, text) for x0, y0, x1, y1, text, *_ in blocks if x0 >= mid],
        key=lambda b: b[1]
    )

    left_blocks = sorted(
        [(x0, y0, text) for x0, y0, x1, y1, text, *_ in blocks if x0 < mid],
        key=lambda b: b[1]
    )

    print(f"  mid={mid:.0f}")
    print("\n--- ЛЕВАЯ + ПРАВАЯ (первые 10 пар по y) ---")
    for i, ((lx, ly, lt), (rx, ry, rt)) in enumerate(zip(left_blocks[:10], right_blocks[:10])):
        print(f"\n  L[y={ly:.0f}]: {repr(lt[:80])}")
        print(f"  R[y={ry:.0f}]: {repr(rt[:80])}")
