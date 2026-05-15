"""
routers/documents.py
--------------------
Doküman yükleme ve metin gönderme endpoint'leri.

POST /api/upload  — PDF veya DOCX dosyası yükle
POST /api/text    — Manuel metin gir
GET  /api/documents       — Tüm dokümanları listele
GET  /api/documents/{id}  — Tek doküman getir (kartları dahil)
DELETE /api/documents/{id} — Dokümanı sil
"""

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from database import get_db
from models   import Document
from schemas  import (
    DocumentTextCreate, DocumentResponse, DocumentSummary, MessageResponse
)
from config import settings

# data_processing modülleri (bir sonraki aşamada doldurulacak)
from data_processing.pdf_reader   import extract_text_from_pdf
from data_processing.docx_reader  import extract_text_from_docx
from data_processing.text_cleaner import clean_text

router = APIRouter()

_CHUNK_SIZE = 1024 * 1024
_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def _safe_original_name(filename: str | None) -> str:
    name = Path(filename or "upload").name.strip()
    return name or "upload"


def _build_stored_filename(filename: str) -> str:
    original = _safe_original_name(filename)
    ext = _get_extension(original)
    stem = Path(original).stem[:80] or "upload"
    safe_stem = _SAFE_FILENAME_PATTERN.sub("_", stem).strip("._") or "upload"
    suffix = f".{ext}" if ext else ""
    return f"{safe_stem}_{uuid4().hex[:12]}{suffix}"


def _save_upload(upload_file: UploadFile, stored_filename: str) -> Path:
    upload_dir = settings.UPLOAD_DIR.resolve()
    dest = (upload_dir / stored_filename).resolve()
    if upload_dir not in dest.parents:
        raise HTTPException(status_code=400, detail="Geçersiz dosya adı.")

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    written = 0
    with dest.open("wb") as f:
        while True:
            chunk = upload_file.file.read(_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Dosya çok büyük. Maksimum boyut: {settings.MAX_FILE_SIZE_MB} MB.",
                )
            f.write(chunk)
    return dest


def _delete_uploaded_file(filename: str) -> None:
    upload_dir = settings.UPLOAD_DIR.resolve()
    file_path = (upload_dir / Path(filename).name).resolve()
    if upload_dir in file_path.parents:
        file_path.unlink(missing_ok=True)


# ── POST /api/upload ──────────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=DocumentSummary,
    status_code=status.HTTP_201_CREATED,
    summary="PDF veya DOCX dosyası yükle",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF veya DOCX dosyası"),
    title: str = Form(default="", description="Belge başlığı (opsiyonel)"),
    db: Session = Depends(get_db),
):
    original_filename = _safe_original_name(file.filename)
    ext = _get_extension(original_filename)
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya türü: .{ext}. İzin verilenler: {settings.ALLOWED_EXTENSIONS}",
        )

    # Dosyayı kaydet
    stored_filename = _build_stored_filename(original_filename)
    saved_path = _save_upload(file, stored_filename)

    # Metni çıkar
    try:
        if ext == "pdf":
            raw_text = extract_text_from_pdf(str(saved_path))
            source_type = "pdf"
        elif ext == "docx":
            raw_text = extract_text_from_docx(str(saved_path))
            source_type = "docx"
        else:
            raw_text = saved_path.read_text(encoding="utf-8", errors="ignore")
            source_type = "text"
    except Exception as e:
        saved_path.unlink(missing_ok=True)       # Hatalı dosyayı sil
        raise HTTPException(status_code=422, detail=f"Dosya okunamadı: {str(e)}")

    if not raw_text.strip():
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Dosyadan metin çıkarılamadı.")

    # Metni temizle
    cleaned = clean_text(raw_text)

    # Veritabanına kaydet
    doc = Document(
        title=title or original_filename,
        source_type=source_type,
        filename=stored_filename,
        raw_text=raw_text,
        clean_text=cleaned,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc


# ── POST /api/text ─────────────────────────────────────────────────────────────
@router.post(
    "/text",
    response_model=DocumentSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Manuel metin gönder",
)
async def submit_text(
    payload: DocumentTextCreate,
    db: Session = Depends(get_db),
):
    cleaned = clean_text(payload.text)

    doc = Document(
        title=payload.title,
        source_type="text",
        filename=None,
        raw_text=payload.text,
        clean_text=cleaned,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc


# ── GET /api/documents ─────────────────────────────────────────────────────────
@router.get(
    "/documents",
    response_model=list[DocumentSummary],
    summary="Tüm dokümanları listele",
)
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


# ── GET /api/documents/{id} ────────────────────────────────────────────────────
@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Doküman detayını getir (kartlar dahil)",
)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doküman bulunamadı.")
    return doc


# ── DELETE /api/documents/{id} ─────────────────────────────────────────────────
@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
    summary="Dokümanı ve kartlarını sil",
)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doküman bulunamadı.")

    # Yükleme dosyasını da sil (varsa)
    if doc.filename:
        _delete_uploaded_file(doc.filename)

    db.delete(doc)
    db.commit()
    return {"message": f"'{doc.title}' silindi.", "success": True}
