"""
models.py
---------
SQLAlchemy ORM modelleri.
Her sınıf bir veritabanı tablosunu temsil eder.

Tablolar:
  - documents  : Yüklenen belgeler
  - flashcards : Üretilen soru-cevap kartları
  - tags       : Konu etiketleri
  - flashcard_tags : Kart ↔ Etiket bağlantı tablosu (M2M)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Float, ForeignKey, Table,
)
from sqlalchemy.orm import relationship

from database import Base


# ── Ara Tablo: Flashcard ↔ Tag (Çoka-Çok İlişki) ─────────────────────────────
flashcard_tags = Table(
    "flashcard_tags",
    Base.metadata,
    Column("flashcard_id", Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",       Integer, ForeignKey("tags.id",       ondelete="CASCADE"), primary_key=True),
)


# ── Document (Belge) ──────────────────────────────────────────────────────────
class Document(Base):
    """
    Kullanıcının yüklediği/girdiği belgeyi saklar.
    Ham metin ve meta veriler burada tutulur.
    """
    __tablename__ = "documents"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(255), nullable=False, default="Adsız Belge")

    # Kaynak türü: "pdf" | "docx" | "text"
    source_type = Column(String(20),  nullable=False)

    # Yüklenen dosyanın orijinal adı (metin girişinde None)
    filename    = Column(String(255), nullable=True)

    # Çıkarılan ham metin
    raw_text    = Column(Text, nullable=False)

    # İşlenmiş / temizlenmiş metin
    clean_text  = Column(Text, nullable=True)

    # Toplam üretilen kart sayısı
    card_count  = Column(Integer, default=0)

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişkiler
    flashcards  = relationship("Flashcard", back_populates="document",
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document id={self.id} title='{self.title}' source={self.source_type}>"


# ── Flashcard (Bilgi Kartı) ───────────────────────────────────────────────────
class Flashcard(Base):
    """
    Tek bir soru-cevap kartını temsil eder.
    QA (klasik) veya MCQ (çoktan seçmeli) tipinde olabilir.
    """
    __tablename__ = "flashcards"

    id          = Column(Integer, primary_key=True, index=True)

    # Hangi belgeye ait
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)

    # Kart içeriği
    question    = Column(Text, nullable=False)
    answer      = Column(Text, nullable=False)

    # Kart türü: "qa" | "mcq"
    card_type   = Column(String(10), nullable=False, default="qa")

    # Çoktan seçmeli seçenekler (JSON string olarak saklanır)
    # Örnek: '["A) Opsiyonu", "B) Opsiyonu", "C) Opsiyonu", "D) Cevap"]'
    options     = Column(Text, nullable=True)

    # Doğru seçenek indeksi (MCQ için 0-3 arası)
    correct_idx = Column(Integer, nullable=True)

    # Zorluk seviyesi: "easy" | "medium" | "hard"
    difficulty  = Column(String(10), nullable=False, default="medium")

    # NLP puanı (cümle önem skoru — 0.0 – 1.0)
    score       = Column(Float, default=0.0)

    # İçerik konu başlığı / kategori bilgisi
    topic       = Column(String(100), nullable=True)

    # Tekrar eden kart mı? (otomatik tespit)
    is_duplicate = Column(Boolean, default=False)

    # Kullanıcı tarafından onaylandı mı?
    is_approved  = Column(Boolean, default=True)

    # Tekrar sistemi için: doğru/yanlış cevap sayıları
    correct_count   = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)

    # Son çalışma zamanı
    last_reviewed_at = Column(DateTime, nullable=True)

    # ── Spaced Repetition (SRS) - SM-2 Algoritması ───────────────────────────
    easiness_factor  = Column(Float,    default=2.5)   # EF (Başlangıç: 2.5)
    interval         = Column(Integer,  default=0)     # Gün cinsinden aralık
    repetitions      = Column(Integer,  default=0)     # Başarılı üst üste tekrar
    next_review_at   = Column(DateTime, default=datetime.utcnow, index=True)
    # ────────────────────────────────────────────────────────────────────────

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişkiler
    document    = relationship("Document", back_populates="flashcards")
    tags        = relationship("Tag", secondary=flashcard_tags, back_populates="flashcards")

    def __repr__(self):
        return f"<Flashcard id={self.id} type={self.card_type} difficulty={self.difficulty}>"


# ── Tag (Etiket) ──────────────────────────────────────────────────────────────
class Tag(Base):
    """
    Kartlara atanan konu etiketleri.
    Bir kart birden fazla etikete sahip olabilir (M2M).
    """
    __tablename__ = "tags"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False, index=True)

    # İlişkiler
    flashcards = relationship("Flashcard", secondary=flashcard_tags, back_populates="tags")

    def __repr__(self):
        return f"<Tag id={self.id} name='{self.name}'>"
