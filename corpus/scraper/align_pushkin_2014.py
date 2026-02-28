"""
align_pushkin_2014.py — Extract parallel pairs from
"Пушкин на ингушском языке (Пушкин гIалгIай меттала) (2014).pdf"

Extracts 22 poem pairs (Ingush translation + Russian original) and appends
them to corpus/dataset/parallel_ing_rus.jsonl.

Run:
    python align_pushkin_2014.py            # dry-run
    python align_pushkin_2014.py --write    # append to dataset
"""

import re, sys, json, urllib.request, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CORPUS_DIR = Path(__file__).parent.parent
PDF_2014   = Path(r"C:\Users\goygo\OneDrive\Desktop\bilingual\Пушкин\Пушкин на ингушском языке (Пушкин гIалгIай меттала) (2014).pdf")
OUT_FILE   = CORPUS_DIR / "dataset" / "parallel_ing_rus.jsonl"
SOURCE     = "pushkin-2014"

UA = "GhalghayTools/1.0 (ingush-corpus; educational)"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url, enc='utf-8'):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode(enc, errors='replace')

def clean_libru(text):
    if not text: return ''
    if re.search(r'<html', text, re.I):
        pre = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.I)
        if pre: text = pre.group(1)
        else:   text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def fetch_wiki_poem(url):
    html = fetch(url)
    m = re.search(r'class="poem"[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1)).replace('&nbsp;', ' ').replace('&#160;', ' ')
        t = re.sub(r'\s+\n', '\n', t)
        t = re.sub(r'\n{3,}', '\n\n', t)
        return t.strip()
    return None

def between(text, t1, t2):
    m1 = re.search(r'\n\s*' + re.escape(t1) + r'\s*\n', text)
    if not m1: return None
    start = m1.end()
    m2 = re.search(r'\n\s*' + re.escape(t2) + r'\s*\n', text[start:])
    end = start + m2.start() if m2 else len(text)
    return text[start:end].strip()

def after_line(text, line, maxlen=2000):
    m = re.search(re.escape(line), text)
    if not m: return None
    start = m.start()
    while start > 0 and text[start-1] != '\n':
        start -= 1
    return text[start:start+maxlen].strip()


# ---------------------------------------------------------------------------
# Russian originals
# ---------------------------------------------------------------------------

def collect_russian(p2, p3):
    rus = {}
    # Short lyrics from p2
    rus['kavkaz']        = between(p2, 'КАВКАЗ', 'ОБВАЛ')
    rus['arion']         = between(p2, 'АРИОН', 'АНГЕЛ')
    rus['zimny_vecher']  = between(p2, 'ЗИМНИЙ ВЕЧЕР', 'С ПОРТУГАЛЬСКОГО')
    rus['zimnya_doroga'] = between(p2, 'ЗИМНЯЯ ДОРОГА', 'МОРДВИНОВУ')
    rus['zoloto_bulat']  = between(p2, 'ЗОЛОТО И БУЛАТ', 'СОЛОВЕЙ И РОЗА')
    rus['pesni_razine']  = between(p2, 'ПЕСНИ О СТЕНЬКЕ РАЗИНЕ', 'ПРИЗНАНИЕ')
    rus['ya_pomnu']      = after_line(p2, 'Я помню чудное мгновенье', 800)
    rus['esli_zhizn']    = after_line(p2, 'Если жизнь тебя обманет', 300)
    rus['anchar']        = after_line(p2, 'В пустыне чахлой и скупой', 1200)
    rus['pamyatnik']     = after_line(p2, 'Я памятник себе воздвиг нерукотворный', 1200)
    rus['tucha']         = after_line(p2, 'Последняя туча рассеянной бури', 500)
    rus['sapojnik']      = after_line(p2, 'Картину раз высматривал сапожник', 600)
    rus['elegiya']       = after_line(p2, 'Безумных лет угасшее веселье', 700)
    rus['ya_vas_lyubil'] = after_line(p2, 'Я вас любил: любовь еще, быть может', 400)

    # Long poems from p3
    rus['kavkaz_plennik'] = between(p3, 'КАВКАЗСКИЙ ПЛЕННИК', 'ГАВРИИЛИАДА')
    rus['tsygany']         = between(p3, 'ЦЫГАНЫ', 'ЭПИЛОГ')
    rus['rybak']           = between(p3, 'СКАЗКА О РЫБАКЕ И РЫБКЕ',
                                        'СКАЗКА О МЕРТВОЙ ЦАРЕВНЕ И О СЕМИ БОГАТЫРЯХ')
    rus['mertvaya']        = between(p3, 'СКАЗКА О МЕРТВОЙ ЦАРЕВНЕ И О СЕМИ БОГАТЫРЯХ',
                                        'СКАЗКА О ЗОЛОТОМ ПЕТУШКЕ')
    rus['balda']           = between(p3, 'СКАЗКА О ПОПЕ И О РАБОТНИКЕ ЕГО БАЛДЕ',
                                        'СКАЗКА О МЕДВЕДИХЕ')

    # User-provided (1816)
    rus['utro'] = (
        "Румяной зарёю\nПокрылся восток.\nВ селе, за рекою,\nПотух огонёк.\n"
        "Росой окропились\nЦветы на полях.\nСтада пробудились\nНа мягких лугах.\n"
        "Седые туманы\nПлывут к облакам,\nГусей караваны\nНесутся к лугам.\n"
        "Проснулися люди,\nСпешат на поля,\nЯвилося Солнце,\nЛикует земля."
    )

    # From WikiSource HTML
    WS = 'https://ru.wikisource.org/wiki/'
    rus['chernaya_shal'] = fetch_wiki_poem(
        WS + '%D0%A7%D1%91%D1%80%D0%BD%D0%B0%D1%8F_%D1%88%D0%B0%D0%BB%D1%8C_(%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD)')
    rus['mozarti'] = fetch_wiki_poem(
        WS + '%D0%9C%D0%BE%D1%86%D0%B0%D1%80%D1%82_%D0%B8_%D0%A1%D0%B0%D0%BB%D1%8C%D0%B5%D1%80%D0%B8_(%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD)')

    return rus


# ---------------------------------------------------------------------------
# Ingush texts from PDF
# ---------------------------------------------------------------------------

def collect_ingush():
    try:
        import fitz
    except ImportError:
        print("PyMuPDF not installed. Run: pip install pymupdf")
        sys.exit(1)

    doc = fitz.open(str(PDF_2014))
    parts = []
    for i in range(38, 135):   # pages 39..135
        t = doc[i].get_text().strip().replace('\xad', '')
        t = re.sub(r'^\d+\s*\n?', '', t)
        parts.append(t)
    full = '\n\n'.join(parts)

    def cl(s):
        if not s: return ''
        s = re.sub(r'[ \t]+', ' ', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
        return s.strip()

    ing = {}

    # Озиев Ахьмад (pp.39-67)
    ing['kavkaz']         = cl(full[35:1088])
    ing['arion']          = cl(full[1088:1641])
    ing['pamyatnik']      = cl(full[1641:2455])
    ing['rybak']          = cl(full[2455:9076])
    ing['kavkaz_plennik'] = cl(full[9076:30721])

    # Озиев Салман (pp.68-93)
    ing['utro']    = cl(full[30760:31110])
    ing['balda']   = cl(full[31110:38733])
    ing['mertvaya']= cl(full[38733:55346])

    # Муталиев (pp.94-95)
    ing['zimny_vecher']  = cl(full[55414:56201])
    ing['zimnya_doroga'] = cl(full[56201:56642])

    # Чахкиев Ювсап (p.96): two *** poems
    chakh = full[56642:56642+1044]
    m1 = chakh.find('***')
    m2 = chakh.find('***', m1+3)
    ing['esli_zhizn'] = cl(chakh[m1+3:m2])
    ing['ya_pomnu']   = cl(chakh[m2+3:])

    # Чахкиев Саид (pp.97-110): Моцарт и Сальери
    ing['mozarti'] = cl(full[56642+1044:68749])

    # Аушев Муса (pp.111-135)
    aushev = full[68749:]

    def find_section(text, header):
        """Find header ignoring trailing spaces before newline."""
        m = re.search(re.escape(header) + r'\s*\n', text)
        return m.end() if m else -1

    def asub(t1, t2):
        s = find_section(aushev, t1)
        if s < 0: return None
        e = aushev.find(t2, s)
        return cl(aushev[s:e] if e >= 0 else aushev[s:])

    ing['tsygany'] = asub('ЦЫГАНАШ', 'ДОШО ГУЙРЕ')
    idx_anch = aushev.find('АНЧАР', 4000)
    idx_gag  = aushev.find('ГАГИЕВ')
    ing['anchar'] = cl(aushev[idx_anch:idx_gag])

    # Гагиев Гирихан
    gagiev = aushev[idx_gag:]

    def gsub(t1, t2):
        s = find_section(gagiev, t1)
        if s < 0: return None
        e = gagiev.find(t2, s)
        return cl(gagiev[s:e] if e >= 0 else gagiev[s:s+6000])

    ing['pesni_razine'] = gsub('СТЕНЬКА РАЗИНАХ ДОЛА ИЛЛЕШ', '1АЬРЖА ШОВЛАКХ')
    ing['chernaya_shal']= gsub('1АЬРЖА ШОВЛАКХ', 'МОРХ')
    ing['tucha']        = gsub('МОРХ', 'ДОШУВИ БОЛАТИ')
    ing['zoloto_bulat'] = gsub('ДОШУВИ БОЛАТИ', 'КЪАЙЛЕ ЯСТАР')
    ing['sapojnik']     = gsub('ИККИЙ ПХЬАР', 'ЭЛЕГИ')

    # Элегия: from ЭЛЕГИ until КЕПАТОХАНЗА
    elem_s = find_section(gagiev, 'ЭЛЕГИ')
    kep_s  = gagiev.find('КЕПАТОХАНЗА')
    if elem_s >= 0:
        end_e = kep_s if kep_s > elem_s else elem_s + 3000
        ing['elegiya'] = cl(gagiev[elem_s:end_e])

    # Я вас любил: second *** poem inside ДОТТАГ1АШКА section
    dott_s = find_section(gagiev, 'ДОТТАГ1АШКА')
    juk_s  = gagiev.find('ЖУКОВСКЕ СУРТАГА', dott_s) if dott_s >= 0 else -1
    if dott_s >= 0 and juk_s >= 0:
        dott = gagiev[dott_s:juk_s]
        m1d = dott.find('***')
        m2d = dott.find('***', m1d+3) if m1d >= 0 else -1
        if m2d >= 0:
            ing['ya_vas_lyubil'] = cl(dott[m2d+3:])
        elif m1d >= 0:
            ing['ya_vas_lyubil'] = cl(dott[m1d+3:])

    return ing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--write',  action='store_true')
    p.add_argument('--append', action='store_true', help='Append (default=append)')
    return p.parse_args()


def main():
    args = parse_args()

    print("Fetching lib.ru p2, p3...")
    p2 = clean_libru(fetch('http://lib.ru/LITRA/PUSHKIN/p2.txt', enc='koi8-r'))
    p3 = clean_libru(fetch('http://lib.ru/LITRA/PUSHKIN/p3.txt', enc='koi8-r'))
    print(f"  p2={len(p2):,}  p3={len(p3):,}")

    print("Collecting Russian texts...")
    rus = collect_russian(p2, p3)

    print("Extracting Ingush texts from PDF...")
    ing = collect_ingush()

    # Build pairs
    all_keys = sorted(set(list(ing.keys()) + list(rus.keys())))
    ok_pairs = []
    skip = []
    for k in all_keys:
        il = len(ing.get(k) or '')
        rl = len(rus.get(k) or '')
        if il > 50 and rl > 50:
            ok_pairs.append(k)
        else:
            skip.append((k, il, rl))

    print(f"\n{'Key':<20} {'ING':>6} {'RUS':>6}")
    print('-' * 36)
    for k in ok_pairs:
        il = len(ing.get(k) or '')
        rl = len(rus.get(k) or '')
        print(f"  {'OK':<6} {k:<20} {il:>6} {rl:>6}")
    for k, il, rl in skip:
        print(f"  {'SKIP':<6} {k:<20} {il:>6} {rl:>6}")

    print(f"\nTotal pairs: {len(ok_pairs)}")

    if not args.write:
        print("[dry-run] Use --write to append to dataset.")
        return

    pairs = [
        {
            'ing':     ing[k],
            'rus':     rus[k],
            'source':  SOURCE,
            'type':    'poem',
            'poem_id': k,
        }
        for k in ok_pairs
    ]

    with open(OUT_FILE, 'a', encoding='utf-8') as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    print(f"Appended {len(pairs)} pairs → {OUT_FILE}")

    total = sum(1 for _ in open(OUT_FILE, encoding='utf-8'))
    chars_ing = sum(len(p['ing']) for p in pairs)
    chars_rus = sum(len(p['rus']) for p in pairs)
    print(f"Dataset total: {total} records")
    print(f"Chars (ing): {chars_ing:,}  |  (rus): {chars_rus:,}")


if __name__ == '__main__':
    main()
