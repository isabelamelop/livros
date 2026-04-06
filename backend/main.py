import asyncio
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv


class SearchRequest(BaseModel):
    query: str


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")


API_ID_RAW = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_user")
TELEGRAM_SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING", "").strip()
ALLOW_INTERACTIVE_LOGIN = os.getenv("ALLOW_INTERACTIVE_LOGIN", "false").lower() == "true"
RESPONSE_TIMEOUT = float(os.getenv("RESPONSE_TIMEOUT", "10"))
FOLLOWUP_IDLE_TIMEOUT = float(os.getenv("FOLLOWUP_IDLE_TIMEOUT", "1.5"))
FILE_WAIT_HINTS = (
    "sending you a file",
    "please wait",
    "aguarde",
    "enviando",
    "arquivo",
)

if not API_ID_RAW:
    raise RuntimeError("Missing API_ID environment variable")
if not API_HASH:
    raise RuntimeError("Missing API_HASH environment variable")
if not BOT_USERNAME:
    raise RuntimeError("Missing BOT_USERNAME environment variable")

try:
    API_ID = int(API_ID_RAW)
except ValueError as error:
    raise RuntimeError("API_ID must be an integer") from error

telegram_client: Optional[TelegramClient] = None
telegram_lock = asyncio.Lock()
download_cache: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    global telegram_client
    session = StringSession(TELEGRAM_SESSION_STRING) if TELEGRAM_SESSION_STRING else SESSION_NAME
    telegram_client = TelegramClient(session, API_ID, API_HASH)

    if ALLOW_INTERACTIVE_LOGIN:
        await telegram_client.start()
    else:
        await telegram_client.connect()
        is_authorized = await telegram_client.is_user_authorized()
        if not is_authorized:
            raise RuntimeError(
                "Telegram session is not authorized. "
                "Set TELEGRAM_SESSION_STRING (recommended for Render) "
                "or enable ALLOW_INTERACTIVE_LOGIN=true for local interactive login."
            )

    await telegram_client.get_entity(BOT_USERNAME)

    try:
        yield
    finally:
        if telegram_client is not None and telegram_client.is_connected():
            await telegram_client.disconnect()


app = FastAPI(title="Telegram Search API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/search")
async def search_book(payload: SearchRequest):
    if telegram_client is None or not telegram_client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram client is not connected")

    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Field 'query' cannot be empty")

    loop = asyncio.get_running_loop()
    sent_message_id: Optional[int] = None
    incoming_messages: asyncio.Queue = asyncio.Queue()

    async def on_new_message(event):
        nonlocal sent_message_id

        if event.out:
            return

        if sent_message_id is None:
            return

        if event.message.id > sent_message_id:
            incoming_messages.put_nowait(event.message)

    event_builder = events.NewMessage(chats=BOT_USERNAME, incoming=True)

    async with telegram_lock:
        telegram_client.add_event_handler(on_new_message, event_builder)
        try:
            sent_message = await telegram_client.send_message(BOT_USERNAME, query)
            sent_message_id = sent_message.id

            deadline = loop.time() + RESPONSE_TIMEOUT
            received_any = False
            waiting_for_document = False
            response_chunks: list[str] = []
            download_payload = None

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break

                wait_timeout = min(remaining, FOLLOWUP_IDLE_TIMEOUT if received_any else remaining)

                try:
                    message = await asyncio.wait_for(incoming_messages.get(), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    if received_any:
                        if waiting_for_document:
                            continue
                        break
                    raise HTTPException(
                        status_code=504,
                        detail=f"No reply from bot within {RESPONSE_TIMEOUT:.0f} seconds",
                    )

                received_any = True

                message_text = (message.raw_text or "").strip()
                if message_text:
                    response_chunks.append(message_text)
                    normalized_text = message_text.lower()
                    if any(hint in normalized_text for hint in FILE_WAIT_HINTS):
                        waiting_for_document = True

                if message.document is not None:
                    file_bytes = await telegram_client.download_media(message, file=bytes)
                    if file_bytes is not None:
                        filename = None
                        if message.file is not None:
                            filename = message.file.name

                        if not filename:
                            filename = f"telegram_document_{message.id}"

                        mime_type = "application/octet-stream"
                        if message.file is not None and message.file.mime_type:
                            mime_type = message.file.mime_type

                        token = uuid.uuid4().hex
                        download_cache[token] = {
                            "filename": filename,
                            "mime_type": mime_type,
                            "content": file_bytes,
                        }
                        download_payload = {
                            "filename": filename,
                            "mime_type": mime_type,
                            "download_url": f"/download/{token}",
                        }
                        waiting_for_document = False
                    break
                elif waiting_for_document:
                    continue
        finally:
            telegram_client.remove_event_handler(on_new_message, event_builder)

    combined_response = "\n\n".join(response_chunks).strip()
    options = sorted(set(re.findall(r"/book_[A-Za-z0-9]+", combined_response)))

    return {
        "query": query,
        "response": combined_response,
        "options": options,
        "document": download_payload,
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/download/{token}")
async def download_document(token: str):
    file_entry = download_cache.get(token)
    if file_entry is None:
        raise HTTPException(status_code=404, detail="File not found or expired")

    return StreamingResponse(
        iter([file_entry["content"]]),
        media_type=file_entry["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename=\"{file_entry['filename']}\""
        },
    )
