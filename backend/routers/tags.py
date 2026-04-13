"""
routers/tags.py
---------------
Etiket yönetimi endpoint'leri.

GET    /api/tags        — Tüm etiketleri listele
POST   /api/tags        — Yeni etiket oluştur
DELETE /api/tags/{id}   — Etiketi sil
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models   import Tag
from schemas  import TagCreate, TagResponse, MessageResponse

router = APIRouter()


# ── GET /api/tags ─────────────────────────────────────────────────────────────
@router.get(
    "/tags",
    response_model=list[TagResponse],
    summary="Tüm etiketleri listele",
)
def list_tags(db: Session = Depends(get_db)):
    return db.query(Tag).order_by(Tag.name).all()


# ── POST /api/tags ────────────────────────────────────────────────────────────
@router.post(
    "/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni etiket oluştur",
)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    name = payload.name.strip().lower()
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"'{name}' etiketi zaten mevcut.")

    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


# ── DELETE /api/tags/{id} ─────────────────────────────────────────────────────
@router.delete(
    "/tags/{tag_id}",
    response_model=MessageResponse,
    summary="Etiketi sil",
)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Etiket bulunamadı.")
    db.delete(tag)
    db.commit()
    return {"message": f"Etiket '{tag.name}' silindi.", "success": True}
