"""
align_luke_ocr.py — OCR Ingush Luke + fetch Russian Luke → parallel pairs

Sources:
  Ingush: inh_cyrillic_Luke.pdf  (52 pages, two-column layout, custom font encoding)
  Russian: bible.by synodal, Luke (book 42), 24 chapters

Run:
    python align_luke_ocr.py          # dry-run: stats only
    python align_luke_ocr.py --write  # append pairs to dataset
"""

import re, json, sys, subprocess, tempfile, os, time, argparse
from pathlib import Path
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

CORPUS_DIR = Path(__file__).parent.parent
PDF_LUKE   = Path(r"C:\Users\goygo\OneDrive\Desktop\bilingual\inh_cyrillic_Luke.pdf")
CACHE_FILE = Path(r"C:\Users\goygo\OneDrive\Desktop\bilingual\rus_bible_cache.json")
OUT_FILE   = CORPUS_DIR / "dataset" / "parallel_ing_rus.jsonl"
TESS_EXE   = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
SOURCE     = "bible-luke"
UA         = "GhalghayTools/1.0 (ingush-corpus; educational)"

LUKE_CHAPTERS = 24

# Luke chapter verse counts (for validation)
LUKE_VERSE_COUNTS = {
    1: 80, 2: 52, 3: 38, 4: 44, 5: 39, 6: 49, 7: 50, 8: 56,
    9: 62, 10: 42, 11: 54, 12: 59, 13: 35, 14: 35, 15: 32,
    16: 31, 17: 37, 18: 43, 19: 48, 20: 47, 21: 38, 22: 71,
    23: 56, 24: 53,
}


# ---------------------------------------------------------------------------
# Russian text: fetch + cache
# ---------------------------------------------------------------------------

def fetch_russian_luke(cache: dict) -> dict:
    """Fetch all 24 chapters of Russian Luke from bible.by. Returns {ch: {v: text}}."""
    if "Luke" in cache:
        print("  Russian Luke already in cache.")
        return cache["Luke"]

    print("  Fetching Russian Luke from bible.by (24 chapters)...")
    luke_data = {}
    for ch in range(1, LUKE_CHAPTERS + 1):
        url = f"https://bible.by/syn/42/{ch}/"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"    ERROR fetching ch {ch}: {e}")
            continue

        verses = re.findall(
            r'<sup>(\d+)</sup>\s*(.*?)(?=<sup>|\Z)', html, re.DOTALL
        )
        ch_data = {}
        for vnum, vtext in verses:
            clean = re.sub(r'<[^>]+>', '', vtext).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if clean:
                ch_data[vnum] = clean
        luke_data[str(ch)] = ch_data
        print(f"    ch {ch:2d}: {len(ch_data)} verses")
        time.sleep(0.5)

    cache["Luke"] = luke_data
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"  Saved to cache. Total Luke verses: {sum(len(v) for v in luke_data.values())}")
    return luke_data


# ---------------------------------------------------------------------------
# Ingush OCR extraction
# ---------------------------------------------------------------------------

def ocr_page(pix, tmp_dir: str) -> str:
    """OCR a fitz Pixmap using Tesseract (Russian model). Returns text."""
    tmp_png = os.path.join(tmp_dir, "page.png")
    out_base = os.path.join(tmp_dir, "page_out")
    pix.save(tmp_png)

    result = subprocess.run(
        [TESS_EXE, tmp_png, out_base, "-l", "rus", "--psm", "1"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    Tesseract error: {result.stderr[:100]}")
        return ""

    with open(out_base + ".txt", encoding="utf-8") as f:
        text = f.read()
    return text


def ocr_all_pages(doc) -> str:
    """OCR all pages of a fitz document and return concatenated text."""
    import fitz
    mat = fitz.Matrix(2.5, 2.5)  # 2.5x zoom for good OCR quality
    all_text = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i in range(len(doc)):
            if i % 5 == 0:
                print(f"  OCR: page {i+1}/{len(doc)}...")
            pix = doc[i].get_pixmap(matrix=mat)
            text = ocr_page(pix, tmp_dir)
            all_text.append(text)

    return "\n\n".join(all_text)


def clean_ocr(text: str) -> str:
    """Normalize OCR output."""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_ingush_verses(ocr_text: str) -> dict:
    """
    Parse OCR'd Luke into {(chapter, verse): text} dict.

    Chapter headers: 'КОРТА N' (Ingush word for chapter)
    Verse numbers:   lines starting with 'N.' or 'N. '

    Key challenge: chapter headers are RUNNING PAGE HEADERS - they appear at
    the top of each column. So 'КОРТА 2' can appear before the last few verses
    of chapter 1 (which spill from the previous page). We delay the chapter
    switch until we actually see verse 1 (or a low verse number ≤ 5) that fits
    the new chapter, rather than immediately on seeing the header.
    """
    lines = ocr_text.split('\n')
    result = {}
    current_ch   = 1      # Luke starts at chapter 1 from the first content page
    current_v    = None
    current_text = []
    pending_ch   = None   # chapter from latest КОРТА header, not yet confirmed
    pending_v1   = []     # text lines seen after chapter header, before first numbered verse

    def flush():
        if current_ch and current_v and current_text:
            t = ' '.join(current_text).strip()
            if t:
                result[(current_ch, current_v)] = t

    def flush_pending_v1(ch: int, lines_buf: list):
        """Save accumulated text as verse 1 of 'ch' if it looks substantive."""
        t = ' '.join(lines_buf).strip()
        # Strip known non-verse artifacts (page numbers, short headers)
        t = re.sub(r'^\d+\s*$', '', t).strip()
        if len(t) > 15 and (ch, 1) not in result:
            result[(ch, 1)] = t

    # Chapter patterns (КОРТА, КОРТАН, etc.)
    ch_pat = re.compile(r'КОРТ[АН]*\.?\s+(\d+)', re.IGNORECASE)
    # Verse number at start of line: "12." or "12. " or "12,"
    v_pat  = re.compile(r'^\s*(\d{1,3})[.,]\s+(.+)')

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for chapter header — only record as pending
        cm = ch_pat.search(line_stripped)
        if cm:
            h_ch = int(cm.group(1))
            if h_ch != current_ch:
                pending_ch = h_ch
                pending_v1 = []
            continue

        # Check for verse start
        vm = v_pat.match(line_stripped)
        if vm:
            v_num = int(vm.group(1))

            # Decide which chapter this verse belongs to.
            # If there's a pending chapter, switch to it only when we see
            # a "restart" verse (≤ 5) that fits the new chapter.
            if pending_ch is not None and v_num <= 5:
                max_new = LUKE_VERSE_COUNTS.get(pending_ch, 80)
                if 1 <= v_num <= max_new:
                    flush()
                    # Save anything collected before this numbered verse as v1
                    if v_num >= 2:
                        flush_pending_v1(pending_ch, pending_v1)
                    current_ch   = pending_ch
                    pending_ch   = None
                    pending_v1   = []
                    current_v    = None
                    current_text = []

            # Sanity check: verse number should fit current chapter
            expected_max = LUKE_VERSE_COUNTS.get(current_ch, 80)
            if 1 <= v_num <= expected_max + 2:
                flush()
                current_v    = v_num
                current_text = [vm.group(2).strip()]
                continue

        # Text that is neither a chapter header nor a numbered verse
        if pending_ch is not None:
            # Collecting potential verse 1 content for the pending chapter
            pending_v1.append(line_stripped)
        elif current_v is not None:
            current_text.append(line_stripped)

    flush()
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--write', action='store_true')
    return p.parse_args()


def main():
    args = parse_args()

    try:
        import fitz
    except ImportError:
        print("PyMuPDF not installed. Run: pip install pymupdf")
        sys.exit(1)

    # Load cache
    with open(CACHE_FILE, encoding='utf-8') as f:
        cache = json.load(f)

    print("Step 1: Fetching Russian Luke...")
    rus_luke = fetch_russian_luke(cache)

    print("\nStep 2: OCR Ingush Luke PDF...")
    doc = fitz.open(str(PDF_LUKE))
    print(f"  Pages: {len(doc)}")

    ocr_text = ocr_all_pages(doc)
    print(f"  OCR complete. Total chars: {len(ocr_text):,}")

    print("\nStep 3: Parsing Ingush verses...")
    ing_verses = parse_ingush_verses(ocr_text)
    print(f"  Parsed {len(ing_verses)} Ingush verse entries")

    # Build pairs
    pairs = []
    missing_rus = []
    missing_ing = []

    for ch in range(1, LUKE_CHAPTERS + 1):
        ch_str = str(ch)
        rus_ch = rus_luke.get(ch_str, {})
        expected = LUKE_VERSE_COUNTS.get(ch, 0)

        for v in range(1, expected + 1):
            v_str = str(v)
            ing_text = ing_verses.get((ch, v))
            rus_text = rus_ch.get(v_str)

            if ing_text and rus_text and len(ing_text) > 5 and len(rus_text) > 5:
                pairs.append({
                    "ing": ing_text,
                    "rus": rus_text,
                    "source": SOURCE,
                    "type": "verse",
                    "ref": f"Luke.{ch}.{v}",
                })
            else:
                if not ing_text:
                    missing_ing.append(f"Luke.{ch}.{v}")
                if not rus_text:
                    missing_rus.append(f"Luke.{ch}.{v}")

    total_expected = sum(LUKE_VERSE_COUNTS.values())
    print(f"\nResults:")
    print(f"  Expected verses: {total_expected}")
    print(f"  OK pairs: {len(pairs)}")
    print(f"  Missing Ingush: {len(missing_ing)}")
    print(f"  Missing Russian: {len(missing_rus)}")

    if missing_ing[:10]:
        print(f"  First missing Ing: {missing_ing[:10]}")

    # Show samples
    print("\nSample pairs:")
    for p in pairs[:3]:
        print(f"  [{p['ref']}]")
        print(f"    ING: {p['ing'][:80]}")
        print(f"    RUS: {p['rus'][:80]}")

    if not args.write:
        print(f"\n[dry-run] Would append {len(pairs)} pairs. Use --write to commit.")
        return

    with open(OUT_FILE, 'a', encoding='utf-8') as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    total = sum(1 for _ in open(OUT_FILE, encoding='utf-8'))
    chars_ing = sum(len(p['ing']) for p in pairs)
    chars_rus = sum(len(p['rus']) for p in pairs)
    print(f"\nAppended {len(pairs)} pairs → {OUT_FILE}")
    print(f"Dataset total: {total} records")
    print(f"Chars (ing): {chars_ing:,}  |  (rus): {chars_rus:,}")


if __name__ == '__main__':
    main()
