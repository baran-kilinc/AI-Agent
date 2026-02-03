import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.bmw_client import bmw_chat, load_system_prompt
from backend.session_store import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat_app")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "1048576"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "20"))

session_store = SessionStore(ttl_seconds=SESSION_TTL_SECONDS, max_messages=MAX_MESSAGES)

app = FastAPI()

allowed_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large."},
        )
    return await call_next(request)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def read_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
async def chat(payload: dict):
    message = payload.get("message")
    if not message or not isinstance(message, str):
        raise HTTPException(status_code=400, detail="Message is required.")

    session_id = payload.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    system_prompt = load_system_prompt()
    history = session_store.get_messages(session_id)
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": message})

    logger.info("Session %s: %s", session_id, message)
    reply = bmw_chat(messages)

    session_store.add_message(session_id, "user", message)
    session_store.add_message(session_id, "assistant", reply)

    return {"session_id": session_id, "reply": reply}


def _cleanup_loop(interval_seconds: int = 300) -> None:
    while True:
        removed = session_store.cleanup_expired()
        if removed:
            logger.info("Removed %s expired sessions", removed)
        time.sleep(interval_seconds)


@app.on_event("startup")
def start_cleanup_thread() -> None:
    thread = threading.Thread(target=_cleanup_loop, daemon=True)
    thread.start()
