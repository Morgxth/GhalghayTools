import os
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from transformers import NllbTokenizer, AutoModelForSeq2SeqLM

MODEL_ID = os.getenv("MODEL_ID", "Targimec/nllb-ingush")
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI(title="GhalghayTools — Переводчик", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Загружаем модель один раз при старте
print(f"Загрузка модели {MODEL_ID} на {DEVICE}...")
tokenizer = NllbTokenizer.from_pretrained(MODEL_ID)
model     = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID).to(DEVICE)
model.eval()
print("Модель готова.")


class TranslateRequest(BaseModel):
    text:     str
    src_lang: str = "inh_Cyrl"
    tgt_lang: str = "rus_Cyrl"
    max_new_tokens: int = 256


class TranslateResponse(BaseModel):
    translation: str
    src_lang:    str
    tgt_lang:    str


@app.post("/translate/api/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    if len(req.text) > 2000:
        raise HTTPException(status_code=400, detail="Текст слишком длинный (макс. 2000 символов)")

    supported = {"inh_Cyrl", "rus_Cyrl"}
    if req.src_lang not in supported or req.tgt_lang not in supported:
        raise HTTPException(status_code=400, detail=f"Поддерживаются языки: {supported}")
    if req.src_lang == req.tgt_lang:
        raise HTTPException(status_code=400, detail="src_lang и tgt_lang должны различаться")

    tokenizer.src_lang = req.src_lang
    inputs = tokenizer(req.text, return_tensors="pt", truncation=True, max_length=256).to(DEVICE)
    tgt_id = tokenizer.convert_tokens_to_ids(req.tgt_lang)

    with torch.no_grad():
        out = model.generate(**inputs, forced_bos_token_id=tgt_id, max_new_tokens=req.max_new_tokens)

    translation = tokenizer.decode(out[0], skip_special_tokens=True)
    return TranslateResponse(translation=translation, src_lang=req.src_lang, tgt_lang=req.tgt_lang)


@app.get("/translate/api/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE}


# Serve static frontend — must be mounted AFTER API routes
app.mount("/translate", StaticFiles(directory="static", html=True), name="static")
