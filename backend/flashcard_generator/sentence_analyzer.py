"""
flashcard_generator/sentence_analyzer.py
------------------------------------------
Cümleleri anahtar kelime yoğunluğuna göre puanlar ve sıralar.

Puanlama mantığı:
  - Cümledeki anahtar kelime sayısı / cümle uzunluğu = keyword yoğunluğu
  - Cümle başındaki ve sonundaki cümleler bonus alır (konu özeti olma ihtimali)
  - Çok kısa (< 5 kelime) ve çok uzun (> 60 kelime) cümleler cezalandırılır

Çıktı: Skora göre sıralanmış cümle listesi
"""

import re
from data_processing.text_cleaner import tokenize_sentences
from flashcard_generator.keyword_extractor import extract_keywords


def score_sentences(
    text: str,
    top_n: int = 20,
    min_words: int = 8,
    max_words: int = 60,
) -> list[dict]:
    """
    Metindeki cümleleri önem skoruna göre puanlar.

    Args:
        text:      Analiz edilecek metin.
        top_n:     Döndürülecek maksimum cümle sayısı.
        min_words: Minimum cümle kelime sayısı.
        max_words: Maksimum cümle kelime sayısı.

    Returns:
        [{"sentence": str, "score": float, "position": int}, ...] listesi,
        skora göre azalan sırada.
    """
    # 1. Cümlelere böl
    sentences = tokenize_sentences(text)
    if not sentences:
        return []

    # 2. Anahtar kelimeleri çıkar
    keywords_data = extract_keywords(text, top_n=30)
    keyword_set = {kw["keyword"].lower() for kw in keywords_data}
    keyword_score = {kw["keyword"].lower(): kw["score"] for kw in keywords_data}

    total_sentences = len(sentences)
    scored = []

    for idx, sentence in enumerate(sentences):
        words = sentence.lower().split()
        word_count = len(words)

        # Uzunluk filtresi
        if word_count < min_words or word_count > max_words:
            continue

        # 3. Keyword skoru: cümledeki keyword'lerin ağırlıklı toplamı
        kw_score = sum(keyword_score.get(w, 0) for w in words)
        density  = kw_score / word_count        # Kelime başına düşen skor

        # 4. Pozisyon bonusu: ilk ve son %20 cümleler önemlidir
        position_ratio = idx / total_sentences
        if position_ratio <= 0.2 or position_ratio >= 0.8:
            position_bonus = 0.15
        else:
            position_bonus = 0.0

        # 5. Uzunluk bonusu: ideal uzunluk 15-35 kelime
        if 15 <= word_count <= 35:
            length_bonus = 0.1
        elif word_count < 10:
            length_bonus = -0.1
        else:
            length_bonus = 0.0

        final_score = density + position_bonus + length_bonus

        scored.append({
            "sentence": sentence.strip(),
            "score": round(max(final_score, 0.0), 4),
            "position": idx,
            "word_count": word_count,
        })

    # 6. Skora göre sırala, top_n kadar döndür
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]
