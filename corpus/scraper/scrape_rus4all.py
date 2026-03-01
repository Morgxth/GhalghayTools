"""
Scraper + LaBSE aligner for rus4all.ru/inh/

Собирает все произведения с ингушским оригиналом и русским переводом.
Проза: LaBSE sentence alignment.
Поэзия/короткое: сохраняем как одну пару целиком.

Usage:
  python scrape_rus4all.py [--dry-run] [--threshold 0.3]
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
MODEL_NAME = "lingtrain/labse-ingush"
BASE_URL = "https://rus4all.ru"
SOURCE_PREFIX = "rus4all"

# ─── HTTP ─────────────────────────────────────────────────────────────────────

def fetch(url, delay=0.5):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
    time.sleep(delay)
    return html


# ─── HTML parsing ─────────────────────────────────────────────────────────────

def strip_html(s):
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&mdash;", "—", s)
    s = re.sub(r"&ndash;", "–", s)
    s = re.sub(r"&laquo;", "«", s)
    s = re.sub(r"&raquo;", "»", s)
    s = re.sub(r"&hellip;", "…", s)
    s = re.sub(r"&[a-zA-Z]+;", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def extract_tab(html, tab_id):
    """Extract text content of a tab div."""
    idx = html.find(f'id="{tab_id}"')
    if idx == -1:
        return None
    # Grab content until next top-level div or end
    chunk = html[idx:idx + 30000]
    # Remove the opening tag
    tag_end = chunk.find(">")
    if tag_end == -1:
        return None
    chunk = chunk[tag_end + 1:]
    # Strip HTML and return
    return strip_html(chunk)


def get_work_meta(html, path):
    """Extract title, author, genre from page."""
    title_m = re.search(r"<title>([^<]+)</title>", html)
    full_title = title_m.group(1).split("|")[0].strip() if title_m else path
    # Genre is in the title: "Весна (Поэзия)" or "Ад (Проза)"
    genre = "prose"
    if re.search(r"\(Поэзи", full_title, re.IGNORECASE):
        genre = "poem"
    return full_title, genre


def get_source_slug(path):
    """Convert URL path to source slug."""
    # /inh/20190528/10932/Ad.html -> rus4all-ad
    slug = path.rstrip("/").split("/")[-1].replace(".html", "").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return f"{SOURCE_PREFIX}-{slug}"


# ─── Crawl all work URLs ───────────────────────────────────────────────────────

def crawl_links():
    all_links = []
    for page in range(1, 20):
        html = fetch(f"{BASE_URL}/inh/?list_sid=inh&page={page}", delay=0.3)
        links = re.findall(r'href="(/inh/\d{8}/\d+/[^"]+\.html)"', html)
        new = [l for l in links if l not in all_links]
        if not new:
            break
        all_links.extend(new)
        print(f"  Page {page}: +{len(new)} (total {len(all_links)})", file=sys.stderr)
        if f"page={page + 1}" not in html:
            break
    return all_links


# ─── Sentence splitting ────────────────────────────────────────────────────────

_SENT_END = re.compile(
    r"(?<=[^А-ЯA-Z\d])[.!?…]+(?=\s+[А-ЯA-ZЁ«\"\u201C]|$)",
    re.UNICODE,
)


def split_sentences(text):
    text = text.replace("\xad", "")
    text = re.sub(r"-\n", "", text)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        words = line.split()
        if not words:
            continue
        if len(words) <= 2 and (line.isdigit() or line.isupper()):
            continue
        cleaned.append(line)
    text = " ".join(cleaned)
    parts = _SENT_END.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 10]


# ─── Embedding + DP alignment ─────────────────────────────────────────────────

def embed(model, sentences):
    return model.encode(sentences, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=False)


def dp_align(ing_emb, rus_emb, window=8):
    N, M = len(ing_emb), len(rus_emb)
    sim = ing_emb @ rus_emb.T
    NEG_INF = -1e9
    dp = np.full((N + 1, M + 1), NEG_INF)
    dp[0][0] = 0.0
    back = np.full((N + 1, M + 1, 2), -1, dtype=int)
    ratio = M / max(N, 1)
    for i in range(1, N + 1):
        expected_j = i * ratio
        j_lo = max(1, int(expected_j - window))
        j_hi = min(M, int(expected_j + window) + 1)
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            for pi, pj, penalty in [(i - 1, j - 1, sim[i-1][j-1]),
                                     (i - 1, j, -0.05),
                                     (i, j - 1, -0.05)]:
                if dp[pi][pj] > NEG_INF:
                    score = dp[pi][pj] + penalty
                    if score > dp[i][j]:
                        dp[i][j] = score
                        back[i][j] = [pi, pj]
    i, j = N, M
    if dp[N][M] == NEG_INF:
        best_j = int(np.argmax(dp[N]))
        if dp[N][best_j] == NEG_INF:
            return []
        i, j = N, best_j
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
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Check existing sources
    existing_sources = set()
    if DATASET_PATH.exists():
        with open(DATASET_PATH, encoding="utf-8") as f:
            for line in f:
                existing_sources.add(json.loads(line).get("source"))

    print("Crawling work list...", file=sys.stderr)
    links = crawl_links()
    print(f"Found {len(links)} works", file=sys.stderr)

    print(f"Loading {MODEL_NAME}...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    all_new_pairs = []
    stats = {"works_processed": 0, "works_skipped": 0,
             "works_no_translation": 0, "total_pairs": 0}

    for path in links:
        slug = get_source_slug(path)
        if slug in existing_sources:
            print(f"  SKIP (already in dataset): {slug}", file=sys.stderr)
            stats["works_skipped"] += 1
            continue

        url = BASE_URL + path
        try:
            html = fetch(url, delay=0.4)
        except Exception as e:
            print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
            continue

        ing_text = extract_tab(html, "tab-source")
        rus_text = extract_tab(html, "tab-literary")

        if not ing_text or not rus_text or len(rus_text.strip()) < 50:
            stats["works_no_translation"] += 1
            continue

        title, genre = get_work_meta(html, path)
        stats["works_processed"] += 1

        print(f"  [{genre}] {title[:50]}", file=sys.stderr)

        new_pairs = []

        if genre == "poem" or len(split_sentences(ing_text)) < 4:
            # Short/poetry: save as single pair
            ing_clean = ing_text.strip()
            rus_clean = rus_text.strip()
            if len(ing_clean) > 20 and len(rus_clean) > 20:
                new_pairs.append({
                    "ing": ing_clean,
                    "rus": rus_clean,
                    "source": slug,
                    "type": genre,
                })
        else:
            # Prose: sentence-level alignment
            ing_sents = split_sentences(ing_text)
            rus_sents = split_sentences(rus_text)

            if len(ing_sents) < 2 or len(rus_sents) < 2:
                new_pairs.append({
                    "ing": ing_text.strip(),
                    "rus": rus_text.strip(),
                    "source": slug,
                    "type": "prose",
                })
            else:
                ing_emb = embed(model, ing_sents)
                rus_emb = embed(model, rus_sents)
                aligned = dp_align(ing_emb, rus_emb,
                                   window=max(6, len(ing_sents) // 5))
                kept = [(i, j, s) for i, j, s in aligned if s >= args.threshold]
                print(f"    {len(ing_sents)} ing / {len(rus_sents)} rus sents → "
                      f"{len(kept)} pairs kept", file=sys.stderr)
                for i, j, score in kept:
                    new_pairs.append({
                        "ing": ing_sents[i],
                        "rus": rus_sents[j],
                        "source": slug,
                        "type": "sentence",
                    })

        all_new_pairs.extend(new_pairs)
        stats["total_pairs"] += len(new_pairs)

    print(f"\n=== Итог ===", file=sys.stderr)
    print(f"Обработано: {stats['works_processed']}", file=sys.stderr)
    print(f"Пропущено (уже есть): {stats['works_skipped']}", file=sys.stderr)
    print(f"Без перевода: {stats['works_no_translation']}", file=sys.stderr)
    print(f"Новых пар: {stats['total_pairs']}", file=sys.stderr)

    if args.dry_run:
        print("Dry run — датасет не изменён.", file=sys.stderr)
        return

    with open(DATASET_PATH, "a", encoding="utf-8") as f:
        for row in all_new_pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    total = sum(1 for _ in open(DATASET_PATH, encoding="utf-8"))
    print(f"Датасет: {total:,} пар всего", file=sys.stderr)


if __name__ == "__main__":
    main()
