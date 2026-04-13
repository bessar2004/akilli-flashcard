"""
schemas.py
----------
Pydantic şemaları (veri doğrulama ve serileştirme).

FastAPI, HTTP istek/yanıtlarını bu şemalar üzerinden doğrular.
Üç katman:
  - Base    : Temel alanlar
  - Create  : POST gövdesi (giriş)
  - Response: API yanıtı (çıkış)
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
import json


# ═══════════════════════════════════════════════════════════════════════════════
#  TAG
# ═══════════════════════════════════════════════════════════════════════════════

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, examples=["biyoloji"])


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
#  FLASHCARD
# ═══════════════════════════════════════════════════════════════════════════════

class FlashcardBase(BaseModel):
    question:   str  = Field(...,  min_length=5,  examples=["Fotosentez nedir?"])
    answer:     str  = Field(...,  min_length=1,  examples=["Bitkilerin güneş ışığını besin maddesine dönüştürme işlemi."])
    card_type:  str  = Field("qa", pattern="^(qa|mcq)$",  examples=["qa"])
    difficulty: str  = Field("medium", pattern="^(easy|medium|hard)$")
    topic:      Optional[str]  = Field(None, max_length=100)
    options:    Optional[str]  = None    # JSON string
    correct_idx: Optional[int] = None   # 0-3


class FlashcardCreate(FlashcardBase):
    document_id: int
    tag_names:   list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mcq_fields(self):
        """MCQ tipinde options ve correct_idx zorunludur."""
        if self.card_type == "mcq":
            if self.options is None or self.correct_idx is None:
                raise ValueError("MCQ kartları için 'options' ve 'correct_idx' gereklidir.")
        return self


class FlashcardUpdate(BaseModel):
    """Kısmi güncelleme — tüm alanlar opsiyonel."""
    question:    Optional[str]  = Field(None, min_length=5)
    answer:      Optional[str]  = Field(None, min_length=1)
    card_type:   Optional[str]  = Field(None, pattern="^(qa|mcq)$")
    difficulty:  Optional[str]  = Field(None, pattern="^(easy|medium|hard)$")
    topic:       Optional[str]  = Field(None, max_length=100)
    options:     Optional[str]  = None
    correct_idx: Optional[int]  = None
    is_approved: Optional[bool] = None
    tag_names:   Optional[list[str]] = None


class FlashcardResponse(FlashcardBase):
    id:               int
    document_id:      int
    score:            float
    is_duplicate:     bool
    is_approved:      bool
    correct_count:    int
    incorrect_count:  int
    last_reviewed_at: Optional[datetime]
    next_review_at:   Optional[datetime] # SRS
    interval:         int                # SRS
    repetitions:      int                # SRS
    easiness_factor:  float              # SRS
    created_at:       datetime
    updated_at:       datetime
    tags:             list[TagResponse] = []

    # options alanını (JSON string) listeye dönüştür
    @model_validator(mode="after")
    def parse_options(self):
        if isinstance(self.options, str):
            try:
                self.options = json.loads(self.options)
            except (json.JSONDecodeError, TypeError):
                pass
        return self

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentBase(BaseModel):
    title:       str = Field("Adsız Belge", max_length=255)
    source_type: str = Field(..., pattern="^(pdf|docx|text)$")


class DocumentTextCreate(BaseModel):
    """Manuel metin girişi için istek gövdesi."""
    title: str = Field("Manuel Metin", max_length=255)
    text:  str = Field(..., min_length=20,
                       description="En az 20 karakter metin giriniz.")


class DocumentResponse(DocumentBase):
    id:         int
    filename:   Optional[str]
    card_count: int
    created_at: datetime
    updated_at: datetime
    flashcards: list[FlashcardResponse] = []

    model_config = {"from_attributes": True}


class DocumentSummary(BaseModel):
    """Listelemelerde kullanılan hafif yanıt şeması (kartlar dahil değil)."""
    id:          int
    title:       str
    source_type: str
    filename:    Optional[str]
    card_count:  int
    created_at:  datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERATE (Flashcard Üretim İsteği)
# ═══════════════════════════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    document_id:    int
    max_cards:      int  = Field(20, ge=1,  le=50)
    include_mcq:    bool = True    # Çoktan seçmeli kart üret
    include_qa:     bool = True    # Klasik Q&A üret
    difficulty:     Optional[str] = Field(None, pattern="^(easy|medium|hard)$")


class GenerateResponse(BaseModel):
    document_id: int
    total_generated: int
    flashcards: list[FlashcardResponse]


# ═══════════════════════════════════════════════════════════════════════════════
#  REVIEW (Tekrar Sistemi — Skor Güncelleme)
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewRequest(BaseModel):
    flashcard_id: int
    was_correct:  bool   # Kullanıcı doğru cevaplayabildi mi?


class ReviewResponse(BaseModel):
    flashcard_id:    int
    correct_count:   int
    incorrect_count: int
    accuracy:        float   # Doğruluk oranı: 0.0 – 1.0
    next_review_at:  Optional[str] = None
    interval:        Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  GENEL API YANITI
# ═══════════════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    """Basit mesaj yanıtı (silme, hata vb. için)."""
    message: str
    success: bool = True
