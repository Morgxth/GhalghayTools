"""
Тест OCR для Мерешкова — смотрим качество и формат текста.
"""
import fitz, pytesseract, os, sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ['TESSDATA_PREFIX'] = r"C:\Users\goygo\tessdata"

PDF_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Мерешков С.  Краткий Ингушско-русский  краткий фразеологический словарь. 2024 год..pdf"

doc = fitz.open(PDF_PATH)
print(f"Страниц: {doc.page_count}")

# Тестируем 3 страницы из середины словаря
for page_num in [5, 10, 20]:
    page = doc[page_num]
    mat = fitz.Matrix(3.0, 3.0)  # высокое разрешение
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    text = pytesseract.image_to_string(img, lang='rus', config='--psm 6')

    print(f"\n{'='*60}")
    print(f"Страница {page_num + 1}")
    print(f"{'='*60}")
    print(text[:1000])
