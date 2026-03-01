"""
LaBSE-Ingush sentence aligner for bilingual Ingush/Russian texts.

Pipeline:
  1. OCR Ingush PDF (Tesseract/rus) → raw text
  2. Split both sides into sentences
  3. Embed with lingtrain/labse-ingush
  4. DP monotone alignment (cosine similarity)
  5. Filter low-confidence pairs
  6. Append to parallel_ing_rus.jsonl

Usage:
  python align_labse.py --ing PDF --rus TXT --source SLUG [--type sentence] [--threshold 0.3]
  python align_labse.py --ing PDF --rus TXT --source SLUG --ocr-only   # just dump OCR
  python align_labse.py --ing TXT --rus TXT --source SLUG              # skip OCR
"""

import argparse
import json
import re
import subprocess
import tempfile
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from sentence_transformers import SentenceTransformer

# ─── Paths ────────────────────────────────────────────────────────────────────

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MODEL_NAME = "lingtrain/labse-ingush"

# ─── OCR ──────────────────────────────────────────────────────────────────────

def ocr_pdf(pdf_path: str, lang: str = "rus", dpi: int = 300) -> str:
    """Extract text from scanned PDF via Tesseract (page by page)."""
    doc = fitz.open(pdf_path)
    all_text = []
    print(f"OCR: {len(doc)} pages, lang={lang}", file=sys.stderr)
    for i, page in enumerate(doc):
        # Render page to image
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_path = f.name
        pix.save(img_path)
        # Run tesseract
        out_base = img_path.replace(".png", "_ocr")
        subprocess.run(
            [TESSERACT_CMD, img_path, out_base, "-l", lang, "--psm", "6"],
            capture_output=True, check=True
        )
        txt_path = out_base + ".txt"
        with open(txt_path, encoding="utf-8") as f:
            text = f.read()
        all_text.append(text)
        os.unlink(img_path)
        os.unlink(txt_path)
        if (i + 1) % 5 == 0:
            print(f"  page {i+1}/{len(doc)}", file=sys.stderr)
    return "\n".join(all_text)


# ─── Sentence splitting ────────────────────────────────────────────────────────

# Split on .!?… followed by space+capital or end-of-string
# Simple heuristic: avoids splitting on single-letter initials (А. Б.)
_SENT_END = re.compile(
    r'(?<=[^А-ЯA-Z\d])'        # not after single capital/digit (initials, abbrevs)
    r'[.!?…]+'                  # sentence-ending punctuation
    r'(?=\s+[А-ЯA-ZЁ«"\u201C]|$)',  # followed by capital or quote
    re.UNICODE
)


def normalize_ingush(text: str) -> str:
    """
    Normalize OCR variants of Ingush palochka (Ӏ = U+04C0).
    Different scans encode it as: 1, [, ], !, |, I (Latin capital I)
    We keep the pattern as-is (don't replace) since LaBSE handles variation,
    but we do remove obviously wrong chars that fragment words.
    """
    # Soft hyphen removal (OCR line-break artifacts)
    text = text.replace('\xad', '')
    # Collapse hyphen+newline (line-break hyphenation in old books)
    text = re.sub(r'-\n', '', text)
    return text


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, clean up OCR artifacts."""
    # Normalize whitespace / soft hyphens / form feeds
    text = normalize_ingush(text)
    text = text.replace('\f', '\n').replace('\r\n', '\n')
    # Remove page headers/footers heuristic: short isolated lines (<4 words, all caps or digits)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        words = line.split()
        if not words:
            continue
        # Skip very short lines that look like page numbers or headers
        if len(words) <= 2 and (line.isdigit() or line.isupper()):
            continue
        cleaned.append(line)
    text = ' '.join(cleaned)

    # Split on sentence boundaries
    parts = _SENT_END.split(text)
    # Re-attach the punctuation (split consumed it)
    sentences = []
    for part in parts:
        part = part.strip()
        if len(part) > 10:
            sentences.append(part)
    return sentences


# ─── Embedding ────────────────────────────────────────────────────────────────

def load_model():
    print(f"Loading {MODEL_NAME}...", file=sys.stderr)
    return SentenceTransformer(MODEL_NAME)


def embed(model, sentences: list[str], batch_size: int = 64) -> np.ndarray:
    return model.encode(sentences, batch_size=batch_size, normalize_embeddings=True,
                        show_progress_bar=True)


# ─── Monotone alignment ───────────────────────────────────────────────────────

def dp_align(ing_emb: np.ndarray, rus_emb: np.ndarray,
             window: int = 8) -> list[tuple[int, int, float]]:
    """
    Monotone 1-1 alignment via DP with ratio-aware band constraint.
    The window is applied around the expected diagonal (i * M/N).
    Returns list of (i, j, score) for matched pairs.
    """
    N, M = len(ing_emb), len(rus_emb)
    sim = ing_emb @ rus_emb.T  # N x M, already normalized

    NEG_INF = -1e9
    dp = np.full((N + 1, M + 1), NEG_INF)
    dp[0][0] = 0.0
    back = np.full((N + 1, M + 1, 2), -1, dtype=int)

    ratio = M / max(N, 1)  # expected rus index per ing index

    for i in range(1, N + 1):
        # Band centered on expected diagonal position
        expected_j = i * ratio
        j_lo = max(1, int(expected_j - window) )
        j_hi = min(M, int(expected_j + window) + 1)
        # Always allow reaching the start/end
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            # Match ing[i-1] with rus[j-1]
            if dp[i-1][j-1] > NEG_INF:
                score = dp[i-1][j-1] + sim[i-1][j-1]
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i-1, j-1]
            # Skip ing[i-1] (no match for this ing sentence)
            if dp[i-1][j] > NEG_INF:
                score = dp[i-1][j] - 0.05
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i-1, j]
            # Skip rus[j-1]
            if dp[i][j-1] > NEG_INF:
                score = dp[i][j-1] - 0.05
                if score > dp[i][j]:
                    dp[i][j] = score
                    back[i][j] = [i, j-1]

    # Traceback from (N, M)
    if dp[N][M] == NEG_INF:
        # Fallback: find best reachable end point
        best_j = int(np.argmax(dp[N]))
        if dp[N][best_j] == NEG_INF:
            return []
        i, j = N, best_j
    else:
        i, j = N, M

    pairs = []
    while i > 0 or j > 0:
        pi, pj = int(back[i][j][0]), int(back[i][j][1])
        if pi < 0 or pj < 0:
            break
        if pi == i - 1 and pj == j - 1:
            pairs.append((i - 1, j - 1, float(sim[i-1][j-1])))
        i, j = pi, pj

    pairs.reverse()
    return pairs


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ing", required=True, help="Ingush PDF or TXT")
    parser.add_argument("--rus", required=True, help="Russian TXT")
    parser.add_argument("--source", required=True, help="Source slug for dataset")
    parser.add_argument("--type", default="sentence", help="Pair type (sentence/play/etc)")
    parser.add_argument("--threshold", type=float, default=0.35,
                        help="Min cosine similarity to keep pair")
    parser.add_argument("--window", type=int, default=12,
                        help="DP band window (larger = slower but more flexible)")
    parser.add_argument("--ocr-only", action="store_true",
                        help="Just dump OCR text and exit")
    parser.add_argument("--ocr-lang", default="rus",
                        help="Tesseract language for OCR (default: rus)")
    parser.add_argument("--ing-skip-pages", default="",
                        help="Comma-separated page ranges to skip (0-indexed), e.g. '0,1,172'")
    parser.add_argument("--rus-skip-lines", default="",
                        help="Regex pattern to strip from Russian text (e.g. chapter headers)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print pairs but don't write to dataset")
    args = parser.parse_args()

    # ── Load Ingush text
    if args.ing.endswith(".pdf"):
        print("Running OCR on Ingush PDF...", file=sys.stderr)
        skip_pages = set()
        if args.ing_skip_pages:
            for part in args.ing_skip_pages.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    skip_pages.update(range(int(a), int(b)+1))
                else:
                    skip_pages.add(int(part))
        doc = fitz.open(args.ing)
        all_text = []
        print(f"OCR: {len(doc)} pages", file=sys.stderr)
        for i, page in enumerate(doc):
            if i in skip_pages:
                continue
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img_path = f.name
            pix.save(img_path)
            out_base = img_path.replace(".png", "_ocr")
            subprocess.run(
                [TESSERACT_CMD, img_path, out_base, "-l", args.ocr_lang, "--psm", "6"],
                capture_output=True, check=True
            )
            txt_path = out_base + ".txt"
            with open(txt_path, encoding="utf-8") as f:
                text = f.read()
            all_text.append(text)
            os.unlink(img_path)
            os.unlink(txt_path)
            if (i + 1) % 5 == 0:
                print(f"  page {i+1}/{len(doc)}", file=sys.stderr)
        ing_raw = "\n".join(all_text)
    else:
        with open(args.ing, encoding="utf-8") as f:
            ing_raw = f.read()

    if args.ocr_only:
        print(ing_raw)
        return

    # ── Load Russian text
    with open(args.rus, encoding="utf-8") as f:
        rus_raw = f.read()

    # ── Split into sentences
    ing_sents = split_sentences(ing_raw)
    rus_sents = split_sentences(rus_raw)
    print(f"Ingush sentences: {len(ing_sents)}", file=sys.stderr)
    print(f"Russian sentences: {len(rus_sents)}", file=sys.stderr)

    if len(ing_sents) == 0 or len(rus_sents) == 0:
        print("ERROR: empty sentence list — check OCR or input files", file=sys.stderr)
        sys.exit(1)

    # ── Embed
    model = load_model()
    print("Embedding Ingush...", file=sys.stderr)
    ing_emb = embed(model, ing_sents)
    print("Embedding Russian...", file=sys.stderr)
    rus_emb = embed(model, rus_sents)

    # ── Align
    print("Running DP alignment...", file=sys.stderr)
    pairs = dp_align(ing_emb, rus_emb, window=args.window)

    # ── Filter and report
    kept = [(i, j, s) for i, j, s in pairs if s >= args.threshold]
    skipped = len(pairs) - len(kept)
    print(f"Aligned: {len(pairs)} pairs, kept {len(kept)} (threshold={args.threshold}), "
          f"skipped {skipped} low-confidence", file=sys.stderr)

    # ── Preview
    print("\n--- Sample pairs ---", file=sys.stderr)
    for i, j, score in kept[:10]:
        print(f"[{score:.3f}] ING: {ing_sents[i][:80]}", file=sys.stderr)
        print(f"        RUS: {rus_sents[j][:80]}", file=sys.stderr)
        print(file=sys.stderr)

    if args.dry_run:
        print("Dry run — not writing to dataset.", file=sys.stderr)
        return

    # ── Append to dataset
    existing_sources = set()
    if DATASET_PATH.exists():
        with open(DATASET_PATH, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                existing_sources.add(row.get("source"))
    if args.source in existing_sources:
        print(f"WARNING: source '{args.source}' already in dataset. "
              f"Use --dry-run to preview without writing.", file=sys.stderr)
        ans = input("Overwrite? (y/N): ")
        if ans.lower() != "y":
            sys.exit(0)

    new_pairs = []
    for i, j, score in kept:
        new_pairs.append({
            "ing": ing_sents[i],
            "rus": rus_sents[j],
            "source": args.source,
            "type": args.type,
        })

    with open(DATASET_PATH, "a", encoding="utf-8") as f:
        for row in new_pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(new_pairs)} pairs to {DATASET_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
