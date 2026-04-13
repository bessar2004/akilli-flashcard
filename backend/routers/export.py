"""
routers/export.py
-----------------
Kartları dışa aktarma (Anki) endpoint'leri.
"""

import io
from fastapi import APIRouter, Depends, HTTPException, responses
from sqlalchemy.orm import Session

from database import get_db
from models   import Document, Flashcard

router = APIRouter()

# ── Export ──────────────────────────────────────────────────
@router.get("/export/anki/{document_id}")
def export_anki(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doküman bulunamadı.")

    cards = db.query(Flashcard).filter(
        Flashcard.document_id == document_id,
        Flashcard.is_duplicate.is_(False),
        Flashcard.is_approved.is_(True)
    ).all()

    # TSV İçeriği: Soru [TAB] Cevap [TAB] Etiketler
    output = io.StringIO()
    # UTF-8 BOM ekle (Anki/Excel için)
    output.write('\ufeff')
    
    for card in cards:
        q = card.question.replace("\n", " ")
        a = card.answer.replace("\n", " ")
        tags = ",".join([t.name for t in card.tags]) if card.tags else doc.title
        output.write(f"{q}\t{a}\t{tags}\n")

    content = output.getvalue().encode("utf-8")
    output.close()

    return responses.Response(
        content=content,
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f"attachment; filename=anki_export_{document_id}.txt"}
    )
