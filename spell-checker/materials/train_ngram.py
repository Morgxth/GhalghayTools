"""
Обучает N-gram модель на ингушском корпусе (Лоаман Iуйре).
Сохраняет биграммы и юниграммы в resources для загрузки Spring Boot.
Запуск: python3 train_ngram.py
"""

import fitz
import re
import json
import sys
import io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CORPUS_PDFS = [
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1973, №1-4) (1).pdf",
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1976, №2).pdf",
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1984, №1-4).pdf",
]

OUTPUT_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\ngram\ingush_ngrams.json"

# Минимальная частота чтобы попасть в модель (фильтруем шум)
MIN_UNIGRAM_FREQ = 2
MIN_BIGRAM_FREQ  = 2


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def is_ingush_word(word: str) -> bool:
    """Берём только слова с ингушскими паттернами."""
    if len(word) < 2:
        return False
    ingush = re.compile(
        r'(ӏ|гӏ|хь|кх|аь|еь|оь|уь|иь|ийта|аьнна|елла|овла|еннаб)',
        re.IGNORECASE
    )
    return bool(ingush.search(word))


def tokenize(text: str) -> list[str]:
    """Извлекает ингушские слова из текста."""
    text = normalize_palochka(text.lower())
    words = re.findall(r'[а-яёӏ][а-яёӏ\-]*', text)
    return [w.strip('-') for w in words if len(w) >= 2]


def extract_corpus(pdf_paths: list[str]) -> list[str]:
    """Читает все PDF и возвращает список слов."""
    all_tokens = []
    for path in pdf_paths:
        doc = fitz.open(path)
        name = path.split('\\')[-1]
        tokens_in_doc = []
        for page in doc:
            text = page.get_text()
            tokens = tokenize(text)
            tokens_in_doc.extend(tokens)
        all_tokens.extend(tokens_in_doc)
        print(f"  {name}: {len(tokens_in_doc):,} токенов")
    return all_tokens


def build_ngrams(tokens: list[str]) -> tuple[dict, dict]:
    """Строит счётчики юниграмм и биграмм."""
    unigrams = Counter(tokens)

    bigrams = Counter()
    for i in range(len(tokens) - 1):
        # Пропускаем биграммы через страничные границы (очень редкие пары)
        bigram = f"{tokens[i]} {tokens[i+1]}"
        bigrams[bigram] += 1

    # Фильтруем шум
    unigrams = {w: c for w, c in unigrams.items()
                if c >= MIN_UNIGRAM_FREQ and is_ingush_word(w)}
    bigrams  = {bg: c for bg, c in bigrams.items()
                if c >= MIN_BIGRAM_FREQ}

    return unigrams, bigrams


def save_model(unigrams: dict, bigrams: dict, output_path: str):
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Сортируем по частоте (самые частые первыми — для удобства отладки)
    data = {
        "totalTokens": sum(unigrams.values()),
        "unigrams": dict(sorted(unigrams.items(), key=lambda x: -x[1])),
        "bigrams":  dict(sorted(bigrams.items(),  key=lambda x: -x[1])),
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"\nСохранено: {output_path} ({size_kb} КБ)")


if __name__ == '__main__':
    print("Читаю корпус...")
    tokens = extract_corpus(CORPUS_PDFS)
    print(f"\nВсего токенов: {len(tokens):,}")

    print("\nСтрою N-gram модель...")
    unigrams, bigrams = build_ngrams(tokens)
    print(f"Юниграмм (уникальных слов): {len(unigrams):,}")
    print(f"Биграмм (пар слов):         {len(bigrams):,}")

    print("\nТоп-20 самых частых слов:")
    for w, c in sorted(unigrams.items(), key=lambda x: -x[1])[:20]:
        print(f"  {w:20s} {c}")

    save_model(unigrams, bigrams, OUTPUT_PATH)
    print("Готово!")
