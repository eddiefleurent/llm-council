"""Unit tests for file attachment ingestion."""

import io
import sys
import types

import pytest
from fastapi import HTTPException, UploadFile

from backend.file_ingestion import MAX_FILE_SIZE_BYTES, extract_attachment_payload


def _make_upload(filename: str, data: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data), headers=None)


@pytest.mark.asyncio
async def test_extract_text_file_success():
    upload = _make_upload("notes.txt", b"Hello council")
    payload = await extract_attachment_payload(upload)
    assert payload.filename == "notes.txt"
    assert payload.extracted_text == "Hello council"


@pytest.mark.asyncio
async def test_extract_json_file_success():
    upload = _make_upload("data.json", b'{"k": "v"}')
    payload = await extract_attachment_payload(upload)
    assert '"k": "v"' in payload.extracted_text


@pytest.mark.asyncio
async def test_extract_csv_file_success():
    upload = _make_upload("sheet.csv", b"a,b\n1,2\n")
    payload = await extract_attachment_payload(upload)
    assert payload.extracted_text == "a, b\n1, 2"


@pytest.mark.asyncio
async def test_extract_pdf_file_success_with_mocked_reader(monkeypatch):
    class _FakePage:
        def extract_text(self):
            return "Page text"

    class _FakeReader:
        def __init__(self, _stream):
            self.pages = [_FakePage()]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=_FakeReader))
    upload = _make_upload("file.pdf", b"%PDF-1.4 fake")
    payload = await extract_attachment_payload(upload)
    assert payload.extracted_text == "Page text"


@pytest.mark.asyncio
async def test_extract_rejects_unsupported_extension():
    upload = _make_upload("archive.zip", b"PK\x03\x04")
    with pytest.raises(HTTPException, match="Unsupported file type"):
        await extract_attachment_payload(upload)


@pytest.mark.asyncio
async def test_extract_rejects_oversized_file():
    upload = _make_upload("big.txt", b"a" * (MAX_FILE_SIZE_BYTES + 1))
    with pytest.raises(HTTPException, match="too large"):
        await extract_attachment_payload(upload)


@pytest.mark.asyncio
async def test_extract_rejects_invalid_json():
    upload = _make_upload("broken.json", b"{bad")
    with pytest.raises(HTTPException, match="Invalid JSON"):
        await extract_attachment_payload(upload)
