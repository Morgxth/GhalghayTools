"""
Batch pipeline: fetch Russian originals + OCR Ingush PDFs + LaBSE alignment.
Processes all pending sources and appends to the main dataset.
Run from repo root or corpus/scraper/.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import fitz
import numpy as np
from sentence_transformers import SentenceTransformer

# ─── Config ───────────────────────────────────────────────────────────────────

TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MODEL_NAME = "lingtrain/labse-ingush"
DATASET = Path(r"C:\Users\goygo\OneDrive\Desktop\GhalghayTools\corpus\dataset\parallel_ing_rus.jsonl")
RUS_DIR  = Path(r"C:\Users\goygo\OneDrive\Desktop\GhalghayTools\corpus\russian_originals")
BILINGUAL = Path(r"C:\Users\goygo\OneDrive\Desktop\bilingual")
THRESHOLD = 0.30
WINDOW    = 15
LOG = []

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ─── HTML text extractor ──────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self._skip = True
        if tag in ('p', 'br', 'div'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)
    def get_text(self):
        return re.sub(r'\n{3,}', '\n\n', ''.join(self.parts)).strip()


def strip_html(html: str) -> str:
    p = TextExtractor()
    p.feed(html)
    return p.get_text()


def fetch(url: str, encoding: str = 'utf-8') -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    html = raw.decode(encoding, errors='replace')
    return strip_html(html)


def fetch_multipage(base_url_tpl: str, encoding: str = 'utf-8', max_pages: int = 30) -> str:
    """Fetch paginated ilibrary.ru text (p.1, p.2, ...)"""
    parts = []
    for i in range(1, max_pages + 1):
        url = base_url_tpl.format(i)
        try:
            text = fetch(url, encoding)
            # Stop if page repeats or too short
            if len(text) < 300:
                break
            parts.append(text)
        except Exception:
            break
    return '\n'.join(parts)


# ─── Shared align functions (copied from align_labse.py) ─────────────────────

_SENT_END = re.compile(
    r'(?<=[^А-ЯA-Z\d])[.!?…]+(?=\s+[А-ЯA-ZЁ«"\u201C]|$)',
    re.UNICODE
)


def normalize_ingush(text: str) -> str:
    text = text.replace('\xad', '')
    text = re.sub(r'-\n', '', text)
    return text


def split_sentences(text: str) -> list:
    text = normalize_ingush(text)
    text = text.replace('\f', '\n').replace('\r\n', '\n')
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        words = line.split()
        if not words:
            continue
        if len(words) <= 2 and (line.isdigit() or line.isupper()):
            continue
        cleaned.append(line)
    text = ' '.join(cleaned)
    parts = _SENT_END.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 12]


def ocr_pdf(pdf_path: str, skip_pages: set = None) -> str:
    skip_pages = skip_pages or set()
    doc = fitz.open(pdf_path)
    all_text = []
    print(f"  OCR: {len(doc)} pages", flush=True)
    for i, page in enumerate(doc):
        if i in skip_pages:
            continue
        mat = fitz.Matrix(400 / 72, 400 / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img_path = f.name
        pix.save(img_path)
        out_base = img_path.replace('.png', '_out')
        subprocess.run(
            [TESSERACT, img_path, out_base, '-l', 'rus', '--psm', '6'],
            capture_output=True
        )
        txt_path = out_base + '.txt'
        try:
            with open(txt_path, encoding='utf-8') as f:
                all_text.append(f.read())
            os.unlink(txt_path)
        except Exception:
            pass
        os.unlink(img_path)
        if (i + 1) % 20 == 0:
            print(f"    page {i+1}/{len(doc)}", flush=True)
    return '\n'.join(all_text)


def embed(model, sentences: list) -> np.ndarray:
    return model.encode(sentences, batch_size=32, normalize_embeddings=True,
                        show_progress_bar=False)


def dp_align(ing_emb, rus_emb, window=15):
    N, M = len(ing_emb), len(rus_emb)
    sim = ing_emb @ rus_emb.T
    NEG = -1e9
    dp = np.full((N + 1, M + 1), NEG)
    dp[0][0] = 0.0
    back = np.full((N + 1, M + 1, 2), -1, dtype=int)
    ratio = M / max(N, 1)
    for i in range(1, N + 1):
        ej = i * ratio
        j_lo = max(1, int(ej - window))
        j_hi = min(M, int(ej + window) + 1)
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            # match
            if dp[i-1][j-1] > NEG:
                s = dp[i-1][j-1] + sim[i-1][j-1]
                if s > dp[i][j]:
                    dp[i][j] = s; back[i][j] = [i-1, j-1]
            # skip ing
            if dp[i-1][j] > NEG:
                s = dp[i-1][j] - 0.05
                if s > dp[i][j]:
                    dp[i][j] = s; back[i][j] = [i-1, j]
            # skip rus
            if dp[i][j-1] > NEG:
                s = dp[i][j-1] - 0.05
                if s > dp[i][j]:
                    dp[i][j] = s; back[i][j] = [i, j-1]
    if dp[N][M] == NEG:
        best_j = int(np.argmax(dp[N]))
        if dp[N][best_j] == NEG:
            return []
        i, j = N, best_j
    else:
        i, j = N, M
    pairs = []
    while i > 0 or j > 0:
        pi, pj = int(back[i][j][0]), int(back[i][j][1])
        if pi < 0 or pj < 0:
            break
        if pi == i-1 and pj == j-1:
            pairs.append((i-1, j-1, float(sim[i-1][j-1])))
        i, j = pi, pj
    pairs.reverse()
    return pairs


def existing_sources():
    if not DATASET.exists():
        return set()
    with open(DATASET, encoding='utf-8') as f:
        return set(json.loads(l)['source'] for l in f)


def write_pairs(pairs_data: list, source: str, pair_type: str):
    with open(DATASET, 'a', encoding='utf-8') as f:
        for ing, rus in pairs_data:
            f.write(json.dumps({'ing': ing, 'rus': rus, 'source': source, 'type': pair_type},
                               ensure_ascii=False) + '\n')


def process(name, slug, pair_type, ing_pdf, rus_text,
            skip_pages=None, rus_start_after=None):
    """Full pipeline for one source."""
    print(f"\n{'='*60}", flush=True)
    print(f"Processing: {name} [{slug}]", flush=True)

    ex = existing_sources()
    if slug in ex:
        print(f"  SKIP — already in dataset", flush=True)
        LOG.append((name, slug, 0, 'skipped'))
        return

    # Clean russian text
    rus = rus_text
    if rus_start_after:
        idx = rus.find(rus_start_after)
        if idx >= 0:
            rus = rus[idx:]

    # OCR ingush
    print(f"  OCR Ingush PDF...", flush=True)
    try:
        ing_raw = ocr_pdf(ing_pdf, skip_pages or set())
    except Exception as e:
        print(f"  OCR FAILED: {e}", flush=True)
        LOG.append((name, slug, 0, f'OCR error: {e}'))
        return

    # Split sentences
    ing_sents = split_sentences(ing_raw)
    rus_sents = split_sentences(rus)
    print(f"  Sentences: {len(ing_sents)} ing / {len(rus_sents)} rus", flush=True)

    if len(ing_sents) < 5 or len(rus_sents) < 5:
        print(f"  TOO FEW SENTENCES — skipping", flush=True)
        LOG.append((name, slug, 0, 'too few sentences'))
        return

    # Embed
    print(f"  Embedding...", flush=True)
    ing_emb = embed(MODEL, ing_sents)
    rus_emb = embed(MODEL, rus_sents)

    # Align
    pairs = dp_align(ing_emb, rus_emb, window=WINDOW)
    kept = [(ing_sents[i], rus_sents[j]) for i, j, s in pairs if s >= THRESHOLD]
    print(f"  Aligned: {len(pairs)}, kept: {len(kept)} (threshold={THRESHOLD})", flush=True)

    # Sample
    for ing, rus_s in kept[:3]:
        print(f"  ING: {ing[:70]}", flush=True)
        print(f"  RUS: {rus_s[:70]}", flush=True)
        print(flush=True)

    # Write
    write_pairs(kept, slug, pair_type)
    print(f"  Wrote {len(kept)} pairs", flush=True)
    LOG.append((name, slug, len(kept), 'ok'))


# ─── Load model once ─────────────────────────────────────────────────────────

print("Loading LaBSE model...", flush=True)
MODEL = SentenceTransformer(MODEL_NAME)
print("Model ready.", flush=True)

# ─── Fetch Russian texts ──────────────────────────────────────────────────────

print("\nFetching Russian texts...", flush=True)

def save_rus(slug, text):
    p = RUS_DIR / f"{slug}_rus.txt"
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"  Saved {slug}_rus.txt ({len(text)} chars)", flush=True)
    return text


# 1. Тургенев Муму
slug_mumu = 'turgenev-mumu-1939'
if not (RUS_DIR / f"{slug_mumu}_rus.txt").exists():
    try:
        print("Fetching Тургенев Муму...", flush=True)
        text = fetch('https://lib.ru/LITRA/TURGENEW/mumu.txt', encoding='koi8-r')
        # Remove lib.ru header (first ~10 lines)
        lines = text.split('\n')
        # Find where story actually starts (first paragraph with Gerасим or big paragraph)
        start = 0
        for k, l in enumerate(lines):
            if 'Герасим' in l or 'герасим' in l.lower() or len(l) > 100:
                start = k
                break
        text = '\n'.join(lines[start:])
        save_rus(slug_mumu, text)
    except Exception as e:
        print(f"  Failed to fetch Муму: {e}", flush=True)
        # Try ilibrary
        try:
            text = fetch('https://ilibrary.ru/text/1250/p.1/index.html')
            save_rus(slug_mumu, text)
        except Exception as e2:
            print(f"  Also failed ilibrary: {e2}", flush=True)
else:
    text = (RUS_DIR / f"{slug_mumu}_rus.txt").read_text(encoding='utf-8')

rus_mumu = text


# 2. Некрасов Мороз Красный нос
slug_nek = 'nekrasov-moroz-1940'
if not (RUS_DIR / f"{slug_nek}_rus.txt").exists():
    try:
        print("Fetching Некрасов Мороз Красный нос...", flush=True)
        text = fetch('https://lib.ru/LITRA/NEKRASOW/moroz.txt', encoding='koi8-r')
        save_rus(slug_nek, text)
    except Exception as e:
        print(f"  Failed lib.ru Некрасов: {e}", flush=True)
        try:
            # Try other URL patterns
            for url in [
                'https://lib.ru/NEKRASOW/moroz.txt',
                'https://ilibrary.ru/text/1013/p.1/index.html',
            ]:
                try:
                    text = fetch(url, encoding='koi8-r')
                    if len(text) > 3000:
                        save_rus(slug_nek, text)
                        break
                except:
                    pass
        except Exception as e2:
            print(f"  Also failed: {e2}", flush=True)
            text = ''
else:
    text = (RUS_DIR / f"{slug_nek}_rus.txt").read_text(encoding='utf-8')

rus_nek = text


# 3. Бианки — try lib.ru
slug_bianki = 'bianki-morskoy-put-1939'
if not (RUS_DIR / f"{slug_bianki}_rus.txt").exists():
    print("Fetching Бианки На великом морском пути...", flush=True)
    text = ''
    for url, enc in [
        ('https://lib.ru/LITRA/BIANKI/morskoy.txt', 'koi8-r'),
        ('https://lib.ru/BIANKI/morskoy.txt', 'koi8-r'),
        ('https://ilibrary.ru/text/bianki-morskoy/p.1/index.html', 'utf-8'),
    ]:
        try:
            text = fetch(url, encoding=enc)
            if len(text) > 2000:
                save_rus(slug_bianki, text)
                break
        except Exception as e:
            print(f"  Failed {url}: {e}", flush=True)
    if not text:
        print("  Бианки text not found — will try WebFetch manually", flush=True)
else:
    text = (RUS_DIR / f"{slug_bianki}_rus.txt").read_text(encoding='utf-8')
rus_bianki = text


# 4. Гайдар Дальние страны
slug_gaidar = 'gaidar-dalnie-strany-1940'
if not (RUS_DIR / f"{slug_gaidar}_rus.txt").exists():
    print("Fetching Гайдар Дальние страны...", flush=True)
    text = ''
    for url, enc in [
        ('https://lib.ru/GAJDAR/dalstran.txt', 'koi8-r'),
        ('https://lib.ru/LITRA/GAJDAR/dalstran.txt', 'koi8-r'),
        ('https://lib.ru/GAJDAR/dal_strany.txt', 'koi8-r'),
    ]:
        try:
            text = fetch(url, encoding=enc)
            if len(text) > 2000:
                save_rus(slug_gaidar, text)
                break
        except Exception as e:
            print(f"  Failed {url}: {e}", flush=True)
    if not text:
        print("  Гайдар text not found", flush=True)
else:
    text = (RUS_DIR / f"{slug_gaidar}_rus.txt").read_text(encoding='utf-8')
rus_gaidar = text


# 5. Гюго Гаврош (отдельная книга — excerpts from Отверженные)
slug_gyugo = 'gyugo-gavrosh-1939'
if not (RUS_DIR / f"{slug_gyugo}_rus.txt").exists():
    print("Fetching Гюго Гаврош (Отверженные)...", flush=True)
    text = ''
    for url, enc in [
        ('https://lib.ru/GUGO/otverj2.txt', 'koi8-r'),
        ('https://lib.ru/LITRA/GYUGO/otverj.txt', 'koi8-r'),
        ('https://lib.ru/GUGO/otverj.txt', 'koi8-r'),
    ]:
        try:
            text = fetch(url, encoding=enc)
            if len(text) > 5000:
                # Gavrosh is in the middle — find the Gavrosh section
                idx = text.find('Гаврош')
                if idx > 0:
                    text = text[max(0, idx-500):]
                save_rus(slug_gyugo, text)
                break
        except Exception as e:
            print(f"  Failed {url}: {e}", flush=True)
    if not text:
        print("  Гюго text not found", flush=True)
else:
    text = (RUS_DIR / f"{slug_gyugo}_rus.txt").read_text(encoding='utf-8')
rus_gyugo = text


# 6. Шекспир — Russian TXT already exists, just clean it
shakes_rus_path = BILINGUAL / 'шекспир' / 'shekspir-u-ardagiyar-kiadyar-perevod-yandieva-m-a-2009_rus.txt'
slug_shakes = 'shakespeare-taming-2009'
if shakes_rus_path.exists():
    rus_shakes = shakes_rus_path.read_text(encoding='utf-8')
    # Strip lib.ru header — play starts after cast list / before ИНТРОДУКЦИЯ
    idx = rus_shakes.find('ИНТРОДУКЦИЯ')
    if idx > 0:
        rus_shakes = rus_shakes[idx:]
else:
    rus_shakes = ''


# 7. Лермонтов ГНВ
slug_lerm = 'lermontov-geroj-1940'
if not (RUS_DIR / f"{slug_lerm}_rus.txt").exists():
    print("Fetching Лермонтов Герой нашего времени...", flush=True)
    text = ''
    for url, enc in [
        ('https://lib.ru/LITRA/LERMONTOW/geroi.txt', 'utf-8'),
        ('https://lib.ru/LERMONTOW/geroi.txt', 'koi8-r'),
    ]:
        try:
            text = fetch(url, encoding=enc)
            if len(text) > 10000:
                save_rus(slug_lerm, text)
                break
        except Exception as e:
            print(f"  Failed {url}: {e}", flush=True)
    if not text:
        print("  Лермонтов text not found", flush=True)
else:
    text = (RUS_DIR / f"{slug_lerm}_rus.txt").read_text(encoding='utf-8')
rus_lerm = text


# ─── Process each source ─────────────────────────────────────────────────────

SOURCES = [
    dict(
        name='Тургенев "Муму"',
        slug=slug_mumu,
        pair_type='sentence',
        ing_pdf=str(BILINGUAL / 'turgenev-i-s-mumu-1939-god.pdf'),
        rus_text=rus_mumu,
    ),
    dict(
        name='Гюго "Гаврош"',
        slug=slug_gyugo,
        pair_type='sentence',
        ing_pdf=str(BILINGUAL / 'Гюго. В. - Гаврош (на ингушском языке) (1939).pdf'),
        rus_text=rus_gyugo,
    ),
    dict(
        name='Некрасов "Мороз, Красный нос"',
        slug=slug_nek,
        pair_type='poem',
        ing_pdf=str(BILINGUAL / 'Некрасов Н. Шелал, ЦIе мераж (Мороз, Красный нос) (пер. на инг. Х.-Б. Муталиева) - 1940 (1).pdf'),
        rus_text=rus_nek,
    ),
    dict(
        name='Бианки "На великом морском пути"',
        slug=slug_bianki,
        pair_type='sentence',
        ing_pdf=str(BILINGUAL / 'Бианки В. - Боккхача форда наькъа тIа (На великом морском пути) (1939).pdf'),
        rus_text=rus_bianki,
    ),
    dict(
        name='Гайдар "Дальние страны"',
        slug=slug_gaidar,
        pair_type='sentence',
        ing_pdf=str(BILINGUAL / 'Гайдар А. Гаьнара мехкаш (Дальние страны) (на ингушском языке) - 1940. (1).pdf'),
        rus_text=rus_gaidar,
    ),
    dict(
        name='Шекспир "Укрощение строптивой"',
        slug=slug_shakes,
        pair_type='play',
        ing_pdf=str(BILINGUAL / 'шекспир' / 'shekspir-u-ardagiyar-kiadyar-perevod-yandieva-m-a-2009.pdf'),
        rus_text=rus_shakes,
    ),
    dict(
        name='Лермонтов "Герой нашего времени"',
        slug=slug_lerm,
        pair_type='sentence',
        ing_pdf=str(BILINGUAL / 'Лермонтов М. Ю. Герой Нашего Времени. На ингушском языке, перевод Б. Зязикова. (1940).pdf'),
        rus_text=rus_lerm,
    ),
]

for src in SOURCES:
    if not src['rus_text'] or len(src['rus_text']) < 500:
        print(f"\nSKIP {src['name']} — no Russian text", flush=True)
        LOG.append((src['name'], src['slug'], 0, 'no Russian text'))
        continue
    try:
        process(**src)
    except Exception as e:
        print(f"\nERROR processing {src['name']}: {e}", flush=True)
        import traceback; traceback.print_exc()
        LOG.append((src['name'], src['slug'], 0, f'error: {e}'))

# ─── Final report ─────────────────────────────────────────────────────────────

print('\n' + '='*60, flush=True)
print('FINAL REPORT', flush=True)
print('='*60, flush=True)
total_added = 0
for name, slug, n, status in LOG:
    print(f"  {name}: +{n} pairs [{status}]", flush=True)
    total_added += n

# Dataset total
with open(DATASET, encoding='utf-8') as f:
    total = sum(1 for _ in f)
print(f"\nTotal dataset: {total} pairs (+{total_added} this run)", flush=True)

# Update DATASET_NOTES if pairs were added
if total_added > 0:
    notes_path = Path(r"C:\Users\goygo\OneDrive\Desktop\GhalghayTools\corpus\DATASET_NOTES.md")
    notes = notes_path.read_text(encoding='utf-8')
    # Update total line
    notes = re.sub(r'\| \*\*TOTAL\*\* \| \*\*\d+\*\* \|', f'| **TOTAL** | **{total}** |', notes)
    notes_path.write_text(notes, encoding='utf-8')
    print(f"Updated DATASET_NOTES.md total to {total}", flush=True)
