"""
Интерактивный скрапер газеты Сердало (serdalo.ru) для параллельного корпуса.

Потоковый режим: обходит листинг страница за страницей, статьи обрабатывает
сразу — не ждёт пока соберёт все URL.

Resume: позиция в листинге (секция + страница) сохраняется в serdalo_state.json.

Usage:
  python scrape_serdalo.py [--threshold 0.35] [--limit N] [--yes] [--dry-run]
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

# Windows cp1251 → UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from sentence_transformers import SentenceTransformer

# ── Пути ──────────────────────────────────────────────────────────────────────

DATASET_PATH = Path(__file__).parent.parent / "dataset" / "parallel_ing_rus.jsonl"
STATE_PATH   = Path(__file__).parent / "serdalo_state.json"
MODEL_NAME   = "lingtrain/labse-ingush"

SERDALO_BASE = "https://serdalo.ru"
USER_AGENT   = "GhalghayTools/1.0 corpus builder"

LISTING_SECTIONS = [
    "/inh/materials",
    "/inh/news",
    "/inh/journalism",
]

SKIP_SEGMENTS = {
    "materials", "news", "journalism", "tags",
    "authors", "search", "category", "inh", "",
}


# ── HTTP ───────────────────────────────────────────────────────────────────────

def fetch(url, delay=0.7):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            content = r.read()
            enc = r.headers.get_content_charset() or "utf-8"
            return content.decode(enc, errors="replace")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  HTTP {e.code}: {url}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ERROR {url}: {e}", file=sys.stderr)
        return None
    finally:
        time.sleep(delay)


# ── Парсинг листинга ──────────────────────────────────────────────────────────

def get_page_paths(section, page):
    """Возвращает список /inh/... путей с одной страницы листинга."""
    url = SERDALO_BASE + section
    if page > 1:
        url += f"?page={page}"
    html = fetch(url, delay=0.5)
    if not html:
        return None  # 404 или ошибка — конец пагинации

    found = re.findall(
        r'href=["\'](?:https://serdalo\.ru)?(/inh/[^"\'?#]+)["\']',
        html,
    )
    paths = []
    seen_local = set()
    for path in found:
        path = path.rstrip("/")
        seg = path.split("/")[-1]
        if seg in SKIP_SEGMENTS:
            continue
        if path not in seen_local:
            seen_local.add(path)
            paths.append(path)
    return paths  # может быть пустым списком (пустая страница), но не None


# ── Парсинг статьи ─────────────────────────────────────────────────────────────

class ContentParser(HTMLParser):
    """Извлекает текст из div.cm-single-description."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_target = False
        self._depth     = 0
        self._tgt_depth = 0
        self._in_p      = False
        self._skip      = False
        self._p_buf     = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if not self._in_target and "cm-single-description" in cls:
            self._in_target = True
            self._tgt_depth = self._depth
        self._depth += 1
        if self._in_target:
            if tag == "p":
                self._in_p = True
                self._p_buf = []
            elif tag in ("script", "style", "nav", "aside", "footer"):
                self._skip = True

    def handle_endtag(self, tag):
        self._depth -= 1
        if self._in_target:
            if tag == "p" and self._in_p:
                self._in_p = False
                text = " ".join(self._p_buf).strip()
                if len(text) > 10:
                    self.paragraphs.append(text)
                self._p_buf = []
            elif tag in ("script", "style", "nav", "aside", "footer"):
                self._skip = False
        if self._in_target and self._depth <= self._tgt_depth:
            self._in_target = False

    def handle_data(self, data):
        if self._in_target and self._in_p and not self._skip:
            t = data.strip()
            if t:
                self._p_buf.append(t)


def extract_text(html):
    if not html:
        return ""
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>",  "", html, flags=re.DOTALL | re.IGNORECASE)
    p = ContentParser()
    p.feed(html)
    return "\n".join(p.paragraphs)


# ── Разбивка на предложения ────────────────────────────────────────────────────

_SENT_END = re.compile(
    r"(?<=[^А-ЯA-ZЁ\d])[.!?…]+(?=\s+[А-ЯA-ZЁ«\"\u201C\u00AB\u2039]|$)",
    re.UNICODE,
)


def split_sentences(text, min_len=20):
    text = text.replace("\xad", "")
    sentences = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        parts = _SENT_END.split(para)
        for p in parts:
            p = p.strip()
            if len(p) >= min_len:
                sentences.append(p)
    return sentences


# ── LaBSE ─────────────────────────────────────────────────────────────────────

def embed(model, sents):
    return model.encode(sents, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=False)


def dp_align(ing_emb, rus_emb, window=10):
    N, M  = len(ing_emb), len(rus_emb)
    sim   = ing_emb @ rus_emb.T
    NEG   = -1e9
    dp    = np.full((N + 1, M + 1), NEG)
    back  = np.full((N + 1, M + 1, 2), -1, dtype=int)
    dp[0][0] = 0.0
    ratio = M / max(N, 1)
    for i in range(1, N + 1):
        ej   = i * ratio
        j_lo = max(1, int(ej - window))
        j_hi = min(M, int(ej + window) + 1)
        if i == N:
            j_hi = M
        for j in range(j_lo, j_hi + 1):
            for pi, pj, pen in [
                (i - 1, j - 1, sim[i - 1][j - 1]),
                (i - 1, j,     -0.05),
                (i,     j - 1, -0.05),
            ]:
                if dp[pi][pj] > NEG:
                    s = dp[pi][pj] + pen
                    if s > dp[i][j]:
                        dp[i][j] = s
                        back[i][j] = [pi, pj]
    i, j = N, M
    if dp[N][M] == NEG:
        best_j = int(np.argmax(dp[N]))
        if dp[N][best_j] == NEG:
            return []
        i, j = N, best_j
    pairs = []
    while i > 0 or j > 0:
        pi, pj = int(back[i][j][0]), int(back[i][j][1])
        if pi < 0 or pj < 0:
            break
        if pi == i - 1 and pj == j - 1:
            pairs.append((i - 1, j - 1, float(sim[i - 1][j - 1])))
        i, j = pi, pj
    pairs.reverse()
    return pairs


# ── State ─────────────────────────────────────────────────────────────────────

def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"done": [], "total_pairs": 0}
    state.setdefault("listing", {})
    return state


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ── UI ────────────────────────────────────────────────────────────────────────

def print_pairs(kept, inh_sents, rus_sents):
    print()
    for idx, (i, j, score) in enumerate(kept, 1):
        ing = inh_sents[i]
        rus = rus_sents[j]
        ing_d = (ing[:88] + "…") if len(ing) > 88 else ing
        rus_d = (rus[:88] + "…") if len(rus) > 88 else rus
        print(f"  [{idx:2d}] score={score:.2f}")
        print(f"       ИНГ: {ing_d}")
        print(f"       РУС: {rus_d}")
    print()


def ask_user(n_pairs):
    while True:
        try:
            ans = input(
                f"  Добавить {n_pairs} пар? [Enter=да / s=пропустить / q=выход]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if ans == "":
            return True
        if ans in ("s", "с", "n"):
            return False
        if ans in ("q", "й"):
            return None
        print("  Введи Enter, s или q")


# ── Обработка одной статьи ────────────────────────────────────────────────────

def process_article(inh_path, model, args, state, done_set, existing_sources,
                    global_stats, article_counter, total_found):
    source_key = "serdalo-" + inh_path.lstrip("/").replace("/", "-")

    if inh_path in done_set or source_key in existing_sources:
        return True  # пропущено как уже обработанное

    inh_url = SERDALO_BASE + inh_path
    rus_url = SERDALO_BASE + inh_path.replace("/inh/", "/", 1)

    print(f"\n{'-'*60}", file=sys.stderr)
    print(f"[{article_counter}] {inh_path}", file=sys.stderr)

    inh_html = fetch(inh_url)
    if not inh_html:
        print("  -> нет ингушской версии", file=sys.stderr)
        global_stats["no_version"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    rus_html = fetch(rus_url)
    if not rus_html:
        print("  -> нет русской версии", file=sys.stderr)
        global_stats["no_version"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    inh_text = extract_text(inh_html)
    rus_text = extract_text(rus_html)

    if len(inh_text) < args.min_text_len or len(rus_text) < args.min_text_len:
        print(f"  -> короткий (inh:{len(inh_text)} ru:{len(rus_text)})", file=sys.stderr)
        global_stats["too_short"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    inh_sents = split_sentences(inh_text)
    rus_sents = split_sentences(rus_text)
    print(f"  Предложений: inh={len(inh_sents)}, rus={len(rus_sents)}", file=sys.stderr)

    if len(inh_sents) < 2 or len(rus_sents) < 2:
        print("  -> мало предложений, пропуск", file=sys.stderr)
        global_stats["too_short"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    inh_emb = embed(model, inh_sents)
    rus_emb = embed(model, rus_sents)
    window  = max(8, max(len(inh_sents), len(rus_sents)) // 6)
    aligned = dp_align(inh_emb, rus_emb, window=window)
    kept    = [(i, j, s) for i, j, s in aligned if s >= args.threshold]

    if not kept:
        print("  -> нет пар выше порога", file=sys.stderr)
        global_stats["no_pairs"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    global_stats["processed"] += 1

    if args.dry_run:
        print(f"  [dry-run] {len(kept)} пар")
        done_set.add(inh_path)
        state["done"].append(inh_path)
        return True

    if not args.yes:
        print_pairs(kept, inh_sents, rus_sents)
        decision = ask_user(len(kept))
    else:
        decision = True

    if decision is None:
        return False  # выход

    if not decision:
        print("  Пропущено.")
        global_stats["skipped_user"] += 1
        done_set.add(inh_path)
        state["done"].append(inh_path)
        save_state(state)
        return True

    # Записываем
    with open(DATASET_PATH, "a", encoding="utf-8") as f:
        f.write(f"### {source_key}  ({len(kept)} пар)\n")
        for i, j, score in kept:
            row = {
                "ing":    inh_sents[i],
                "rus":    rus_sents[j],
                "source": source_key,
                "type":   "sentence",
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    global_stats["added"]       += 1
    global_stats["total_pairs"] += len(kept)
    state["total_pairs"]         = state.get("total_pairs", 0) + len(kept)
    done_set.add(inh_path)
    state["done"].append(inh_path)
    save_state(state)

    print(f"  + {len(kept)} пар  (сессия: {global_stats['total_pairs']})", file=sys.stderr)
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold",    type=float, default=0.35)
    parser.add_argument("--limit",        type=int,   default=0,
                        help="Обработать не более N статей")
    parser.add_argument("--min-text-len", type=int,   default=100)
    parser.add_argument("--yes",          action="store_true",
                        help="Авто-принимать все статьи")
    parser.add_argument("--dry-run",      action="store_true")
    args = parser.parse_args()

    # Существующие source-ключи
    existing_sources = set()
    if DATASET_PATH.exists():
        with open(DATASET_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        existing_sources.add(json.loads(line).get("source", ""))
                    except Exception:
                        pass

    state    = load_state()
    done_set = set(state["done"])

    print(f"Уже обработано статей: {len(done_set)}", file=sys.stderr)
    print(f"Загрузка модели {MODEL_NAME}...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    stats = {
        "processed": 0, "added": 0, "skipped_user": 0,
        "no_version": 0, "too_short": 0, "no_pairs": 0, "total_pairs": 0,
    }

    article_counter = 0
    total_found     = 0
    stop            = False

    for section in LISTING_SECTIONS:
        if stop:
            break

        start_page = state["listing"].get(section, 1)
        page       = start_page
        empty_streak = 0

        print(f"\nСекция: {section}  (с страницы {page})", file=sys.stderr)

        while not stop:
            paths = get_page_paths(section, page)

            if paths is None:
                # 404 — конец пагинации
                print(f"  {section} закончился на стр.{page}", file=sys.stderr)
                state["listing"][section] = page
                save_state(state)
                break

            # Фильтруем уже обработанные
            new_paths = [p for p in paths if p not in done_set]

            if not new_paths:
                empty_streak += 1
                if empty_streak >= 3:
                    print(f"  {section}: 3 пустые страницы подряд, стоп", file=sys.stderr)
                    state["listing"][section] = page
                    save_state(state)
                    break
            else:
                empty_streak = 0
                total_found += len(new_paths)
                print(f"  {section} стр.{page}: {len(new_paths)} новых статей", file=sys.stderr)

                for inh_path in new_paths:
                    article_counter += 1
                    ok = process_article(
                        inh_path, model, args, state, done_set,
                        existing_sources, stats, article_counter, total_found,
                    )
                    if not ok:
                        stop = True
                        break
                    if args.limit and stats["processed"] >= args.limit:
                        stop = True
                        break

            # Сохраняем позицию листинга
            state["listing"][section] = page
            save_state(state)
            page += 1

    # Итог
    print(f"\n{'='*60}")
    print(f"Обработано статей:   {stats['processed']}")
    print(f"Добавлено статей:    {stats['added']}")
    print(f"Пропущено (user):    {stats['skipped_user']}")
    print(f"Нет пар:             {stats['no_pairs']}")
    print(f"Нет версии/коротко:  {stats['no_version'] + stats['too_short']}")
    print(f"Новых пар итого:     {stats['total_pairs']}")

    if DATASET_PATH.exists():
        total = sum(
            1 for line in open(DATASET_PATH, encoding="utf-8")
            if line.strip() and not line.startswith("#")
        )
        print(f"Датасет всего:       {total:,} пар")


if __name__ == "__main__":
    main()
