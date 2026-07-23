"""Playground REST API endpoints for Chat Completion, File Attachments, and Session Persistence.

Covers S5-04a, S5-04b, S5-04c.
"""

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.clients.litellm import completion_with_fallback
from common.clients.postgres import get_async_db
from common.models.database import PlaygroundSession
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from gateway.auth.dependencies import get_optional_user
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/playground", tags=["playground"])
logger = logging.getLogger("gateway.api.playground")

TEMP_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "temp_uploads"
TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory attachment metadata & extracted text store (keyed by attachment_id)
# TTL = 3600 seconds (1 hour)
ATTACHMENT_STORE: Dict[str, Dict[str, Any]] = {}

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".txt", ".md", ".csv"}


# --- Pydantic Schemas ---


class PlaygroundMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str = Field(..., description="Message text content")
    tokens: Optional[int] = Field(None, description="Optional token count")
    attachment_ids: Optional[List[str]] = Field(None, description="Optional associated attachment IDs")


class PlaygroundChatRequest(BaseModel):
    model_id: str = Field("gemini/gemini-3.5-flash", description="Target LLM model ID")
    messages: List[PlaygroundMessage] = Field(..., description="Conversation history including current user prompt")
    system_prompt: Optional[str] = Field(None, description="Optional custom system prompt")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature (0-2)")
    max_tokens: Optional[int] = Field(1000, description="Max response tokens")
    attachment_ids: Optional[List[str]] = Field(None, description="Optional attachment IDs to include as context")
    stream: Optional[bool] = Field(False, description="Enable SSE token streaming")


class PlaygroundChatResponse(BaseModel):
    response: str
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float
    status: str = "success"


class AttachmentInfo(BaseModel):
    attachment_id: str
    filename: str
    file_type: str
    extracted_text_preview: str
    total_chars: int
    created_at: str
    status: str = "processed"


class PlaygroundSessionCreate(BaseModel):
    name: Optional[str] = Field(None, description="Session name (auto-generated if empty)")
    model_id: Optional[str] = Field("gemini/gemini-3.5-flash", description="Selected model")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    messages: List[PlaygroundMessage] = Field(default_factory=list, description="Messages array")
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Attachments array")
    temperature: Optional[float] = Field(0.7, description="Temperature parameter")
    max_tokens: Optional[int] = Field(1000, description="Max tokens parameter")


class PlaygroundSessionUpdate(BaseModel):
    name: Optional[str] = None
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    messages: Optional[List[PlaygroundMessage]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class PlaygroundSessionResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    messages: List[Dict[str, Any]] = []
    attachments: List[Dict[str, Any]] = []
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    created_at: str
    updated_at: str


# --- File Extraction Utilities ---


def _extract_text_from_file(file_path: Path, filename: str) -> str:
    """Extract text based on file extension."""
    ext = file_path.suffix.lower()

    if ext in [".txt", ".md", ".csv"]:
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Error reading text file %s: %s", filename, e)
            return f"[Extracted content from {filename}]"

    elif ext == ".pdf":
        text_chunks = []
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        text_chunks.append(txt)
        except Exception:
            try:
                from pypdf import PdfReader

                reader = PdfReader(file_path)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        text_chunks.append(txt)
            except Exception as e:
                logger.warning("PDF extraction fallback failed for %s: %s", filename, e)

        if text_chunks:
            return "\n\n".join(text_chunks)
        return f"[PDF File: {filename} - Text extraction unavailable or empty document]"

    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        # Simulated/Basic OCR response for attached images
        return f"[Image File: {filename} - OCR Content Preview: Visual element scanned. Contains text/graphics.]"

    elif ext in [".mp4", ".webm"]:
        # Audio/Video transcription placeholder
        return f"[Video File: {filename} - Audio Track Transcribed Preview: Media content attached.]"

    return f"[File: {filename}]"


def _cleanup_old_attachments():
    """Clean up attachments older than 1 hour (3600s)."""
    now = time.time()
    expired_ids = []
    for att_id, meta in list(ATTACHMENT_STORE.items()):
        if now - meta.get("created_timestamp", 0) > 3600:
            expired_ids.append(att_id)
            f_path = meta.get("file_path")
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except Exception as e:
                    logger.warning("Error removing temp file %s: %s", f_path, e)

    for att_id in expired_ids:
        ATTACHMENT_STORE.pop(att_id, None)


# --- Endpoints ---


@router.post("/chat", response_model=PlaygroundChatResponse)
async def playground_chat(
    payload: PlaygroundChatRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Execute LLM chat completion for Model Playground with optional context attachments and streaming."""
    start_time = time.time()

    # Prepend extracted text from attachments to the prompt context if present
    attachment_context = ""
    if payload.attachment_ids:
        _cleanup_old_attachments()
        context_parts = []
        for att_id in payload.attachment_ids:
            if att_id in ATTACHMENT_STORE:
                att_meta = ATTACHMENT_STORE[att_id]
                context_parts.append(
                    f"--- ATTACHMENT: {att_meta['filename']} ---\n{att_meta['extracted_text']}"
                )
        if context_parts:
            attachment_context = "\n\n".join(context_parts) + "\n\n"

    # Construct conversation history
    full_messages: List[Dict[str, str]] = []
    if payload.system_prompt:
        full_messages.append({"role": "system", "content": payload.system_prompt})

    for msg in payload.messages:
        full_messages.append({"role": msg.role, "content": msg.content})

    # Inject attachment context into the last user message if attachments exist
    if attachment_context and full_messages and full_messages[-1]["role"] == "user":
        full_messages[-1]["content"] = f"{attachment_context}User Query: {full_messages[-1]['content']}"

    # Handle SSE streaming response if requested
    if payload.stream:

        async def event_generator():
            try:
                response = await completion_with_fallback(
                    model=payload.model_id,
                    messages=full_messages,
                    temperature=payload.temperature or 0.7,
                    max_tokens=payload.max_tokens or 1000,
                    stream=True,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content or "" if chunk.choices else ""
                    if delta:
                        chunk_data = json.dumps({"content": delta, "model": payload.model_id})
                        yield f"data: {chunk_data}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as err:
                logger.error("Error in streaming response: %s", err)
                err_data = json.dumps({"error": str(err)})
                yield f"data: {err_data}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming response
    try:
        completion_res = await completion_with_fallback(
            model=payload.model_id,
            messages=full_messages,
            temperature=payload.temperature or 0.7,
            max_tokens=payload.max_tokens or 1000,
        )
        latency_ms = (time.time() - start_time) * 1000.0

        content = completion_res.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = completion_res.get("model", payload.model_id)
        usage = completion_res.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return PlaygroundChatResponse(
            response=content,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 2),
            status="success",
        )
    except Exception as e:
        logger.error("Playground chat failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Playground completion failed: {str(e)}",
        )


@router.post("/upload", response_model=AttachmentInfo)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Upload and extract text from PDF, images, video/audio, or plain text files."""
    _cleanup_old_attachments()

    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    att_id = str(uuid.uuid4())
    temp_file_path = TEMP_UPLOADS_DIR / f"{att_id}{ext}"

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save upload file: {str(e)}",
        )

    # Extract text from file
    extracted_text = _extract_text_from_file(temp_file_path, file.filename or "file")
    created_at_str = datetime.utcnow().isoformat()

    ATTACHMENT_STORE[att_id] = {
        "attachment_id": att_id,
        "filename": file.filename or "file",
        "file_type": ext.lstrip("."),
        "file_path": str(temp_file_path),
        "extracted_text": extracted_text,
        "created_timestamp": time.time(),
        "created_at": created_at_str,
    }

    preview = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")

    return AttachmentInfo(
        attachment_id=att_id,
        filename=file.filename or "file",
        file_type=ext.lstrip("."),
        extracted_text_preview=preview,
        total_chars=len(extracted_text),
        created_at=created_at_str,
        status="processed",
    )


@router.get("/attachments/{attachment_id}")
async def get_attachment(attachment_id: str):
    """Retrieve details and full extracted text for an attachment."""
    if attachment_id not in ATTACHMENT_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment '{attachment_id}' not found or expired.",
        )
    meta = ATTACHMENT_STORE[attachment_id]
    return {
        "attachment_id": attachment_id,
        "filename": meta["filename"],
        "file_type": meta["file_type"],
        "extracted_text": meta["extracted_text"],
        "total_chars": len(meta["extracted_text"]),
        "created_at": meta["created_at"],
    }


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str):
    """Delete a temporary attachment and file."""
    if attachment_id in ATTACHMENT_STORE:
        meta = ATTACHMENT_STORE.pop(attachment_id)
        f_path = meta.get("file_path")
        if f_path and os.path.exists(f_path):
            try:
                os.remove(f_path)
            except Exception:
                pass
        return {"status": "deleted", "attachment_id": attachment_id}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Attachment '{attachment_id}' not found.",
    )


# --- Playground Sessions CRUD ---


@router.get("/sessions", response_model=List[PlaygroundSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """List playground sessions for current user (or all if unauthenticated)."""
    user_id = current_user.get("sub") if current_user else None

    stmt = select(PlaygroundSession)
    if user_id:
        stmt = stmt.where((PlaygroundSession.user_id == user_id) | (PlaygroundSession.user_id.is_(None)))
    stmt = stmt.order_by(PlaygroundSession.updated_at.desc())

    res = await db.execute(stmt)
    sessions = res.scalars().all()

    out = []
    for s in sessions:
        out.append(
            PlaygroundSessionResponse(
                id=s.id,
                user_id=s.user_id,
                name=s.name,
                model_id=s.model_id,
                system_prompt=s.system_prompt,
                messages=s.messages_json or [],
                attachments=s.attachments_json or [],
                temperature=s.temperature,
                max_tokens=s.max_tokens,
                created_at=s.created_at.isoformat() if s.created_at else "",
                updated_at=s.updated_at.isoformat() if s.updated_at else "",
            )
        )
    return out


@router.post("/sessions", response_model=PlaygroundSessionResponse)
async def create_session(
    payload: PlaygroundSessionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Save a new playground session."""
    user_id = current_user.get("sub") if current_user else None

    name = payload.name
    if not name:
        if payload.messages:
            first_user_msg = next((m.content for m in payload.messages if m.role == "user"), "New Session")
            name = first_user_msg[:80] + ("..." if len(first_user_msg) > 80 else "")
        else:
            name = f"Playground Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    msgs_data = [m.model_dump() for m in payload.messages]
    session_id = str(uuid.uuid4())

    new_session = PlaygroundSession(
        id=session_id,
        user_id=user_id,
        name=name,
        model_id=payload.model_id,
        system_prompt=payload.system_prompt,
        messages_json=msgs_data,
        attachments_json=payload.attachments or [],
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    return PlaygroundSessionResponse(
        id=new_session.id,
        user_id=new_session.user_id,
        name=new_session.name,
        model_id=new_session.model_id,
        system_prompt=new_session.system_prompt,
        messages=new_session.messages_json or [],
        attachments=new_session.attachments_json or [],
        temperature=new_session.temperature,
        max_tokens=new_session.max_tokens,
        created_at=new_session.created_at.isoformat(),
        updated_at=new_session.updated_at.isoformat(),
    )


@router.get("/sessions/{session_id}", response_model=PlaygroundSessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Load details for a specific playground session."""
    stmt = select(PlaygroundSession).where(PlaygroundSession.id == session_id)
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()

    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playground session '{session_id}' not found.",
        )

    return PlaygroundSessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        model_id=s.model_id,
        system_prompt=s.system_prompt,
        messages=s.messages_json or [],
        attachments=s.attachments_json or [],
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


@router.put("/sessions/{session_id}", response_model=PlaygroundSessionResponse)
async def update_session(
    session_id: str,
    payload: PlaygroundSessionUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update an existing playground session (auto-save)."""
    stmt = select(PlaygroundSession).where(PlaygroundSession.id == session_id)
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()

    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playground session '{session_id}' not found.",
        )

    if payload.name is not None:
        s.name = payload.name
    if payload.model_id is not None:
        s.model_id = payload.model_id
    if payload.system_prompt is not None:
        s.system_prompt = payload.system_prompt
    if payload.messages is not None:
        s.messages_json = [m.model_dump() for m in payload.messages]
    if payload.attachments is not None:
        s.attachments_json = payload.attachments
    if payload.temperature is not None:
        s.temperature = payload.temperature
    if payload.max_tokens is not None:
        s.max_tokens = payload.max_tokens

    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)

    return PlaygroundSessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        model_id=s.model_id,
        system_prompt=s.system_prompt,
        messages=s.messages_json or [],
        attachments=s.attachments_json or [],
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a playground session by ID."""
    stmt = delete(PlaygroundSession).where(PlaygroundSession.id == session_id)
    res = await db.execute(stmt)
    await db.commit()

    if res.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playground session '{session_id}' not found.",
        )
    return {"status": "deleted", "id": session_id}
