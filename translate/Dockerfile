FROM python:3.12-slim

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скачиваем модель во время сборки образа (не при каждом старте)
ARG MODEL_ID=Targimec/nllb-ingush
RUN python -c "from transformers import NllbTokenizer, AutoModelForSeq2SeqLM; \
    NllbTokenizer.from_pretrained('${MODEL_ID}'); \
    AutoModelForSeq2SeqLM.from_pretrained('${MODEL_ID}')"

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
