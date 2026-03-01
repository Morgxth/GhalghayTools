# Parallel Ingush–Russian Dataset

**File:** `parallel_ing_rus.jsonl`
**Format:** JSONL — each line is a JSON object with fields `ing`, `rus`, `source`, `type`

## Current Stats (2026-03-01)

| Source | Pairs | Type | Notes |
|--------|-------|------|-------|
| bible-genesis | 1527 | verse | EPUB, verse-ID aligned |
| bible-luke | 1128 | verse | PDF OCR (Tesseract/rus), 97.9% coverage |
| bible-proverbs | 915 | verse | EPUB, verse-ID aligned |
| bible-john | 877 | verse | EPUB, verse-ID aligned |
| bible-esther | 167 | verse | EPUB, verse-ID aligned |
| nartskij-epos-ingushej-2017 | 148 | story | TXT, section-number aligned |
| kipling-rikki-tikki-1939 | 91 | sentence | OCR + Gale-Church alignment |
| bible-ruth | 85 | verse | EPUB, verse-ID aligned |
| garshin-signal-1962 | 71 | sentence | TXT + Gale-Church alignment |
| bible-jonah | 48 | verse | EPUB, verse-ID aligned |
| pushkin-2014 | 22 | poem | PDF char-position + lib.ru/WikiSource |
| marshak-* | 4 | poem | Manual 1-poem-1-pair entries |
| **TOTAL** | **5083** | | |

**Ingush chars:** ~1.24M
**Russian chars:** ~2.21M

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
- Aligned by section number (1..N in each half)
- Script: `corpus/scraper/align_nart_epic.py`

### Pushkin 2014: bilingual PDF
- 22 poems extracted by character positions from PDF
- Russian originals from lib.ru p2.txt, p3.txt (koi8-r), WikiSource
- Script: `corpus/scraper/align_pushkin_2014.py`

## Pending Sources

| Book | Pages | Status | Notes |
|------|-------|--------|-------|
| Shakespeare "Укрощение строптивой" | 173pp | TEXT layer 168/173pp | Need scene-level aligner |
| Turgenev "Муму" | 25pp | SCAN | Short — good OCR candidate |
| Nekrasov "Мороз, Красный нос" | 45pp | SCAN | Narrative poem, 1940 |
| Гюго "Гаврош" | 35pp | SCAN | Short excerpt |
| Лермонтов "Герой нашего времени" | 202pp | SCAN | Full novel — complex |
| Гайдар "Дальние страны" | 98pp | SCAN | Children's stories |
| Бианки "На великом морском пути" | 53pp | SCAN | Children's stories |
| Пришвин "Журка" | 20pp | SCAN | Short, OCR looks good |
| Quran tafsir | 672pp | TEXT | Tafsir (commentary), needs Russian tafsir |
| Pushkin 1941 fairy tales | ~20pp | OCR TXT | Overlaps with 2014 edition |

## Scripts

```
corpus/scraper/
  align_nart_epic.py     — Nart Epic section alignment
  align_pushkin_2014.py  — Pushkin 2014 PDF poem extraction
  align_luke_ocr.py      — Luke PDF OCR + verse alignment
  align_prose.py         — Gale-Church prose alignment (Garshin, Kipling)
  fetch_russian_originals.py — Download Russian texts
```

## Target Use

Fine-tuning NLLB-200 (or similar) for Ingush ↔ Russian translation.
Recommended split: 80% train, 10% dev, 10% test.
