# Parallel Ingush–Russian Dataset

**File:** `parallel_ing_rus.jsonl`
**Format:** JSONL — each line is a JSON object with fields `ing`, `rus`, `source`, `type`

## Current Stats (2026-03-02)

| Source | Pairs | Type | Notes |
|--------|-------|------|-------|
| nartskij-epos-ingushej-2017 | 5280 | sentence | TXT, section-aligned → LaBSE sentence split (148 sections → 5280 pairs) |
| wiki-inh-* | 5200 | sentence | inh.wikipedia.org ↔ ru.wikipedia.org, LaBSE alignment (401 articles, threshold 0.35) |
| bible-genesis | 1527 | verse | EPUB, verse-ID aligned |
| bible-luke | 1128 | verse | PDF OCR (Tesseract/rus), 97.9% coverage |
| lermontov-geroj-1940 | 1084 | sentence | OCR PSM6 + LaBSE; Russian from lib.ru (koi8-r) |
| shakespeare-taming-2009 | 1030 | play | OCR PSM6 + LaBSE; Russian from lib.ru (koi8-r) |
| bible-proverbs | 915 | verse | EPUB, verse-ID aligned |
| bible-john | 877 | verse | EPUB, verse-ID aligned |
| gaidar-dalnie-strany-1940 | 828 | sentence | OCR PSM6 + LaBSE; Russian from traumlibrary.ru (windows-1251) |
| rus4all-* | ~2200 | sentence/poem | rus4all.ru/inh/ — original Ingush literature with Russian translation |
| gyugo-gavrosh-1939 | 399 | sentence | OCR PSM6 + LaBSE; Russian from nukadeti.ru |
| bianki-morskoy-put-1939 | 319 | sentence | OCR PSM6 + LaBSE; Russian from moreskazok.ru |
| nekrasov-moroz-1940 | 194 | sentence | OCR PSM6 + LaBSE; Russian from lib.ru (koi8-r) |
| bible-esther | 167 | verse | EPUB, verse-ID aligned |
| kipling-rikki-tikki-1939 | 91 | sentence | OCR + Gale-Church alignment |
| bible-ruth | 85 | verse | EPUB, verse-ID aligned |
| garshin-signal-1962 | 71 | sentence | TXT + Gale-Church alignment |
| bible-jonah | 48 | verse | EPUB, verse-ID aligned |
| pushkin-2014 | 22 | poem | PDF char-position + lib.ru/WikiSource |
| prishvin-zhurka-1940 | 19 | sentence | OCR PSM6 + LaBSE alignment |
| turgenev-mumu-1939 | 17 | sentence | OCR PSM6 + LaBSE; Russian from lib.ru (koi8-r) |
| marshak-* | 4 | poem | Manual 1-poem-1-pair entries |
| doshlorg | 438 | phrase | ghalghay.github.io dictionary example sentences |
| **TOTAL** | **21,308** | | after dedup pass1 |

**Ingush chars:** ~3.1M (est.)
**Russian chars:** ~5.5M (est.)

## Sources

### EPUB: `inh_cyrillic_compilation.epub`
- Contains: Genesis, John, Proverbs, Ruth, Esther, Jonah
- Format: `id="Book.Ch.V"` verse markers — perfect alignment
- Russian: fetched from bible.by (Synodal translation), cached in `rus_bible_cache.json`

### PDF with custom font encoding: `inh_cyrillic_Luke.pdf`
- Ingush Gospel of Luke, 52 pages, two-column layout
- Extraction: Tesseract OCR (Russian model, PSM 1), 1128/1151 verses
- Tricky: running page headers cause chapter-boundary bugs — solved with pending-chapter mechanism
- Script: `corpus/scraper/align_luke_ocr.py`

### Text files: Garshin, Kipling
- `Гаршин В М Сигнал (На ингушском языке) 1962 г.txt` — already OCR'd
- `kipling_ing_ocr.txt` — already OCR'd
- Russian: `corpus/russian_originals/garshin-..._rus.txt`, `bilingual/Киплинг/26974.pdf`
- Alignment: Gale-Church DP (character-length-based)
- Script: `corpus/scraper/align_prose.py`

### Nart Epic: `nartskij-epos-ingushej-2017.txt`
- Bilingual book, Ingush and Russian halves in same file
- Phase 1: section-number alignment → 148 section pairs (align_nart_epic.py)
- Phase 2: local LaBSE sentence splitting within each section pair → 5280 sentence pairs
- Script: `corpus/scraper/align_nart_epic.py`, `corpus/scraper/align_nart_sentences.py`

### Pushkin 2014: bilingual PDF
- 22 poems extracted by character positions from PDF
- Russian originals from lib.ru p2.txt, p3.txt (koi8-r), WikiSource
- Script: `corpus/scraper/align_pushkin_2014.py`

### LaBSE pipeline (OCR scans): `align_labse.py`
- Sources: Prishvin, Turgenev, Nekrasov, Shakespeare, Lermontov, Gaidar, Bianki, Гюго
- All Ingush PDFs are scans → Tesseract OCR (PSM 6, lang=rus)
- Russian texts from lib.ru (koi8-r), traumlibrary.ru (windows-1251), or HTML sites (utf-8)
- Ingush palochka (Ӏ) appears as: 1, [, ], |, ! — LaBSE handles the variation
- DP alignment with ratio-aware band window (`expected_j = i * M/N ± window`)
- Threshold: 0.3 cosine similarity minimum
- Russian originals saved in `corpus/russian_originals/`

## Pending Sources

| Book | Pages | Status | Notes |
|------|-------|--------|-------|
| Quran tafsir | 672pp | TEXT | Tafsir (commentary), needs Russian tafsir |
| Pushkin 1941 fairy tales | ~20pp | OCR TXT | Overlaps with 2014 edition |

## Scripts

```
corpus/scraper/
  align_nart_epic.py     — Nart Epic section alignment
  align_pushkin_2014.py  — Pushkin 2014 PDF poem extraction
  align_luke_ocr.py      — Luke PDF OCR + verse alignment
  align_prose.py         — Gale-Church prose alignment (Garshin, Kipling)
  align_labse.py         — LaBSE (lingtrain/labse-ingush) OCR+alignment pipeline
  process_all_sources.py — Batch processor (runs all pending sources)
  fetch_russian_originals.py — Download Russian texts
```

## Target Use

Fine-tuning NLLB-200 (or similar) for Ingush ↔ Russian translation.
Recommended split: 80% train, 10% dev, 10% test.
