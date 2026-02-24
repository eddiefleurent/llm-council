"""File upload validation and content extraction for prompt attachments."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_EXTRACTED_CHARS = 30_000
TRUNCATION_SUFFIX = "\n\n[File content truncated due to size limits.]"

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".json", ".csv"}
SUPPORTED_TYPES_DISPLAY = ", ".join(sorted(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS))


class AttachmentPayload(BaseModel):
    """Sanitized attachment payload that can be included in message context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(gt=0, le=MAX_FILE_SIZE_BYTES)
    extracted_text: str = Field(min_length=1, max_length=MAX_EXTRACTED_CHARS)


def _get_extension(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _trim_extracted_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if len(stripped) <= MAX_EXTRACTED_CHARS:
        return stripped

    remaining = MAX_EXTRACTED_CHARS - len(TRUNCATION_SUFFIX)
    if remaining <= 0:
        return TRUNCATION_SUFFIX[:MAX_EXTRACTED_CHARS]
    return stripped[:remaining].rstrip() + TRUNCATION_SUFFIX


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    size = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large (max {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB).",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return data


def _extract_text_from_textlike(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _extract_text_from_json(data: bytes) -> str:
    try:
        parsed = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="JSON file must be UTF-8 encoded."
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON file.") from exc
    return json.dumps(parsed, indent=2, ensure_ascii=False)


def _extract_text_from_csv(data: bytes) -> str:
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="CSV file must be UTF-8 encoded."
        ) from exc

    try:
        reader = csv.reader(io.StringIO(decoded))
        rows = [", ".join(row) for row in reader]
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail="Invalid CSV file.") from exc

    return "\n".join(rows)


def _extract_text_from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=500, detail="PDF support is not available on this server."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid PDF file.") from exc

    pages: list[str] = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    return "\n\n".join(page for page in pages if page)


async def extract_attachment_payload(upload: UploadFile) -> AttachmentPayload:
    """Validate and extract text from an uploaded attachment."""
    extension = _get_extension(upload.filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type. Supported types: {SUPPORTED_TYPES_DISPLAY}. "
                "Please upload a txt, md, pdf, json, or csv file."
            ),
        )

    data = await _read_upload_bytes(upload)

    if extension in {".txt", ".md"}:
        extracted = _extract_text_from_textlike(data)
    elif extension == ".json":
        extracted = _extract_text_from_json(data)
    elif extension == ".csv":
        extracted = _extract_text_from_csv(data)
    else:
        extracted = _extract_text_from_pdf(data)

    trimmed = _trim_extracted_text(extracted)
    if not trimmed:
        raise HTTPException(
            status_code=400,
            detail="Could not extract readable text from the uploaded file.",
        )

    return AttachmentPayload(
        filename=upload.filename or "attachment",
        content_type=upload.content_type or "application/octet-stream",
        size_bytes=len(data),
        extracted_text=trimmed,
    )


def build_attachment_context_block(attachment: AttachmentPayload) -> str:
    """Format attachment content for prompt context."""
    return (
        f"[Attached file: {attachment.filename} "
        f"({attachment.content_type}, {attachment.size_bytes} bytes)]\n"
        f"{attachment.extracted_text}"
    )
