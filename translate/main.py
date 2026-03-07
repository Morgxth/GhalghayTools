import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MODEL_ID = os.getenv("MODEL_ID", "Targimec/nllb-ingush")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"

app = FastAPI(title="GhalghayTools — Переводчик", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


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
async def translate(req: TranslateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    if len(req.text) > 2000:
        raise HTTPException(status_code=400, detail="Текст слишком длинный (макс. 2000 символов)")

    supported = {"inh_Cyrl", "rus_Cyrl"}
    if req.src_lang not in supported or req.tgt_lang not in supported:
        raise HTTPException(status_code=400, detail=f"Поддерживаются языки: {supported}")
    if req.src_lang == req.tgt_lang:
        raise HTTPException(status_code=400, detail="src_lang и tgt_lang должны различаться")

    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    payload = {
        "inputs": req.text,
        "parameters": {
            "src_lang": req.src_lang,
            "tgt_lang": req.tgt_lang,
            "max_new_tokens": req.max_new_tokens,
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(HF_API_URL, json=payload, headers=headers)

    if resp.status_code == 503:
        raise HTTPException(status_code=503, detail="Модель загружается на HuggingFace, попробуйте через 20 секунд")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"HF API error {resp.status_code}: {resp.text[:200]}")

    result = resp.json()
    if isinstance(result, list) and result:
        translation = result[0].get("translation_text", "")
    else:
        raise HTTPException(status_code=502, detail="Неожиданный ответ от HF API")

    return TranslateResponse(translation=translation, src_lang=req.src_lang, tgt_lang=req.tgt_lang)


@app.get("/translate/api/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "backend": "huggingface-inference-api"}
