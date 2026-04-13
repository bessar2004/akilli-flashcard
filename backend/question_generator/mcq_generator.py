"""
question_generator/mcq_generator.py
--------------------------------------
Çoktan seçmeli soru (MCQ) üretici.

Yöntem:
  1. Cümleleri ve anahtar kelimeleri al
  2. Her önemli cümle için doğru cevabı belirle (içerik cümlesi)
  3. Diğer anahtar kelimelerden 3 yanlış seçenek (distractor) seç
  4. Seçenekleri karıştır, doğru index'i kaydet

Çıktı formatı:
  {
    "question":    str,
    "answer":      str,        # Doğru cevabın metni
    "options":     list[str],  # 4 elemanlı: ["A) ...", "B) ...", "C) ...", "D) ..."]
    "correct_idx": int,        # 0-3 arası
    "score":       float,
    "topic":       str | None,
  }
"""

import random
from flashcard_generator.sentence_analyzer import score_sentences
from flashcard_generator.keyword_extractor import extract_keywords


_MCQ_QUESTION_TEMPLATES = [
    "'{keyword}' kavramı ile ilgili hangisi doğrudur?",
    "'{keyword}' en iyi şekilde aşağıdakilerden hangisi ile açıklanır?",
    "Aşağıdakilerden hangisi '{keyword}' kavramını doğru tanımlar?",
    "Which of the following best describes '{keyword}'?",
    "What is the correct statement about '{keyword}'?",
]


def _format_option(letter: str, text: str) -> str:
    """Seçeneği standart formata çevirir: 'A) metin'"""
    # Eğer zaten 'X) ' formatındaysa dokunma
    if len(text) >= 3 and text[1] == ")" and text[0].isalpha():
        return text
    return f"{letter}) {text}"


def generate_mcqs(text: str, max_questions: int = 10) -> list[dict]:
    """
    Verilen metinden çoktan seçmeli sorular üretir.

    Args:
        text:          Temizlenmiş metin.
        max_questions: Üretilecek maksimum soru sayısı.

    Returns:
        MCQ kart dict listesi.
    """
    top_sentences = score_sentences(text, top_n=max_questions * 3)
    keywords_data = extract_keywords(text, top_n=25)

    if len(keywords_data) < 4:
        # Yeterli keyword yoksa MCQ üretilemiyor
        return []

    keyword_list = [kw["keyword"] for kw in keywords_data]
    results: list[dict] = []

    for idx, sent_obj in enumerate(top_sentences):
        if len(results) >= max_questions:
            break

        sentence = sent_obj["sentence"]
        score    = sent_obj["score"]

        # Cümledeki keywordleri bul
        matched = [kw for kw in keyword_list if kw.lower() in sentence.lower()]
        if not matched:
            continue

        correct_keyword = matched[0]                     # Doğru cevap
        correct_answer  = sentence                       # Doğru cevap açıklaması

        # 3 dikdeyici seçenek: diğer keywordlerden al
        distractors_pool = [kw for kw in keyword_list if kw != correct_keyword]
        random.shuffle(distractors_pool)
        distractors = distractors_pool[:3]

        if len(distractors) < 3:
            continue     # Yeterli dikdeyici yoksa atla

        # Tüm seçenekleri karıştır (doğru + 3 yanlış)
        all_options = [correct_answer] + [
            f"{d} — bu terim '{correct_keyword}' ile ilişkili değildir."
            for d in distractors
        ]
        random.shuffle(all_options)
        correct_idx = all_options.index(correct_answer)

        # Seçeneklere harf etiketi ekle
        letters = ["A", "B", "C", "D"]
        formatted_options = [
            _format_option(letters[i], opt) for i, opt in enumerate(all_options)
        ]

        # Soru şablonu seç
        template = _MCQ_QUESTION_TEMPLATES[idx % len(_MCQ_QUESTION_TEMPLATES)]
        question = template.format(keyword=correct_keyword)

        results.append({
            "question":    question,
            "answer":      correct_answer,
            "options":     formatted_options,
            "correct_idx": correct_idx,
            "score":       score,
            "topic":       correct_keyword,
        })

    return results[:max_questions]
