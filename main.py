import asyncio
import json
import logging
import os
import time
import uuid
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from masking_pipeline import MaskingPipeline
from stream_interceptor import unmask_stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-24s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pii_proxy")

app = FastAPI(title="PII Masking Proxy", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MAX_MESSAGE_LENGTH = 5000

async def fake_llm_stream(prompt: str):
    masks_in_prompt = re.findall(r"\[[A-Z_]+_\d+\]", prompt)

    if masks_in_prompt:
        response = f"Здравствуйте, {masks_in_prompt[0]}! "
        response += "Я обработал ваш запрос. "
        if len(masks_in_prompt) > 1:
            response += f"Данные по {masks_in_prompt[1]} проверены. "
        if len(masks_in_prompt) > 2:
            others = ", ".join(masks_in_prompt[2:])
            response += f"Также подтверждаю получение: {others}. "
        response += "Чем ещё могу помочь?"
    else:
        response = (
            "Здравствуйте! Я вижу ваш запрос. "
            "Позвольте помочь. "
            "Готово! Обращайтесь, если будут вопросы."
        )

    words = response.split(" ")
    i = 0
    while i < len(words):
        chunk_size = min(2, len(words) - i)
        chunk = " ".join(words[i : i + chunk_size])
        if i + chunk_size < len(words):
            chunk += " "
        yield chunk
        i += chunk_size
        await asyncio.sleep(0.04)

def validate_message(body: dict) -> tuple[str | None, str | None]:
    message = body.get("message")
    if message is None:
        return None, "Поле 'message' обязательно"
    if not isinstance(message, str):
        return None, "Поле 'message' должно быть строкой"
    message = message.strip()
    if not message:
        return None, "Сообщение не может быть пустым"
    if len(message) > MAX_MESSAGE_LENGTH:
        return None, f"Сообщение слишком длинное (макс. {MAX_MESSAGE_LENGTH} символов)"
    return message, None

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    user_message, error = validate_message(body)
    if error:
        return JSONResponse({"error": error}, status_code=400)
    request_id = uuid.uuid4().hex[:8]
    pipeline = MaskingPipeline()
    t_start = time.perf_counter()
    masked_text, mapping = await asyncio.to_thread(pipeline.mask, user_message)
    t_mask = (time.perf_counter() - t_start) * 1000
    logger.info(
        "[%s] MASK │ %d entities │ %.1f ms │ %s → %s",
        request_id,
        len(mapping),
        t_mask,
        repr(user_message[:80]),
        repr(masked_text[:80]),
    )
    async def event_stream():
        meta = {
            "type": "meta",
            "request_id": request_id,
            "masked_text": masked_text,
            "masking_time_ms": round(t_mask, 1),
            "entities_found": [
                {"token": k, "original": v} for k, v in mapping.items()
            ],
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
        llm_stream = fake_llm_stream(masked_text)
        async for piece in unmask_stream(llm_stream, mapping):
            payload = {"type": "token", "content": piece}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        logger.info("[%s] DONE │ stream complete", request_id)
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/mask_only")
async def mask_only(request: Request):
    body = await request.json()
    user_message, error = validate_message(body)
    if error:
        return JSONResponse({"error": error}, status_code=400)
    pipeline = MaskingPipeline()
    t_start = time.perf_counter()
    masked_text, mapping = await asyncio.to_thread(pipeline.mask, user_message)
    t_mask = (time.perf_counter() - t_start) * 1000
    logger.info(
        "MASK_ONLY │ %d entities │ %.1f ms",
        len(mapping),
        t_mask,
    )
    return {
        "original": user_message,
        "masked": masked_text,
        "mapping": {k: v for k, v in mapping.items()},
        "masking_time_ms": round(t_mask, 1),
    }

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
