"""
question_generator/qa_generator.py
-------------------------------------
Klasik soru-cevap kartları üretir.
(Bu modül card_builder.py ile örtüşebilir;
 burada alternatif / ek QA stratejileri barındırılır.)

Ek stratejiler:
  - "Kim/Ne/Nerede/Ne zaman/Neden" soru kalıpları
  - Birden fazla cümleyi birleştiren özet sorular
"""

from flashcard_generator.sentence_analyzer import score_sentences
from flashcard_generator.keyword_extractor import extract_keywords

# Soru başlangıcı kalıpları
_WHO_WHAT_TEMPLATES = [
    ("kim",     "Bu metne göre, {subject} kimdir?"),
    ("what",    "What does '{subject}' refer to in this context?"),
    ("neden",   "'{subject}' neden önemlidir?"),
    ("why",     "Why is '{subject}' significant?"),
    ("nasıl",   "'{subject}' nasıl çalışır?"),
    ("how",     "How does '{subject}' work?"),
]


def generate_qa_cards(text: str, max_cards: int = 10) -> list[dict]:
    """
    Verilen metinden 'Kim/Ne/Neden/Nasıl' tarzı QA kartları üretir.

    Bu fonksiyon `card_builder.build_flashcards`'ı tamamlar;
    router tarafından doğrudan çağrılmaz, card_builder içinden kullanılabilir.

    Args:
        text:      Temizlenmiş metin.
        max_cards: Üretilecek maksimum kart sayısı.

    Returns:
        QA kart dict listesi.
    """
    top_sentences = score_sentences(text, top_n=max_cards * 2)
    keywords_data = extract_keywords(text, top_n=15)
    if not keywords_data or not top_sentences:
        return []

    cards: list[dict] = []
    for idx, kw_obj in enumerate(keywords_data[:max_cards]):
        keyword = kw_obj["keyword"]
        # Bu keyword'ü içeren en iyi cümleyi bul
        relevant = [
            s for s in top_sentences
            if keyword.lower() in s["sentence"].lower()
        ]
        if not relevant:
            continue

        best_sentence = relevant[0]["sentence"]
        score         = relevant[0]["score"]

        # Kalıp seç (döngüsel)
        _, template = _WHO_WHAT_TEMPLATES[idx % len(_WHO_WHAT_TEMPLATES)]
        question = template.format(subject=keyword)

        cards.append({
            "question":     question,
            "answer":       best_sentence,
            "score":        score,
            "topic":        keyword,
            "is_duplicate": False,
        })

    return cards[:max_cards]
