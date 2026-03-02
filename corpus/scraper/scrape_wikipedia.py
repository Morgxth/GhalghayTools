"""
Scraper для ингушской Википедии.

Для каждой статьи:
  1. Находит русский эквивалент через langlinks API
  2. Скачивает plain text обеих статей
  3. Выравнивает предложения через LaBSE
  4. Добавляет в параллельный корпус

Поддерживает resume: сохраняет прогресс в wiki_state.json,
можно прервать и продолжить.

Usage:
  python scrape_wikipedia.py [--dry-run] [--threshold 0.35] [--limit N]
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATASET_PATH  = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
STATE_PATH    = Path(__file__).parent / "wiki_state.json"
MODEL_NAME    = "lingtrain/labse-ingush"
SOURCE_PREFIX = "wiki-inh"

INH_API = "https://inh.wikipedia.org/w/api.php"
RU_API  = "https://ru.wikipedia.org/w/api.php"

# Разделы, которые не несут смысловой нагрузки
SKIP_SECTIONS = {
    "см. также", "примечания", "ссылки", "литература",
    "источники", "галерея", "references", "notes", "see also",
    "external links", "bibliography", "хьажа а", "хьажа",
}


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def api_get(endpoint, params, delay=0.3):
    params["format"] = "json"
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "GhalghayTools/1.0 corpus builder"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    time.sleep(delay)
    return data


# ─── Wikipedia API ────────────────────────────────────────────────────────────

def get_all_article_titles():
    """Получить все статьи ингушской Вики (namespace=0)."""
    titles = []
    apcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": "0",
            "aplimit": "500",
            "apfilterredir": "nonredirects",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        data = api_get(INH_API, params)
        pages = data["query"]["allpages"]
        titles.extend(p["title"] for p in pages)
        print(f"  Получено: {len(titles)} статей...", file=sys.stderr, end="\r")

        cont = data.get("continue", {})
        apcontinue = cont.get("apcontinue")
        if not apcontinue:
            break

    print(f"\n  Всего статей: {len(titles)}", file=sys.stderr)
    return titles


def get_article_with_ru_link(inh_title):
    """
    Возвращает (inh_text, ru_title) или (None, None) если нет русского аналога.
    Один запрос: langlinks + extracts вместе.
    """
    params = {
        "action": "query",
        "titles": inh_title,
        "prop": "langlinks|extracts",
        "lllang": "ru",
        "explaintext": "true",
        "exsectionformat": "plain",
        "exlimit": "1",
    }
    try:
        data = api_get(INH_API, params)
    except Exception as e:
        print(f"  ERROR inh [{inh_title}]: {e}", file=sys.stderr)
        return None, None

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))

    inh_text = page.get("extract", "").strip()
    langlinks = page.get("langlinks", [])
    ru_title = next((l["*"] for l in langlinks if l["lang"] == "ru"), None)

    return inh_text, ru_title


def get_ru_text(ru_title):
    """Получить plain text русской статьи."""
    params = {
        "action": "query",
        "titles": ru_title,
        "prop": "extracts",
        "explaintext": "true",
        "exsectionformat": "plain",
        "exlimit": "1",
    }
    try:
        data = api_get(RU_API, params)
    except Exception as e:
        print(f"  ERROR ru [{ru_title}]: {e}", file=sys.stderr)
        return None

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    return page.get("extract", "").strip()


# ─── Очистка текста ───────────────────────────────────────────────────────────

def clean_wiki_text(text):
    """Убрать специфику вики-экстрактов."""
    # Удалить строки типа "== Раздел ==" (заголовки секций)
    lines = []
    skip_next = False
    for line in text.split("\n"):
        stripped = line.strip()
        # Пропустить пустые заголовки секций и нежелательные разделы
        if re.match(r"^=+\s*.+\s*=+$", stripped):
            section_name = re.sub(r"=+", "", stripped).strip().lower()
            skip_next = section_name in SKIP_SECTIONS
            continue
        if skip_next and stripped == "":
            continue
        if skip_next and stripped:
            # Проверяем, не начался ли новый раздел
            if not re.match(r"^=+", stripped):
                skip_next = False
                lines.append(stripped)
            continue
        if stripped:
            lines.append(stripped)

    text = " ".join(lines)
    # Убрать множественные пробелы
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


# ─── Sentence splitting ────────────────────────────────────────────────────────

_SENT_END = re.compile(
    r"(?<=[^А-ЯA-Z\d])[.!?…]+(?=\s+[А-ЯA-ZЁ«\"\u201C]|$)",
    re.UNICODE,
)


def split_sentences(text, min_len=15):
    text = text.replace("\xad", "")
    text = re.sub(r"-\n", "", text)
    # Разбиваем по параграфам сначала
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    sentences = []
    for para in paragraphs:
        parts = _SENT_END.split(para)
        for p in parts:
            p = p.strip()
            if len(p) >= min_len:
                sentences.append(p)
    return sentences


# ─── LaBSE alignment ──────────────────────────────────────────────────────────

def embed(model, sentences):
    return model.encode(sentences, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=False)


def dp_align(ing_emb, rus_emb, window=10):
    N, M = len(ing_emb), len(rus_emb)
    sim = ing_emb @ rus_emb.T
    NEG_INF = -1e9
    dp   = np.full((N + 1, M + 1), NEG_INF)
    back = np.full((N + 1, M + 1, 2), -1, dtype=int)
    dp[0][0] = 0.0
    ratio = M / max(N, 1)
    for i in range(1, N + 1):
        expected_j = i * ratio
        j_lo = max(1, int(expected_j - window))
        j_hi = min(M, int(expected_j + window) + 1)
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            for pi, pj, pen in [(i-1, j-1, sim[i-1][j-1]),
                                 (i-1, j,   -0.05),
                                 (i,   j-1, -0.05)]:
                if dp[pi][pj] > NEG_INF:
                    s = dp[pi][pj] + pen
                    if s > dp[i][j]:
                        dp[i][j] = s
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
            pairs.append((i-1, j-1, float(sim[i-1][j-1])))
        i, j = pi, pj
    pairs.reverse()
    return pairs


def get_source_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^\w]+", "-", slug, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    # Транслит базовый (кириллица → латиница для slug) — просто обрезаем
    slug = re.sub(r"[^a-z0-9-]", "", slug).strip("-")
    if not slug:
        slug = urllib.parse.quote(title.lower(), safe="")[:40]
    return f"{SOURCE_PREFIX}-{slug}"


# ─── Прогресс / resume ────────────────────────────────────────────────────────

def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold",    type=float, default=0.35,
                        help="Min LaBSE cosine similarity")
    parser.add_argument("--limit",        type=int,   default=0,
                        help="Process at most N articles (0 = all)")
    parser.add_argument("--min-text-len", type=int,   default=200,
                        help="Min chars in article text")
    parser.add_argument("--dry-run",      action="store_true")
    args = parser.parse_args()

    # Загружаем existing sources
    existing_sources = set()
    if DATASET_PATH.exists():
        with open(DATASET_PATH, encoding="utf-8") as f:
            for line in f:
                existing_sources.add(json.loads(line).get("source", ""))

    state = load_state()
    done_titles = set(state["done"])

    print("Получение списка статей...", file=sys.stderr)
    all_titles = get_all_article_titles()

    if args.limit:
        all_titles = all_titles[:args.limit]

    print(f"Загрузка модели {MODEL_NAME}...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    stats = {
        "processed": 0, "skipped_done": 0, "no_ru_link": 0,
        "too_short": 0, "ratio_skip": 0, "total_pairs": 0,
    }
    all_new_pairs = []

    for idx, title in enumerate(all_titles):
        slug = get_source_slug(title)

        if title in done_titles or slug in existing_sources:
            stats["skipped_done"] += 1
            continue

        print(f"\n[{idx+1}/{len(all_titles)}] {title}", file=sys.stderr)

        # Получить ингушский текст + ссылку на русский
        inh_text, ru_title = get_article_with_ru_link(title)

        if not ru_title:
            print(f"  -> нет русского аналога", file=sys.stderr)
            stats["no_ru_link"] += 1
            done_titles.add(title)
            state["done"].append(title)
            if idx % 20 == 0:
                save_state(state)
            continue

        if not inh_text or len(inh_text) < args.min_text_len:
            print(f"  -> ингушский текст слишком короткий ({len(inh_text or '')} chars)", file=sys.stderr)
            stats["too_short"] += 1
            done_titles.add(title)
            state["done"].append(title)
            continue

        # Получить русский текст
        ru_text = get_ru_text(ru_title)
        if not ru_text or len(ru_text) < args.min_text_len:
            print(f"  -> русский текст слишком короткий", file=sys.stderr)
            stats["too_short"] += 1
            done_titles.add(title)
            state["done"].append(title)
            continue

        # Очистить тексты
        inh_clean = clean_wiki_text(inh_text)
        ru_clean  = clean_wiki_text(ru_text)

        # Проверить соотношение длин (если >5:1, выравнивание бессмысленно)
        ratio = max(len(inh_clean), len(ru_clean)) / max(min(len(inh_clean), len(ru_clean)), 1)
        if ratio > 5.0:
            print(f"  -> большое расхождение в длинах (ratio {ratio:.1f}:1), пропуск", file=sys.stderr)
            stats["ratio_skip"] += 1
            done_titles.add(title)
            state["done"].append(title)
            continue

        # Разбить на предложения
        inh_sents = split_sentences(inh_clean)
        ru_sents  = split_sentences(ru_clean)

        if len(inh_sents) < 2 or len(ru_sents) < 2:
            print(f"  -> мало предложений (inh:{len(inh_sents)} ru:{len(ru_sents)})", file=sys.stderr)
            stats["too_short"] += 1
            done_titles.add(title)
            state["done"].append(title)
            continue

        # LaBSE выравнивание
        inh_emb = embed(model, inh_sents)
        ru_emb  = embed(model, ru_sents)
        window  = max(8, max(len(inh_sents), len(ru_sents)) // 6)
        aligned = dp_align(inh_emb, ru_emb, window=window)
        kept    = [(i, j, s) for i, j, s in aligned if s >= args.threshold]

        print(f"  {ru_title[:50]}", file=sys.stderr)
        print(f"  inh:{len(inh_sents)} sents / ru:{len(ru_sents)} sents -> {len(kept)} pairs kept", file=sys.stderr)

        new_pairs = []
        for i, j, score in kept:
            new_pairs.append({
                "ing": inh_sents[i],
                "rus": ru_sents[j],
                "source": slug,
                "type": "sentence",
            })

        all_new_pairs.extend(new_pairs)
        stats["total_pairs"] += len(new_pairs)
        stats["processed"] += 1

        done_titles.add(title)
        state["done"].append(title)
        if idx % 10 == 0:
            save_state(state)

    # Итог
    print(f"\n=== Итог ===", file=sys.stderr)
    print(f"Обработано:          {stats['processed']}", file=sys.stderr)
    print(f"Пропущено (готово):  {stats['skipped_done']}", file=sys.stderr)
    print(f"Нет рус. аналога:    {stats['no_ru_link']}", file=sys.stderr)
    print(f"Слишком короткие:    {stats['too_short']}", file=sys.stderr)
    print(f"Расхождение длин:    {stats['ratio_skip']}", file=sys.stderr)
    print(f"Новых пар:           {stats['total_pairs']}", file=sys.stderr)

    if args.dry_run or not all_new_pairs:
        print("Dry run или нет данных — корпус не изменён.", file=sys.stderr)
        save_state(state)
        return

    with open(DATASET_PATH, "a", encoding="utf-8") as f:
        for row in all_new_pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    save_state(state)
    total = sum(1 for _ in open(DATASET_PATH, encoding="utf-8"))
    print(f"Датасет: {total:,} пар всего", file=sys.stderr)


if __name__ == "__main__":
    main()
