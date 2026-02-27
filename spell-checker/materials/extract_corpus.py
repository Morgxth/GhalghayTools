"""
Извлекает ингушские слова из текстовых альманахов Лоаман Iуйре.
Добавляет живые слова которых нет в академическом словаре Куркиева.
Запуск: python3 extract_corpus.py
"""

import fitz
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CORPUS_PDFS = [
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1973, №1-4) (1).pdf",
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1976, №2).pdf",
    r"C:\Users\goygo\OneDrive\Desktop\SomeApp\materials\Лоаман Iуйре (1984, №1-4).pdf",
]

DICTIONARY_PATH = r"C:\Users\goygo\OneDrive\Desktop\SomeApp\src\main\resources\dictionary\ingush_words.txt"

# Слова которые явно русские — пропускаем
RUSSIAN_STOPWORDS = {
    'это', 'как', 'что', 'для', 'или', 'при', 'не', 'но', 'по', 'из',
    'от', 'до', 'на', 'за', 'со', 'об', 'во', 'же', 'бы', 'ли', 'бы',
    'все', 'был', 'она', 'они', 'его', 'её', 'их', 'нет', 'так',
    'уже', 'ещё', 'тот', 'эта', 'эти', 'был', 'быть',
}

# Признаки ингушского слова — специфичные сочетания букв
INGUSH_PATTERNS = re.compile(
    r'(ӏ|гӏ|хь|кх|аь|еь|оь|уь|иь|юь|яь|ийта|ийт|аьнна|елла|'
    r'овла|алла|еннаб|аьб|елаб|илла|ерг|ерш|арг|арш)',
    re.IGNORECASE
)


def normalize_palochka(text: str) -> str:
    text = text.replace('\u04c0', 'ӏ')
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])I', 'ӏ', text)
    text = re.sub(r'(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])', 'ӏ', text)
    return text


def is_ingush_word(word: str) -> bool:
    if len(word) < 2:
        return False
    if word in RUSSIAN_STOPWORDS:
        return False
    # Слово должно содержать хотя бы один ингушский паттерн
    return bool(INGUSH_PATTERNS.search(word))


def extract_from_corpus(pdf_path: str) -> set[str]:
    doc = fitz.open(pdf_path)
    words = set()

    for page in doc:
        text = page.get_text()
        text = normalize_palochka(text)

        for word in re.findall(r'[а-яёӏА-ЯЁ][а-яёӏА-ЯЁ\-]*', text):
            word = word.lower().strip('-')
            if is_ingush_word(word):
                words.add(word)

    return words


def load_existing_words(path: str) -> set[str]:
    words = set()
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    words.add(line)
    except FileNotFoundError:
        pass
    return words


def append_new_words(path: str, new_words: set[str], existing: set[str], source: str):
    added = new_words - existing
    if not added:
        print(f"  Новых слов: 0")
        return 0

    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'\n# Добавлено из корпуса: {source}\n')
        for word in sorted(added):
            f.write(word + '\n')

    print(f"  Новых слов: {len(added)}")
    return len(added)


if __name__ == '__main__':
    print("Загружаю существующий словарь...")
    existing = load_existing_words(DICTIONARY_PATH)
    print(f"Слов в словаре: {len(existing)}")

    total_added = 0
    for pdf_path in CORPUS_PDFS:
        name = pdf_path.split('\\')[-1]
        print(f"\nКорпус: {name}...")
        words = extract_from_corpus(pdf_path)
        print(f"Ингушских слов в тексте: {len(words)}")
        added = append_new_words(DICTIONARY_PATH, words, existing, name)
        existing.update(words)
        total_added += added

    print(f"\nГотово! Добавлено новых слов: {total_added}")
    print(f"Итого в словаре: {len(existing)}")
