"""
flashcard_generator/card_builder.py
--------------------------------------
Puanlanmış cümlelerden ve anahtar kelimelerden Q&A flashcard nesneleri üretir.

Üretim stratejileri:
  1. "Tanım" kartı   — Cümlenin başındaki anahtar kelime soruya dönüştürülür.
  2. "Doldur-boşluk" — Anahtar kelimenin silinmesiyle tamamlama sorusu.
  3. "Genel bilgi"   — Cümle özeti soruya, cümlenin kendisi cevaba dönüşür.

Tekrarlı kartlar:
  - Jaro-Winkler benzeri basit overlap kontrolüyle yakalanır.
  - is_duplicate=True olarak işaretlenir, veritabanına eklenmez.
"""

import re
from flashcard_generator.sentence_analyzer import score_sentences
from flashcard_generator.keyword_extractor import extract_keywords


# ── Şablonlar ─────────────────────────────────────────────────────────────────

# Soru şablonları (kart türü → şablon)
_DEFINITION_TEMPLATES = [
    "'{keyword}' nedir? Lütfen detaylıca açıklayınız.",
    "'{keyword}' kavramının temel önemi ve işlevini açıklayın.",
    "Metne göre '{keyword}' neyi ifade etmektedir?",
    "'{keyword}' hakkında bilinen temel özellikleri sıralayınız.",
]

_GENERAL_TEMPLATES = [
    "Aşağıdaki ifade bağlamında önemli olan nedir? '{excerpt}'",
    "Bu cümledeki temel fikri açıklayınız: '{excerpt}'",
    "Şu ifadeden yola çıkarak konuyu yorumlayınız: '{excerpt}'",
]


def _pick_template(templates: list[str], idx: int) -> str:
    """Şablonlar arasında döngüsel seçim yapar."""
    return templates[idx % len(templates)]


def _excerpt(sentence: str, max_len: int = 80) -> str:
    """Cümlenin kısaltılmış halini döndürür."""
    if len(sentence) <= max_len:
        return sentence
    return sentence[:max_len].rsplit(" ", 1)[0] + "..."


def _similarity(a: str, b: str) -> float:
    """İki metin arasındaki basit Jaccard benzerliği (0-1)."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _is_duplicate(question: str, existing: list[str], threshold: float = 0.65) -> bool:
    """Soru mevcut kartlarla %65+ benzerlik taşıyorsa tekrar sayar."""
    return any(_similarity(question, q) >= threshold for q in existing)


def _find_best_keyword(sentence: str, matched_keywords: list[str]) -> str:
    """
    Cümledeki en uygun anahtar kelimeyi seçer.
    Eğer cümle bir tanım cümlesi ise (denir, adlandırılır vb.), 
    tanımlanan asıl terimi bulmaya çalışır.
    """
    if not matched_keywords:
        return ""
        
    s_lower = sentence.lower()
    # Tanım kalıpları
    def_patterns = ["denir", "adlandırılır", "ifade eder", "açıklanır", "kastedilir"]
    
    for pattern in def_patterns:
        if pattern in s_lower:
            # Tanımlanan kelime genelde bu kalıplardan hemen öncedir
            # matched_keywords içinden hangisi bu kalıba en yakınsa onu seç
            parts = s_lower.split(pattern)
            left_side = parts[0]
            
            # En sağdaki (kalıba en yakın) anahtar kelimeyi bul
            best_kw = matched_keywords[0]
            max_pos = -1
            for kw in matched_keywords:
                pos = left_side.rfind(kw.lower())
                if pos > max_pos:
                    max_pos = pos
                    best_kw = kw
            return best_kw
            
    # Tanım cümlesi değilse, metin genelindeki frekansı en yüksek olanı (ilkini) kullan
    return matched_keywords[0]


# ── Ana Fonksiyon ─────────────────────────────────────────────────────────────

def build_flashcards(text: str, max_cards: int = 20) -> list[dict]:
    """
    Metinden Q&A flashcard listesi üretir.
    Zeki anahtar kelime seçimi ile soru-cevap uyumluluğu artırılmıştır.
    """
    # Cümleleri ve anahtar kelimeleri al
    top_sentences = score_sentences(text, top_n=max_cards * 2)
    keywords_data = extract_keywords(text, top_n=20)
    top_keywords  = [kw["keyword"] for kw in keywords_data]

    cards: list[dict] = []
    seen_questions: list[str] = []
    card_idx = 0

    for sent_obj in top_sentences:
        if len(cards) >= max_cards:
            break

        sentence = sent_obj["sentence"]
        score    = sent_obj["score"]

        # Cümledeki anahtar kelimeleri bul
        matched_keywords = [
            kw for kw in top_keywords if kw.lower() in sentence.lower()
        ]

        if matched_keywords:
            # ── Strateji: Tanım/Kavram Kartı ──────────────────────────────────
            keyword = _find_best_keyword(sentence, matched_keywords)

            question = _pick_template(_DEFINITION_TEMPLATES, card_idx).format(
                keyword=keyword
            )
            answer = sentence

            is_dup = _is_duplicate(question, seen_questions)
            if not is_dup:
                cards.append({
                    "question":     question,
                    "answer":       answer,
                    "score":        score,
                    "topic":        keyword,
                    "is_duplicate": False,
                })
                seen_questions.append(question)
                card_idx += 1
        else:
            # ── Strateji: Genel Bilgi Kartı ────────────────────────────
            excerpt = _excerpt(sentence)
            q3 = _pick_template(_GENERAL_TEMPLATES, card_idx).format(excerpt=excerpt)
            is_dup3 = _is_duplicate(q3, seen_questions)
            if not is_dup3:
                cards.append({
                    "question":     q3,
                    "answer":       sentence,
                    "score":        score * 0.7,
                    "topic":        None,
                    "is_duplicate": False,
                })
                seen_questions.append(q3)
                card_idx += 1

    return cards[:max_cards]

