# Fine-tune NLLB-200 на ингушском — инструкция для Colab

## Что получим
Модель NLLB-200-distilled-600M (600M параметров), дообученная на 16K параллельных пар
ингушского и русского языка. Умеет переводить в оба направления: inh→rus и rus→inh.

## Шаги

### 1. Подготовь данные (локально, уже сделано)
```
python prepare_data.py
```
Результат: `train.jsonl` (29K), `dev.jsonl` (1.6K), `test.jsonl` (1.6K)

### 2. Открой Google Colab
https://colab.research.google.com/

Runtime → Change runtime type → **T4 GPU** (бесплатно)

### 3. Загрузи файлы в Colab
```python
from google.colab import files
uploaded = files.upload()  # выбери train.jsonl, dev.jsonl, test.jsonl, train.py
```
Или через Google Drive:
```python
from google.colab import drive
drive.mount('/content/drive')
# Положи файлы в My Drive/nllb-ingush/
```

### 4. Установи зависимости
```python
!pip install -q transformers[torch] datasets sacrebleu sentencepiece evaluate
```

### 5. Запусти обучение
```python
!python train.py \
    --train train.jsonl \
    --dev   dev.jsonl \
    --epochs 3 \
    --batch 8 \
    --grad-acc 4 \
    --lr 5e-5 \
    --max-len 128 \
    --out ./nllb-ingush
```

Эффективный batch = 8 × 4 = 32. При ~29K train примерах:
- ~906 шагов/эпоха
- ~2718 шагов всего
- Время: ~1.5–2 часа на T4

### 6. Скачай модель
```python
import shutil
shutil.make_archive('/content/nllb-ingush', 'zip', '/content/nllb-ingush')
files.download('/content/nllb-ingush.zip')
```

### 7. Протестируй перевод
```python
from transformers import pipeline

pipe = pipeline(
    "translation",
    model="./nllb-ingush",
    src_lang="inh_Cyrl",
    tgt_lang="rus_Cyrl",
    max_length=256,
)

print(pipe("Даьла безам бе, со воккхавелча вай хьалхара г1алг1ай хилар ховш хила безам бу суна."))
```

## Параметры для экспериментов

| Параметр | Базовый | Если VRAM < 8GB | Если хочешь качество |
|----------|---------|-----------------|----------------------|
| batch    | 8       | 4               | 8                    |
| grad-acc | 4       | 8               | 8                    |
| max-len  | 128     | 96              | 192                  |
| epochs   | 3       | 3               | 5                    |
| lr       | 5e-5    | 3e-5            | 3e-5                 |

## Оценка (BLEU)

После каждой эпохи выводится BLEU на dev. Ожидаемые результаты:
- BLEU 5–10: модель что-то выучила, но качество низкое
- BLEU 10–20: читаемые переводы, полезно для понимания
- BLEU 20+: хорошее качество (сложно достичь на таком малом корпусе)

Для ингушского с 16K пар реалистично ожидать BLEU 8–15 (inh→rus).

## Следующие шаги после первого запуска

1. Посмотреть примеры переводов — важнее BLEU
2. Добавить данные (цель: 50K+ пар)
3. Попробовать `nllb-200-1.3B` если качество недостаточное
4. Загрузить модель на HuggingFace Hub для публичного доступа
