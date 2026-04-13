"""
llm/llm_generator.py
----------------------
Ollama LLM'den flashcard üretimini orkestre eder.

Sorumluluklar:
  1. Prompt oluştur (prompt_builder kullanarak)
  2. Ollama'ya gönder (ollama_client kullanarak)
  3. Ham metin yanıtını JSON'a çevir ve doğrula
  4. Ollama erişilemezse NLP fallback'e düş (card_builder)

Döndürülen flashcard formatı:
  [
    {
      "question"   : str,
      "answer"     : str,
      "difficulty" : "easy" | "medium" | "hard",
      "type"       : "qa"   | "mcq",
      "options"    : list[str] | None,   # MCQ için
      "correct_idx": int | None,         # MCQ için
      "score"      : float,
      "topic"      : str | None,
      "is_duplicate": bool,
      "source"     : "llm" | "nlp",     # Kartın kaynağı
    }
  ]
"""

import json
import re
import logging
from typing import Optional

from llm.ollama_client import default_client, OllamaClient
from llm.prompt_builder import (
    SYSTEM_PROMPT,
    build_qa_prompt,
    build_mcq_prompt,
    build_mixed_prompt,
)

logger = logging.getLogger(__name__)

# Geçerli alan değerleri
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_TYPES        = {"qa", "mcq"}


# ── JSON Ayrıştırıcı ──────────────────────────────────────────────────────────

def _extract_json_block(raw: str) -> str:
    """
    LLM yanıtından JSON listesini çıkarır.
    LLM bazen açıklama metni veya ```json ... ``` bloğu ekleyebilir.
    """
    # Markdown kod bloğu varsa içini al
    md_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if md_match:
        return md_match.group(1)

    # Düz JSON listesi varsa al (ilk [ ... ] bloğu)
    bracket_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if bracket_match:
        return bracket_match.group(0)

    return raw.strip()


def _validate_card(card: dict) -> Optional[dict]:
    """
    Tek bir kart dict'ini doğrular ve normalize eder.
    Geçersiz kartlar None döndürür.
    """
    # Zorunlu alanlar
    question = str(card.get("question", "")).strip()
    answer   = str(card.get("answer",   "")).strip()
    if not question or not answer:
        return None

    # Zorluk seviyesi
    difficulty = str(card.get("difficulty", "medium")).lower()
    if difficulty not in _VALID_DIFFICULTIES:
        difficulty = "medium"

    # Kart türü
    card_type = str(card.get("type", "qa")).lower()
    if card_type not in _VALID_TYPES:
        card_type = "qa"

    # MCQ alanlarını doğrula
    options    = card.get("options")
    correct_idx = card.get("correct_idx")

    if card_type == "mcq":
        # options en az 2 elemanlı liste olmalı
        if not isinstance(options, list) or len(options) < 2:
            # MCQ formatı bozuksa qa'ya düşür
            card_type = "qa"
            options    = None
            correct_idx = None
        else:
            options = [str(o) for o in options]
            # doğru idx sınırların dışındaysa 0'a çek
            if not isinstance(correct_idx, int) or not (0 <= correct_idx < len(options)):
                correct_idx = 0
    else:
        options    = None
        correct_idx = None

    return {
        "question":    question,
        "answer":      answer,
        "difficulty":  difficulty,
        "type":        card_type,
        "options":     options,
        "correct_idx": correct_idx,
        "score":       0.8,          # LLM kartları varsayılan yüksek skor
        "topic":       card.get("topic"),
        "is_duplicate": False,
        "source":      "llm",
    }


def parse_llm_response(raw_response: str) -> list[dict]:
    """
    LLM'in ham metin yanıtını doğrulanmış flashcard listesine dönüştürür.

    Args:
        raw_response: Ollama'dan gelen ham metin.

    Returns:
        Geçerli flashcard dict listesi. Ayrıştırma başarısızsa boş liste.
    """
    if not raw_response.strip():
        logger.warning("LLM boş yanıt döndürdü.")
        return []

    json_str = _extract_json_block(raw_response)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        # JSON bozuksa basit düzeltme dene: trailing comma, tek tırnak
        cleaned = re.sub(r",\s*([}\]])", r"\1", json_str)   # trailing comma
        cleaned = cleaned.replace("'", '"')                  # tek → çift tırnak
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("LLM yanıtı JSON olarak ayrıştırılamadı: %s", e)
            return []

    if not isinstance(data, list):
        logger.warning("LLM yanıtı liste değil: %s", type(data))
        return []

    valid_cards = []
    for raw_card in data:
        if not isinstance(raw_card, dict):
            continue
        card = _validate_card(raw_card)
        if card:
            valid_cards.append(card)

    logger.info("LLM yanıtından %d/%d geçerli kart çıkarıldı.", len(valid_cards), len(data))
    return valid_cards


# ── Ana Generator ─────────────────────────────────────────────────────────────

def generate_with_llm(
    text: str,
    max_cards: int        = 15,
    include_qa: bool      = True,
    include_mcq: bool     = True,
    client: OllamaClient  = None,
) -> list[dict]:
    """
    Ollama LLM kullanarak flashcard üretir.
    Ollama erişilemezse NLP tabanlı fallback'e geçer.

    Args:
        text:        Temizlenmiş ders notu metni.
        max_cards:   Üretilecek maksimum kart sayısı.
        include_qa:  QA kartları dahil edilsin mi?
        include_mcq: MCQ kartları dahil edilsin mi?
        client:      Kullanılacak OllamaClient örneği (None → singleton).

    Returns:
        Flashcard dict listesi (source alanı "llm" veya "nlp").
    """
    llm = client or default_client

    # ── 1. Ollama erişilebilirlik kontrolü ───────────────────────────────────
    if not llm.is_available():
        logger.warning(
            "Ollama erişilemez. NLP fallback kullanılıyor (model: %s).", llm.model
        )
        return _nlp_fallback(text, max_cards, include_qa, include_mcq)

    # ── 2. Prompt seç ve gönder ───────────────────────────────────────────────
    try:
        if include_qa and include_mcq:
            user_prompt = build_mixed_prompt(text, total=max_cards)
        elif include_mcq:
            user_prompt = build_mcq_prompt(text, count=max_cards)
        else:
            user_prompt = build_qa_prompt(text, count=max_cards)

        logger.info("LLM'e istek gönderiliyor: model=%s, max_cards=%d", llm.model, max_cards)
        raw_response = llm.generate(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
        )
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        logger.error("LLM isteği başarısız: %s. NLP fallback kullanılıyor.", e)
        return _nlp_fallback(text, max_cards, include_qa, include_mcq)

    # ── 3. Ayrıştır ve doğrula ────────────────────────────────────────────────
    cards = parse_llm_response(raw_response)

    if not cards:
        logger.warning("LLM geçerli kart üretemedi. NLP fallback kullanılıyor.")
        return _nlp_fallback(text, max_cards, include_qa, include_mcq)

    # İstenmeyen kart tiplerini sil (LLM kural tanımamışsa)
    if not include_qa:
        cards = [c for c in cards if c["type"] != "qa"]
    if not include_mcq:
        cards = [c for c in cards if c["type"] != "mcq"]

    # ── 4. MCQ Eksikliğini Telafi Et (Fallback) ─────────────────────────────
    # Küçük LLM'ler (örn gemma 1B) format kurallarını hiçe sayıp MCQ üretmeyebilir.
    if include_mcq:
        mcq_count = sum(1 for c in cards if c["type"] == "mcq")
        if mcq_count < (max_cards // 2 if include_qa else max_cards):
            logger.warning("LLM yetersiz MCQ üretti! NLP MCQ Üretici devreye giriyor.")
            hedef = max_cards // 2 if include_qa else max_cards
            eksik_mcq_sayisi = hedef - mcq_count
            
            nlp_cards = _nlp_fallback(text, max_cards=eksik_mcq_sayisi, include_qa=False, include_mcq=True)
            cards = nlp_cards + cards

    # Yeterince QA yoksa QA telafisi yap
    if include_qa:
        qa_count = sum(1 for c in cards if c["type"] == "qa")
        if qa_count < (max_cards // 2 if include_mcq else max_cards):
            hedef = max_cards // 2 if include_mcq else max_cards
            eksik_qa_sayisi = hedef - qa_count
            nlp_cards = _nlp_fallback(text, max_cards=eksik_qa_sayisi, include_qa=True, include_mcq=False)
            cards = cards + nlp_cards

    return cards[:max_cards]


# ── NLP Fallback ──────────────────────────────────────────────────────────────

def _nlp_fallback(
    text: str,
    max_cards: int,
    include_qa: bool,
    include_mcq: bool,
) -> list[dict]:
    """
    Ollama kullanılamadığında devreye giren NLTK tabanlı flashcard üretici.
    Eski sistem korunur — hiçbir dosya silinmez.
    """
    from flashcard_generator.card_builder  import build_flashcards
    from question_generator.mcq_generator  import generate_mcqs
    from question_generator.difficulty_classifier import classify_difficulty

    results: list[dict] = []

    if include_qa:
        qa_limit = max_cards if not include_mcq else max_cards // 2
        for item in build_flashcards(text, max_cards=qa_limit):
            item["type"]   = "qa"
            item["source"] = "nlp"
            item.setdefault("difficulty", "medium")
            item.setdefault("options",    None)
            item.setdefault("correct_idx", None)
            results.append(item)

    if include_mcq:
        mcq_limit = max_cards - len(results)
        for item in generate_mcqs(text, max_questions=mcq_limit):
            item["type"]        = "mcq"
            item["source"]      = "nlp"
            item["is_duplicate"] = False
            item.setdefault("difficulty", classify_difficulty(item.get("answer", "")))
            results.append(item)

    return results[:max_cards]
