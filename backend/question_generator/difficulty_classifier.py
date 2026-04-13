"""
question_generator/difficulty_classifier.py
---------------------------------------------
Flashcard cevabına bakarak zorluk seviyesi belirler.

Sınıflandırma kriterleri:
  - Cümle uzunluğu (kelime sayısı)
  - Nadir/teknik kelime oranı (3+ heceli kelimeler)
  - Sayı, formül veya özel terim varlığı

Döndürür: "easy" | "medium" | "hard"
"""

import re


# ── Eşik Değerleri ────────────────────────────────────────────────────────────
_EASY_WORD_LIMIT   =  10   # 10 kelime ve altı → easy
_HARD_WORD_LIMIT   =  30   # 30 kelime ve üstü → hard (uzun cevap = zor)

_LONG_WORD_CHARS   =   8   # 8+ karakter uzunluğundaki kelimeler "uzun" sayılır
_HARD_LONG_RATIO   = 0.30  # Uzun kelime oranı %30+ → hard
_MEDIUM_LONG_RATIO = 0.15  # Uzun kelime oranı %15+ → medium

# Teknik / karmaşık içerik belirteçleri
_TECHNICAL_PATTERN = re.compile(
    r"\d+[\.,]\d+|"          # Ondalık/kesirli sayı
    r"\b\d{4,}\b|"           # 4+ basamaklı sayı
    r"[A-Z]{2,}|"            # Kısaltmalar (DNA, RNA vb.)
    r"[+\-*/=<>]{2,}|"       # Matematiksel operatörler
    r"\([^)]{5,}\)",          # Parantez içi açıklama
    re.UNICODE,
)


def classify_difficulty(text: str) -> str:
    """
    Verilen metni (genellikle flashcard cevabı) analiz ederek
    zorluk seviyesi belirler.

    Args:
        text: Analiz edilecek metin.

    Returns:
        "easy", "medium" veya "hard" string değeri.
    """
    if not text or not text.strip():
        return "medium"

    words = text.strip().split()
    word_count = len(words)

    # ── 1. Kelime sayısına göre hızlı sınıflandırma ───────────────────────────
    if word_count <= _EASY_WORD_LIMIT:
        return "easy"

    if word_count >= _HARD_WORD_LIMIT:
        # Uzun cevap — teknik içerik var mı kontrol et
        if _TECHNICAL_PATTERN.search(text):
            return "hard"
        return "hard"   # Çok uzun cevap her durumda hard

    # ── 2. Uzun/teknik kelime oranı ───────────────────────────────────────────
    long_words = [w for w in words if len(w) >= _LONG_WORD_CHARS and w.isalpha()]
    long_ratio  = len(long_words) / word_count

    has_technical = bool(_TECHNICAL_PATTERN.search(text))

    if long_ratio >= _HARD_LONG_RATIO or has_technical:
        return "hard"

    if long_ratio >= _MEDIUM_LONG_RATIO:
        return "medium"

    # ── 3. Varsayılan: kelime sayısına göre ──────────────────────────────────
    if word_count <= 15:
        return "easy"
    if word_count <= 22:
        return "medium"
    return "hard"
