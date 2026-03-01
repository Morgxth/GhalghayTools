"""
align_prose.py — Align short Ingush/Russian prose using Gale-Church algorithm

Usage:
    python align_prose.py garshin     # dry-run Garshin Signal
    python align_prose.py garshin --write
    python align_prose.py kipling     # Rikki-Tikki-Tavi
    python align_prose.py kipling --write

Algorithm:
  1. Split both texts into sentences
  2. Gale-Church DP alignment by character lengths
  3. Output 1:1 sentence pairs (skipping 0:1 or 1:0 alignments for quality)
"""

import re, json, sys, argparse
from pathlib import Path
import math

sys.stdout.reconfigure(encoding='utf-8')

CORPUS_DIR  = Path(__file__).parent.parent
OUT_FILE    = CORPUS_DIR / "dataset" / "parallel_ing_rus.jsonl"
BILINGUAL   = Path(r"C:\Users\goygo\OneDrive\Desktop\bilingual")
RUS_ORIG    = CORPUS_DIR / "russian_originals"

# ---------------------------------------------------------------------------
# Text configs
# ---------------------------------------------------------------------------

BOOKS = {
    "garshin": {
        "source":    "garshin-signal-1962",
        "type":      "sentence",
        "ing_file":  BILINGUAL / "Гаршин сигнал" / "Гаршин В М Сигнал (На ингушском языке)  1962 г.txt",
        "rus_file":  RUS_ORIG / "garshin-v-m-signal-na-ingushskom-yazyke-1962-g_rus.txt",
        "ing_start": "Семен Иванов",
        "rus_start": "Семён Иванов",
    },
    "kipling": {
        "source":    "kipling-rikki-tikki-1939",
        "type":      "sentence",
        "ing_file":  BILINGUAL / "Киплинг" / "kipling_ing_ocr.txt",
        "rus_file":  BILINGUAL / "Киплинг" / "26974.pdf",   # Russian Rikki-Tikki PDF
        "ing_start": "Ер— Сигаули",
        "rus_start": "Это рассказ о великой войне",
    },
}


# ---------------------------------------------------------------------------
# Text loading and cleaning
# ---------------------------------------------------------------------------

def load_text(fpath: Path, start_marker: str, end_marker: str = None) -> str:
    if str(fpath).lower().endswith('.pdf'):
        import fitz
        doc = fitz.open(str(fpath))
        parts = []
        for i in range(len(doc)):
            t = doc[i].get_text().strip()
            if t:
                parts.append(t)
        text = '\n'.join(parts)
    else:
        with open(fpath, encoding='utf-8', errors='replace') as f:
            text = f.read()

    # Find start marker
    idx = text.find(start_marker)
    if idx >= 0:
        text = text[idx:]

    # Find end marker
    if end_marker:
        idx2 = text.find(end_marker)
        if idx2 >= 0:
            next_period = text.find('.', idx2)
            text = text[:next_period + 1] if next_period >= 0 else text[:idx2]

    return text.strip()


def clean_ing(text: str) -> str:
    """Clean Ingush OCR text: fix hyphenation, normalize spaces."""
    # Join hyphenated line breaks (word- \n continuations)
    text = re.sub(r'[-‐]\s*\n\s*', '', text)
    # Join other line breaks
    text = re.sub(r'\n', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove spurious backticks and apostrophes that appear from OCR
    text = re.sub(r"[`'](?=[а-яА-ЯёЁ])", '', text)
    return text.strip()


def clean_rus(text: str) -> str:
    """Clean Russian text."""
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation."""
    text = re.sub(r'\s+', ' ', text).strip()

    # Split at sentence boundaries: ., !, ? followed by space and uppercase/quote
    sents = re.split(
        r'(?<=[.!?»])\s+(?=[А-ЯЁ«\d"])',
        text
    )

    result = []
    for s in sents:
        s = s.strip()
        if len(s) >= 15:
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# Gale-Church alignment
# ---------------------------------------------------------------------------

def gale_church(src_sents: list[str], tgt_sents: list[str]) -> list[tuple]:
    """
    Simplified Gale-Church character-length-based alignment.
    Returns list of (src_text, tgt_text) 1:1 pairs.

    Uses DP to find optimal path through the (n+1) × (m+1) grid,
    allowing 1:1, 1:2, 2:1 alignments. Penalizes 1:0 and 0:1.
    """
    n = len(src_sents)
    m = len(tgt_sents)

    # Character lengths
    src_len = [len(s) for s in src_sents]
    tgt_len = [len(s) for s in tgt_sents]

    total_src = sum(src_len)
    total_tgt = sum(tgt_len)
    ratio = total_tgt / max(total_src, 1)

    def cost(i1, i2, j1, j2):
        """Cost of aligning src[i1:i2] ↔ tgt[j1:j2]."""
        s = sum(src_len[i1:i2])
        t = sum(tgt_len[j1:j2])
        if s == 0 and t == 0:
            return 0.0
        if s == 0 or t == 0:
            return 8.0  # high cost for skipped sentences
        expected_t = s * ratio
        z = (t - expected_t) / max(math.sqrt(s * 0.2 + 1), 1)
        return z * z + (i2 - i1 - 1) * 2.0 + (j2 - j1 - 1) * 2.0

    # DP table: dist[i][j] = min cost to align src[:i] ↔ tgt[:j]
    INF = float('inf')
    dist = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dist[0][0] = 0.0

    # Allowed moves: (di, dj) for src consumed, tgt consumed
    moves = [(1, 1), (1, 2), (2, 1), (1, 0), (0, 1)]

    for i in range(n + 1):
        for j in range(m + 1):
            if dist[i][j] == INF:
                continue
            for di, dj in moves:
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                c = cost(i, ni, j, nj) + dist[i][j]
                if c < dist[ni][nj]:
                    dist[ni][nj] = c
                    back[ni][nj] = (i, j, di, dj)

    # Trace back
    path = []
    i, j = n, m
    while i > 0 or j > 0:
        if back[i][j] is None:
            break
        pi, pj, di, dj = back[i][j]
        if di > 0 and dj > 0:  # real alignment (skip 1:0 and 0:1 in output)
            src_text = ' '.join(src_sents[pi:i]).strip()
            tgt_text = ' '.join(tgt_sents[pj:j]).strip()
            path.append((src_text, tgt_text, di, dj))
        i, j = pi, pj

    path.reverse()
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('book', choices=list(BOOKS.keys()))
    p.add_argument('--write', action='store_true')
    p.add_argument('--min-len', type=int, default=20,
                   help='Minimum character length per sentence pair side')
    return p.parse_args()


def main():
    args = parse_args()
    cfg  = BOOKS[args.book]

    print(f"Loading {args.book}...")
    ing_raw = load_text(cfg['ing_file'], cfg['ing_start'])
    rus_raw = load_text(cfg['rus_file'], cfg['rus_start'],
                        end_marker=cfg.get('rus_end'))

    ing_clean = clean_ing(ing_raw)
    rus_clean = clean_rus(rus_raw)
    print(f"  Ingush: {len(ing_clean):,} chars")
    print(f"  Russian: {len(rus_clean):,} chars")

    ing_sents = split_sentences(ing_clean)
    rus_sents = split_sentences(rus_clean)
    print(f"  Ingush sentences: {len(ing_sents)}")
    print(f"  Russian sentences: {len(rus_sents)}")

    print("Running Gale-Church alignment...")
    alignment = gale_church(ing_sents, rus_sents)

    # Filter: only 1:1 pairs that meet minimum length
    pairs = []
    skipped = 0
    for ing_text, rus_text, di, dj in alignment:
        if di == 1 and dj == 1 and len(ing_text) >= args.min_len and len(rus_text) >= args.min_len:
            pairs.append({
                "ing":    ing_text,
                "rus":    rus_text,
                "source": cfg['source'],
                "type":   cfg['type'],
            })
        else:
            skipped += 1

    print(f"\nResults:")
    print(f"  Total alignment segments: {len(alignment)}")
    print(f"  1:1 pairs accepted: {len(pairs)}")
    print(f"  Skipped (multi-sent or too short): {skipped}")

    print("\nSample pairs:")
    for p in pairs[:5]:
        print(f"  ING: {p['ing'][:80]}")
        print(f"  RUS: {p['rus'][:80]}")
        print()

    if not args.write:
        print("[dry-run] Use --write to append to dataset.")
        return

    # Remove existing pairs for this source first (replace)
    existing = []
    with open(OUT_FILE, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('source') != cfg['source']:
                existing.append(line)

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        for line in existing:
            f.write(line)
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    total = sum(1 for _ in open(OUT_FILE, encoding='utf-8'))
    print(f"\nWrote {len(pairs)} pairs → {OUT_FILE}")
    print(f"Dataset total: {total} records")


if __name__ == '__main__':
    main()
