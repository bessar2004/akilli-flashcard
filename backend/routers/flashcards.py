"""
routers/flashcards.py
---------------------
Flashcard CRUD ve üretim endpoint'leri.

POST   /api/generate               — Doküman için flashcard üret (LLM öncelikli)
GET    /api/flashcards             — Kartları listele (filtre desteği)
GET    /api/flashcards/{id}        — Tek kart getir
PUT    /api/flashcards/{id}        — Kartı güncelle
DELETE /api/flashcards/{id}        — Kartı sil
POST   /api/flashcards/{id}/review — Tekrar sistemi: doğru/yanlış kaydet
GET    /api/llm/status             — Ollama bağlantı durumu
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models   import Document, Flashcard, Tag
from schemas  import (
    GenerateRequest, GenerateResponse,
    FlashcardUpdate, FlashcardResponse,
    ReviewRequest, ReviewResponse,
    MessageResponse,
)

# ── LLM Entegrasyonu (birincil) ───────────────────────────────────────────────
from llm.llm_generator  import generate_with_llm
from llm.ollama_client  import default_client
from routers.quiz       import _clean_option_text

# ── NLP Motoru (fallback — silinmedi) ────────────────────────────────────────
from question_generator.difficulty_classifier import classify_difficulty

router = APIRouter()


# ── Yardımcı: Tag'leri bul veya oluştur ──────────────────────────────────────
def _get_or_create_tags(tag_names: list[str], db: Session) -> list[Tag]:
    tags = []
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()   # id al ama commit etme
        tags.append(tag)
    return tags


# ── GET /api/llm/status ──────────────────────────────────────────────────────
@router.get(
    "/llm/status",
    summary="Ollama LLM bağlantı durumunu kontrol et",
)
def llm_status():
    """
    Ollama'nın çalışıp çalışmadığını ve yapılandırılmış modelin
    yüklü olup olmadığını döndürür.
    """
    available = default_client.is_available()
    models    = default_client.list_models()
    return {
        "ollama_available": available,
        "configured_model": default_client.model,
        "base_url":         default_client.base_url,
        "installed_models": models,
        "mode":             "llm" if available else "nlp_fallback",
    }


# ── POST /api/generate ────────────────────────────────────────────────────────
@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Belge için flashcard üret (Ollama LLM öncelikli, NLP fallback)",
)
def generate_flashcards(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Flashcard üretim akışı:
      1. Ollama erişilebilirse → LLM ile üretim (gemma3:1b)
      2. Ollama kapalıysa      → NLP pipeline ile üretim (NLTK)
    """
    # Dokümanı getir
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doküman bulunamadı.")

    text = doc.clean_text or doc.raw_text
    if not text.strip():
        raise HTTPException(status_code=422, detail="Doküman metni boş.")

    # ── LLM / NLP üretim çağrısı (fallback llm_generator içinde) ─────────────
    raw_cards = generate_with_llm(
        text=text,
        max_cards=payload.max_cards,
        include_qa=payload.include_qa,
        include_mcq=payload.include_mcq,
    )

    created_cards: list[Flashcard] = []
    seen_in_batch = set()

    for item in raw_cards:
        # Zorluk filtresi
        difficulty = item.get("difficulty") or classify_difficulty(item.get("answer", ""))
        if payload.difficulty and difficulty != payload.difficulty:
            continue

        card_type = item.get("type", "qa")

        # MCQ seçeneklerini JSON string'e dönüştür
        options_json = None
        if card_type == "mcq" and isinstance(item.get("options"), list):
            cleaned_opts = [_clean_option_text(o) for o in item["options"]]
            options_json = json.dumps(cleaned_opts, ensure_ascii=False)

        # ── Akıllı Tekilleştirme (Smart Deduplication) ─────────────────────────
        q_text = str(item.get("question", "")).strip()
        
        # 1. Bu istek içinde daha önce eklendi mi?
        already_seen = q_text.lower() in seen_in_batch
        
        # 2. Veritabanında (daha önceki isteklerde) var mı?
        existing = db.query(Flashcard).filter(
            Flashcard.document_id == payload.document_id,
            Flashcard.question == q_text
        ).first()
        
        is_duplicate = item.get("is_duplicate", False) or already_seen or (existing is not None)
        # ───────────────────────────────────────────────────────────────────

        card = Flashcard(
            document_id  = payload.document_id,
            question     = q_text,
            answer       = item.get("answer", ""),
            card_type    = card_type,
            difficulty   = difficulty,
            score        = item.get("score", 0.8),
            topic        = item.get("topic"),
            options      = options_json,
            correct_idx  = item.get("correct_idx"),
            is_duplicate = is_duplicate,
        )
        db.add(card)
        created_cards.append(card)
        
        # Soru temizse sete ekle
        if not is_duplicate:
            seen_in_batch.add(q_text.lower())

    db.flush()

    # Dokümanın kart sayısını güncelle
    doc.card_count = db.query(Flashcard).filter(
        Flashcard.document_id == payload.document_id,
        Flashcard.is_duplicate.is_(False),
    ).count()

    db.commit()
    for c in created_cards:
        db.refresh(c)

    return GenerateResponse(
        document_id=payload.document_id,
        total_generated=len(created_cards),
        flashcards=created_cards,
    )


# ── GET /api/flashcards ───────────────────────────────────────────────────────
@router.get(
    "/flashcards",
    response_model=list[FlashcardResponse],
    summary="Flashcard'ları listele (filtre desteğiyle)",
)
def list_flashcards(
    document_id: Optional[int]  = Query(None, description="Belge ID filtresi"),
    difficulty:  Optional[str]  = Query(None, pattern="^(easy|medium|hard)$"),
    card_type:   Optional[str]  = Query(None, pattern="^(qa|mcq)$"),
    tag:         Optional[str]  = Query(None, description="Etiket adı filtresi"),
    due_only:    bool           = Query(False, description="Yalnızca çalışma zamanı gelenleri getir"),
    skip: int = Query(0,  ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Flashcard).filter(Flashcard.is_duplicate.is_(False))

    if due_only:
        # Gece yarısına kadar olanları (bugün dahil) getir
        q = q.filter(Flashcard.next_review_at <= datetime.utcnow())

    if document_id:
        q = q.filter(Flashcard.document_id == document_id)
    if difficulty:
        q = q.filter(Flashcard.difficulty == difficulty)
    if card_type:
        q = q.filter(Flashcard.card_type == card_type)
    if tag:
        q = q.join(Flashcard.tags).filter(Tag.name == tag.lower())

    return q.order_by(Flashcard.score.desc()).offset(skip).limit(limit).all()


# ── GET /api/flashcards/{id} ──────────────────────────────────────────────────
@router.get(
    "/flashcards/{flashcard_id}",
    response_model=FlashcardResponse,
    summary="Tek flashcard getir",
)
def get_flashcard(flashcard_id: int, db: Session = Depends(get_db)):
    card = db.get(Flashcard, flashcard_id)
    if not card:
        raise HTTPException(status_code=404, detail="Kart bulunamadı.")
    return card


# ── PUT /api/flashcards/{id} ──────────────────────────────────────────────────
@router.put(
    "/flashcards/{flashcard_id}",
    response_model=FlashcardResponse,
    summary="Flashcard güncelle",
)
def update_flashcard(
    flashcard_id: int,
    payload: FlashcardUpdate,
    db: Session = Depends(get_db),
):
    card = db.get(Flashcard, flashcard_id)
    if not card:
        raise HTTPException(status_code=404, detail="Kart bulunamadı.")

    # Gelen alanları güncelle (None olanları atla)
    update_data = payload.model_dump(exclude_unset=True)
    tag_names = update_data.pop("tag_names", None)

    for field, value in update_data.items():
        setattr(card, field, value)

    if tag_names is not None:
        card.tags = _get_or_create_tags(tag_names, db)

    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return card


# ── DELETE /api/flashcards/{id} ───────────────────────────────────────────────
@router.delete(
    "/flashcards/{flashcard_id}",
    response_model=MessageResponse,
    summary="Flashcard sil",
)
def delete_flashcard(flashcard_id: int, db: Session = Depends(get_db)):
    card = db.get(Flashcard, flashcard_id)
    if not card:
        raise HTTPException(status_code=404, detail="Kart bulunamadı.")
    db.delete(card)
    db.commit()
    return {"message": f"Kart #{flashcard_id} silindi.", "success": True}


# ── POST /api/flashcards/{id}/review ─────────────────────────────────────────
@router.post(
    "/flashcards/{flashcard_id}/review",
    response_model=ReviewResponse,
    summary="Tekrar sistemine doğru/yanlış kaydet",
)
def review_flashcard(
    flashcard_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
):
    card = db.get(Flashcard, flashcard_id)
    if not card:
        raise HTTPException(status_code=404, detail="Kart bulunamadı.")

    if payload.was_correct:
        card.correct_count += 1
        # SM-2: Başarılı tekrar (Kalite 4 olarak varsayalım)
        quality = 4
        card.repetitions += 1
        
        if card.repetitions == 1:
            card.interval = 1
        elif card.repetitions == 2:
            card.interval = 6
        else:
            card.interval = int(round(card.interval * card.easiness_factor))
            
        # EF Güncelleme (Basitleştirilmiş SM-2)
        card.easiness_factor = max(1.3, card.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    else:
        card.incorrect_count += 1
        # SM-2: Başarısız tekrar (Kalite 0)
        card.repetitions = 0
        card.interval = 0  # Yarın tekrar et
        card.easiness_factor = max(1.3, card.easiness_factor - 0.2)

    card.last_reviewed_at = datetime.utcnow()
    # Bir sonraki tekrar zamanı: Şimdi + Interval gün
    card.next_review_at = card.last_reviewed_at + timedelta(days=card.interval)
    
    db.commit()
    db.refresh(card)

    total = card.correct_count + card.incorrect_count
    accuracy = card.correct_count / total if total > 0 else 0.0

    return ReviewResponse(
        flashcard_id=card.id,
        correct_count=card.correct_count,
        incorrect_count=card.incorrect_count,
        accuracy=round(accuracy, 3),
        next_review_at=card.next_review_at.isoformat() if card.next_review_at else None,
        interval=card.interval
    )
