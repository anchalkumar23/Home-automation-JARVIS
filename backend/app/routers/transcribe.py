from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.schemas import TranscribeResponse

router = APIRouter(prefix="/api", tags=["transcribe"])


def build_multipart_body(
    filename: str, file_bytes: bytes, content_type: str, model: str
) -> tuple[bytes, str]:
    """Build a multipart/form-data body for Groq's audio transcription endpoint."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe_with_groq(
    api_key: str, model: str, filename: str, file_bytes: bytes, content_type: str
) -> str:
    body, content_type_header = build_multipart_body(filename, file_bytes, content_type, model)
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type_header,
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq transcription HTTP {exc.code}: {body_text}") from exc
    except Exception as exc:
        raise RuntimeError(f"Groq transcription request failed: {exc}") from exc

    return str(payload.get("text", ""))


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: Request, audio: UploadFile = File(...)) -> TranscribeResponse:
    settings = request.app.state.settings
    if not settings.groq_api_key:
        raise HTTPException(status_code=400, detail="Voice transcription requires a Groq API key.")

    file_bytes = await audio.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="No audio data received.")

    try:
        text = transcribe_with_groq(
            settings.groq_api_key,
            settings.groq_whisper_model,
            audio.filename or "recording.webm",
            file_bytes,
            audio.content_type or "audio/webm",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TranscribeResponse(text=text.strip())
