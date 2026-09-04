from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import DATA_DIR
from app.schemas import UploadResponse

router = APIRouter(prefix="/api", tags=["uploads"])

UPLOADS_DIR = DATA_DIR / "uploads"


@router.post("/uploads", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}-{Path(file.filename).name}"
    destination = UPLOADS_DIR / safe_name

    with destination.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            out_file.write(chunk)

    return UploadResponse(file_path=str(destination), file_name=file.filename)
