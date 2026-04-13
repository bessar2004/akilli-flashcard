"""
flashcard_generator/keyword_extractor.py
-----------------------------------------
NLTK POS tagging ve TF-IDF benzeri yaklaşım ile metinden
anahtar kelimeleri çıkarır.

Yöntem:
  1. Metni cümlelere ve tokenlara böl
  2. POS tagging ile isim (NN*) ve özel isim (NNP*) etiketli kelimeleri seç
  3. Frekans sayımı → normalize et (TF)
  4. Kısa / stopword kelimeleri filtrele
  5. En yüksek skorlu N kelimeyi döndür
"""

import re
import math
from collections import Counter

# NLTK modülleri
try:
    import nltk
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords

    for _pkg in ("averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "punkt", "stopwords"):
        try:
            nltk.data.find(f"taggers/{_pkg}")
        except (LookupError, OSError):
            try:
                nltk.data.find(f"tokenizers/{_pkg}")
            except (LookupError, OSError):
                try:
                    nltk.data.find(f"corpora/{_pkg}")
                except (LookupError, OSError):
                    try:
                        nltk.download(_pkg, quiet=True)
                    except Exception:
                        pass

    _STOPWORDS = set(stopwords.words("english")) | {
        "also", "however", "therefore", "thus", "hence", "furthermore",
        "moreover", "although", "despite", "since", "because",
        # Türkçe
        "bir", "ve", "ile", "bu", "da", "de", "ki", "için", "olan",
        "olarak", "ise", "ne", "her", "ama", "veya", "gibi",
    }
    _NLTK_OK = True
except ImportError:
    _NLTK_OK = False
    _STOPWORDS: set[str] = set()

# İsim türlerine ait POS etiketleri (NLTK tagging)
_NOUN_TAGS = {"NN", "NNS", "NNP", "NNPS"}


def _pos_tag_words(text: str) -> list[tuple[str, str]]:
    """Metni tokenize edip POS etiketler."""
    if not _NLTK_OK:
        # Fallback: büyük harfle başlayan kelimeleri keyword say
        tokens = re.findall(r"\b[A-ZÇĞİÖŞÜ][a-zçğışöüa-z]{2,}\b", text)
        return [(t, "NNP") for t in tokens]

    tokens = word_tokenize(text)
    return nltk.pos_tag(tokens)


def _is_valid_keyword(word: str) -> bool:
    """Kelimenin anahtar kelime olarak geçerli olup olmadığını kontrol eder."""
    return (
        len(word) >= 3                # En az 3 karakter
        and word.isalpha()            # Sadece harf
        and word.lower() not in _STOPWORDS
    )


def extract_keywords(text: str, top_n: int = 15) -> list[dict]:
    """
    Metinden en önemli N anahtar kelimeyi çıkarır.

    Args:
        text:  Anahtar kelime çıkarılacak metin.
        top_n: Döndürülecek maksimum anahtar kelime sayısı.

    Returns:
        [{"keyword": str, "score": float, "pos": str}, ...] listesi,
        skora göre azalan sırada.
    """
    if not text.strip():
        return []

    tagged = _pos_tag_words(text)

    # İsim türündeki kelimeleri al
    noun_words = [
        word.lower()
        for word, tag in tagged
        if tag in _NOUN_TAGS and _is_valid_keyword(word)
    ]

    if not noun_words:
        # Fallback: tüm alfanümerik kelimeleri say
        noun_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-ZçğışöüÇĞİŞÖÜ]{3,}\b", text)
            if w.lower() not in _STOPWORDS
        ]

    # Frekans sayımı
    freq = Counter(noun_words)
    total = sum(freq.values()) or 1

    # TF skoru hesapla ve normalize et
    max_freq = max(freq.values())
    results = []
    for word, count in freq.most_common(top_n * 2):  # Daha fazla al, sonra filtrele
        tf_score = count / max_freq               # Normalize TF (0-1)
        results.append({
            "keyword": word,
            "score": round(tf_score, 4),
            "count": count,
        })

    # Skora göre sırala, top_n kadar döndür
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
