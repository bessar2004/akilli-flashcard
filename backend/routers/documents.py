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

import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from database import get_db
from models   import Document, Flashcard
from schemas  import (
    DocumentTextCreate, DocumentResponse, DocumentSummary, MessageResponse
)
from config import settings

# data_processing modülleri (bir sonraki aşamada doldurulacak)
from data_processing.pdf_reader   import extract_text_from_pdf
from data_processing.docx_reader  import extract_text_from_docx
from data_processing.text_cleaner import clean_text

router = APIRouter()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def _save_upload(upload_file: UploadFile) -> Path:
    """Yüklenen dosyayı uploads/ klasörüne kaydeder, Path döndürür."""
    dest = settings.UPLOAD_DIR / upload_file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return dest


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
    ext = _get_extension(file.filename)
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya türü: .{ext}. İzin verilenler: {settings.ALLOWED_EXTENSIONS}",
        )

    # Dosyayı kaydet
    saved_path = _save_upload(file)

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
        title=title or file.filename,
        source_type=source_type,
        filename=file.filename,
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
        file_path = settings.UPLOAD_DIR / doc.filename
        file_path.unlink(missing_ok=True)

    db.delete(doc)
    db.commit()
    return {"message": f"'{doc.title}' silindi.", "success": True}
