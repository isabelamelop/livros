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


# -------------------------
# REQUESTS
# -------------------------
class SearchRequest(BaseModel):
    query: str


class SelectRequest(BaseModel):
    command: str


# -------------------------
# ENV
# -------------------------
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME")

SESSION = os.getenv("TELEGRAM_SESSION_STRING", "")

RESPONSE_TIMEOUT = 12
FOLLOWUP_IDLE_TIMEOUT = 1.5


# -------------------------
# STATE
# -------------------------
client: Optional[TelegramClient] = None
lock = asyncio.Lock()
download_cache = {}


def normalize_download_filename(filename: str) -> str:
    clean_name = Path(filename or "").name.strip()
    if not clean_name:
        return "livro.epub"

    suffix = Path(clean_name).suffix
    stem = Path(clean_name).stem

    stem = stem.replace("_", " ")
    stem = re.sub(
        r"\b(?:z[\s-]*library|z[\s-]*lib|1lib|sk|lib\s*sk)\b",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    stem = re.sub(r"\s*,\s*", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -_,.;")

    if not stem:
        stem = "livro"

    if not suffix:
        suffix = ".epub"

    return f"{stem}{suffix}"


# -------------------------
# PARSER CORRIGIDO (🔥 CORAÇÃO DO FIX)
# -------------------------
def parse_books(text: str):
    """Extrai opções de livro ignorando emojis decorativos e linhas de resumo."""

    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(
        r"(?im)^\s*📚\s*(good\s+news!\s*we\s+found.*)$",
        r"\1",
        normalized,
    )
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    books = []

    def clean_title(value: str) -> str:
        cleaned = value
        if cleaned.startswith("📚"):
            cleaned = cleaned[1:].strip()
        cleaned = cleaned.replace("↗️", "").strip()
        return cleaned.strip(" -–:()")

    def is_summary_line(value: str) -> bool:
        lower = value.lower()
        return (
            "good news" in lower
            or "we found" in lower
            or "on your request" in lower
            or "sugest" in lower
        )

    def is_metadata(value: str) -> bool:
        lower = value.lower()
        return (
            value.startswith("🌐")
            or value.startswith("/")
            or value == "↗️"
            or bool(re.search(r"\b(epub|pdf|mobi|azw3|fb2)\b", lower))
            or bool(re.search(r"\d+(?:[\.,]\d+)?\s*(kb|mb|gb)\b", lower))
            or is_summary_line(value)
        )

    def extract_format(value: str) -> str:
        compact = re.sub(r"[^a-z]", "", value.lower())
        if "epub" in compact:
            return "EPUB"
        if "pdf" in compact:
            return "PDF"
        if "mobi" in compact:
            return "MOBI"
        if "azw3" in compact:
            return "AZW3"
        if "fb2" in compact:
            return "FB2"
        return ""

    for i, line in enumerate(lines):
        command_match = re.search(r"(/book_[^\s\n\r]+)", line)
        if not command_match:
            continue

        command = command_match.group(1)
        command_suffix = line[command_match.end():]

        title = ""
        title_line_index = None
        for j in range(i - 1, max(-1, i - 8), -1):
            candidate = lines[j]
            if candidate.startswith("📚"):
                candidate_title = clean_title(candidate)
                if candidate_title and not is_summary_line(candidate_title):
                    title = candidate_title
                    title_line_index = j
                    break

        if not title:
            title = f"Livro {len(books) + 1}"

        segment_start = title_line_index + 1 if title_line_index is not None else max(0, i - 6)
        segment_lines = lines[segment_start:i]
        context_lines = segment_lines + [line] + lines[i + 1:min(len(lines), i + 3)]

        author = ""
        language = "—"
        fmt = extract_format(command_suffix)
        size_match_on_command = re.search(
            r"\d+(?:[\.,]\d+)?\s*(KB|MB|GB)\b",
            command_suffix,
            re.IGNORECASE,
        )
        size = size_match_on_command.group(0).upper() if size_match_on_command else ""

        for segment_line in context_lines:
            language_match = re.search(r"🌐\s*(.+)$", segment_line)
            if language_match and language_match.group(1).strip():
                language = language_match.group(1).strip()

            if not fmt:
                fmt = extract_format(segment_line)

            size_match = re.search(r"\d+(?:[\.,]\d+)?\s*(KB|MB|GB)\b", segment_line, re.IGNORECASE)
            if size_match and not size:
                size = size_match.group(0).upper()

            cleaned_segment = clean_title(segment_line)
            if (
                not author
                and segment_line in segment_lines
                and cleaned_segment
                and not is_metadata(segment_line)
                and cleaned_segment != title
            ):
                author = cleaned_segment

        book_info = {
            "command": command,
            "title": title,
            "author": author or "Autor desconhecido",
            "language": language,
            "format": fmt,
            "size": size,
        }

        books.append(book_info)
        print(f"✅ PARSER: '{command}' → '{book_info['title']}' por '{book_info['author']}'")

    print(f"📚 Total: {len(books)} livros parseados")
    return books


# -------------------------
# APP
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram not authorized")
    await client.get_entity(BOT_USERNAME)
    yield
    if client:
        await client.disconnect()


app = FastAPI(title="Books API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# SEARCH
# -------------------------
@app.post("/search")
async def search(payload: SearchRequest):
    if not payload.query.strip():
        raise HTTPException(400, "query required")

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    sent_id = None

    async def handler(event):
        nonlocal sent_id
        if event.out or sent_id is None or event.message.id <= sent_id:
            return
        queue.put_nowait(event.message)

    event = events.NewMessage(chats=BOT_USERNAME, incoming=True)

    async with lock:
        client.add_event_handler(handler, event)
        try:
            sent = await client.send_message(BOT_USERNAME, payload.query)
            sent_id = sent.id

            deadline = loop.time() + RESPONSE_TIMEOUT
            full_text = ""

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=min(remaining, FOLLOWUP_IDLE_TIMEOUT))
                    text = msg.raw_text or ""
                    if text:
                        full_text += "\n" + text
                except asyncio.TimeoutError:
                    break

            books = parse_books(full_text)
            return {"options": books}

        finally:
            client.remove_event_handler(handler, event)


# -------------------------
# SELECT
# -------------------------
@app.post("/select")
async def select(payload: SelectRequest):
    if not payload.command:
        raise HTTPException(400, "command required")

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    sent_id = None

    async def handler(event):
        nonlocal sent_id
        if event.out or sent_id is None or event.message.id <= sent_id:
            return
        queue.put_nowait(event.message)

    event = events.NewMessage(chats=BOT_USERNAME, incoming=True)

    async with lock:
        client.add_event_handler(handler, event)
        try:
            sent = await client.send_message(BOT_USERNAME, payload.command)
            sent_id = sent.id

            deadline = loop.time() + RESPONSE_TIMEOUT

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                if msg.document:
                    file_bytes = await client.download_media(msg, file=bytes)
                    token = uuid.uuid4().hex
                    normalized_filename = normalize_download_filename(
                        msg.file.name or f"livro_{payload.command}"
                    )
                    download_cache[token] = {
                        "filename": normalized_filename,
                        "mime_type": msg.file.mime_type or "application/octet-stream",
                        "content": file_bytes,
                    }
                    print(f"📦 Download: {download_cache[token]['filename']}")
                    return {
                        "document": {
                            "download_url": f"/download/{token}",
                            "filename": download_cache[token]["filename"]
                        }
                    }

                text = msg.raw_text or ""
                match = re.search(r'https?://[^\s<>"]+', text)
                if match:
                    return {
                        "document": {
                            "download_url": match.group(0),
                            "filename": "livro_direct_link"
                        }
                    }

        finally:
            client.remove_event_handler(handler, event)

    raise HTTPException(404, "No document found")


# -------------------------
# DOWNLOAD & HEALTH
# -------------------------
@app.get("/download/{token}")
async def download(token: str):
    file = download_cache.pop(token, None)
    if not file:
        raise HTTPException(404, "File expired")
    return StreamingResponse(
        iter([file["content"]]),
        media_type=file["mime_type"],
        headers={"Content-Disposition": f'attachment; filename="{file["filename"]}"'}
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
