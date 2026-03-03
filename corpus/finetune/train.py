"""
Fine-tune NLLB-200-distilled-600M на параллельном корпусе ингушского языка.

Запускать в Google Colab (T4 16GB) или локально с GPU 8GB+.

Инструкция для Colab:
  1. Runtime → Change runtime type → T4 GPU
  2. Загрузи train.jsonl, dev.jsonl в /content/
  3. !pip install transformers[torch] datasets sacrebleu sentencepiece
  4. Запусти этот скрипт: !python train.py
  5. После обучения модель будет в ./nllb-ingush/

Параметры (можно менять):
  --model    : HuggingFace model ID
  --train    : путь к train.jsonl
  --dev      : путь к dev.jsonl
  --epochs   : число эпох (3 рекомендуется)
  --batch    : batch size per device
  --lr       : learning rate
  --max-len  : максимальная длина токенов (src+tgt)
  --out      : папка для сохранения модели
"""

import argparse
import json
import numpy as np
from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
)
import evaluate


# ─── Параметры ────────────────────────────────────────────────────────────────

MODEL_ID   = "facebook/nllb-200-distilled-600M"
ING_LANG   = "inh_Cyrl"
RUS_LANG   = "rus_Cyrl"


# ─── Загрузка данных ──────────────────────────────────────────────────────────

def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def make_dataset(rows):
    return Dataset.from_list(rows)


# ─── Токенизация ──────────────────────────────────────────────────────────────

def get_tokenize_fn(tokenizer, max_len):
    def tokenize(batch):
        # Устанавливаем язык источника для каждого примера
        tokenizer.src_lang = batch["src_lang"][0]  # в батче одинаковый src_lang
        model_inputs = tokenizer(
            batch["src"],
            text_target=batch["tgt"],
            max_length=max_len,
            truncation=True,
            padding=False,
        )
        # Устанавливаем forced_bos_token_id для каждого примера через labels
        # NLLB требует tgt_lang при токенизации target
        with tokenizer.as_target_tokenizer():
            labels = tokenizer(
                batch["tgt"],
                max_length=max_len,
                truncation=True,
                padding=False,
            )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs
    return tokenize


def preprocess_dataset(dataset, tokenizer, max_len, batch_size=256):
    """Токенизируем, группируя по src_lang чтобы корректно ставить язык."""
    # Разбиваем по направлению и токенизируем отдельно
    ing2rus = dataset.filter(lambda x: x["src_lang"] == ING_LANG)
    rus2ing = dataset.filter(lambda x: x["src_lang"] == RUS_LANG)

    def tok(ds, src_lang, tgt_lang):
        def fn(batch):
            tokenizer.src_lang = src_lang
            model_inputs = tokenizer(
                batch["src"],
                max_length=max_len,
                truncation=True,
                padding=False,
            )
            tgt_tokenizer = tokenizer
            tgt_tokenizer.src_lang = tgt_lang
            labels = tgt_tokenizer(
                text_target=batch["tgt"],
                max_length=max_len,
                truncation=True,
                padding=False,
            )
            model_inputs["labels"] = labels["input_ids"]
            return model_inputs
        return ds.map(fn, batched=True, batch_size=batch_size,
                      remove_columns=ds.column_names)

    tok1 = tok(ing2rus, ING_LANG, RUS_LANG)
    tok2 = tok(rus2ing, RUS_LANG, ING_LANG)

    from datasets import concatenate_datasets
    combined = concatenate_datasets([tok1, tok2])
    return combined.shuffle(seed=42)


# ─── BLEU метрика ─────────────────────────────────────────────────────────────

def make_compute_metrics(tokenizer):
    bleu = evaluate.load("sacrebleu")

    def compute_metrics(eval_pred):
        preds, labels = eval_pred
        # Декодируем
        if isinstance(preds, tuple):
            preds = preds[0]
        preds = np.where(preds != -100, preds, tokenizer.pad_token_id)
        decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

        decoded_preds  = [p.strip() for p in decoded_preds]
        decoded_labels = [[l.strip()] for l in decoded_labels]

        result = bleu.compute(predictions=decoded_preds, references=decoded_labels)
        return {"bleu": round(result["score"], 2)}

    return compute_metrics


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",   default=MODEL_ID)
    parser.add_argument("--train",   default="train.jsonl")
    parser.add_argument("--dev",     default="dev.jsonl")
    parser.add_argument("--epochs",  type=int,   default=3)
    parser.add_argument("--batch",   type=int,   default=8)
    parser.add_argument("--grad-acc",type=int,   default=4,  help="Gradient accumulation steps")
    parser.add_argument("--lr",      type=float, default=5e-5)
    parser.add_argument("--max-len", type=int,   default=128)
    parser.add_argument("--out",     default="./nllb-ingush")
    parser.add_argument("--fp16",    action="store_true", default=torch.cuda.is_available())
    parser.add_argument("--no-grad-ckpt", action="store_true", help="Disable gradient checkpointing")
    args = parser.parse_args()

    print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'нет'}")
    print(f"Модель: {args.model}")

    # Загрузка модели и токенизатора
    print("\nЗагрузка токенизатора и модели...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)

    param_count = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"Параметров: {param_count:.0f}M")

    # Данные
    print("\nЗагрузка данных...")
    train_rows = load_jsonl(args.train)
    dev_rows   = load_jsonl(args.dev)
    print(f"Train: {len(train_rows):,}  Dev: {len(dev_rows):,}")

    train_ds = make_dataset(train_rows)
    dev_ds   = make_dataset(dev_rows)

    print("Токенизация...")
    train_tok = preprocess_dataset(train_ds, tokenizer, args.max_len)
    dev_tok   = preprocess_dataset(dev_ds,   tokenizer, args.max_len)
    print(f"Train токенизировано: {len(train_tok):,}  Dev: {len(dev_tok):,}")

    # Effective batch = batch * grad_acc
    eff_batch = args.batch * args.grad_acc
    steps_per_epoch = len(train_tok) // eff_batch
    print(f"\nEff. batch size: {eff_batch}, шагов/эпоха: {steps_per_epoch:,}")

    # Аргументы обучения
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_acc,
        learning_rate=args.lr,
        warmup_steps=min(500, steps_per_epoch // 2),
        weight_decay=0.01,

        fp16=args.fp16,
        gradient_checkpointing=not args.no_grad_ckpt,
        optim="adafactor",
        predict_with_generate=True,
        generation_max_length=args.max_len,

        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="bleu",
        greater_is_better=True,

        logging_steps=50,
        report_to="none",   # поставь "tensorboard" если хочешь логи
        save_total_limit=2,

        dataloader_num_workers=0,   # 0 для Colab/Windows
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        padding=True,
        pad_to_multiple_of=8 if args.fp16 else None,
    )

    # processing_class= появился в transformers 4.46, до этого — tokenizer=
    import transformers as _tr
    _tr_ver = tuple(int(x) for x in _tr.__version__.split(".")[:2])
    _trainer_kwargs = dict(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=dev_tok,
        data_collator=data_collator,
        compute_metrics=make_compute_metrics(tokenizer),
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )
    if _tr_ver >= (4, 46):
        _trainer_kwargs["processing_class"] = tokenizer
    else:
        _trainer_kwargs["tokenizer"] = tokenizer

    trainer = Seq2SeqTrainer(**_trainer_kwargs)

    print("\n=== Начало обучения ===")
    trainer.train()

    print(f"\n=== Сохранение модели в {args.out} ===")
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)

    # Финальная оценка на dev
    print("\n=== Финальная оценка на dev ===")
    metrics = trainer.evaluate()
    print(f"BLEU (dev): {metrics.get('eval_bleu', '?')}")


if __name__ == "__main__":
    main()
