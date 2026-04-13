"""
data_processing/text_cleaner.py
---------------------------------
Metni normalleştirir: gereksiz boşlukları, özel karakterleri ve
İngilizce/Türkçe stopwords'leri kaldırır.

Adımlar:
  1. Unicode normalizasyonu
  2. HTML/XML etiketlerini kaldır
  3. Çok satırlı boşlukları tek satıra indir
  4. Cümle tokenizasyonu için temel temizlik
"""

import re
import unicodedata
import sys


# ── NLTK kurulumu (yoksa indir) ───────────────────────────────────────────────
try:
    import nltk
    from nltk.corpus   import stopwords
    from nltk.tokenize import sent_tokenize

    # Gerekli NLTK verilerini kontrol et
    try:
        nltk.data.find("tokenizers/punkt")
    except (LookupError, OSError):
        nltk.download("punkt", quiet=True)

    try:
        nltk.data.find("corpora/stopwords")
    except (LookupError, OSError):
        nltk.download("stopwords", quiet=True)

    _EN_STOPWORDS = set(stopwords.words("english"))
    # Türkçe stopwords (elle tanımlı temel liste)
    _TR_STOPWORDS = {
        "bir", "ve", "ile", "bu", "da", "de", "ki", "mi", "mu", "mü",
        "için", "olan", "olarak", "ise", "ne", "en", "çok", "daha",
        "her", "ama", "veya", "ya", "gibi", "kadar", "sonra", "önce",
        "ben", "sen", "o", "biz", "siz", "onlar", "bu", "şu",
    }
    STOPWORDS = _EN_STOPWORDS | _TR_STOPWORDS
    _NLTK_AVAILABLE = True

except ImportError:
    _NLTK_AVAILABLE = False
    STOPWORDS: set[str] = set()


# ── Regex desenleri (önceden derle — performans) ──────────────────────────────
_RE_HTML    = re.compile(r"<[^>]+>")                  # HTML etiketleri
_RE_URL     = re.compile(r"https?://\S+|www\.\S+")    # URL'ler
_RE_EMAIL   = re.compile(r"\S+@\S+\.\S+")             # E-postalar
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")             # 3+ boş satır → 2
_RE_MULTI_SPACE   = re.compile(r" {2,}")              # Birden fazla boşluk
_RE_SPECIAL = re.compile(r"[^\w\s.,;:?!\'\"-]", re.UNICODE)  # Özel karakterler


def _normalize_unicode(text: str) -> str:
    """Unicode karakterleri NFC formuna normalize eder."""
    return unicodedata.normalize("NFC", text)


def _remove_html(text: str) -> str:
    return _RE_HTML.sub(" ", text)


def _remove_urls_emails(text: str) -> str:
    text = _RE_URL.sub(" ", text)
    return _RE_EMAIL.sub(" ", text)


def _normalize_whitespace(text: str) -> str:
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """
    Verilen ham metni temizler ve normalleştirir.

    İşlem adımları:
      1. Unicode normalizasyonu
      2. HTML etiketlerini kaldır
      3. URL ve e-postaları kaldır
      4. Özel karakterleri kaldır (noktalama işaretlerini koru)
      5. Çoklu boşlukları düzelt

    Not: Stopwords burada kaldırılmaz; cümle bütünlüğü bozulur.
         Stopwords, keyword extraction aşamasında filtrelenir.

    Args:
        text: Temizlenecek ham metin.

    Returns:
        Temizlenmiş metin.
    """
    if not text:
        return ""

    text = _normalize_unicode(text)
    text = _remove_html(text)
    text = _remove_urls_emails(text)
    text = _RE_SPECIAL.sub(" ", text)
    text = _normalize_whitespace(text)

    return text


def tokenize_sentences(text: str) -> list[str]:
    """
    Metni cümlelere böler.
    NLTK varsa sent_tokenize kullanır, yoksa basit nokta bölümü yapar.

    Args:
        text: Temizlenmiş metin.

    Returns:
        Cümle listesi.
    """
    if _NLTK_AVAILABLE:
        sentences = sent_tokenize(text)
    else:
        # Basit fallback: nokta + büyük harf ile böl
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])", text)

    # Çok kısa cümleleri filtrele (5 kelimeden az)
    return [s.strip() for s in sentences if len(s.split()) >= 5]


def remove_stopwords(tokens: list[str]) -> list[str]:
    """
    Token listesinden stopwords'leri kaldırır.

    Args:
        tokens: Kelime listesi.

    Returns:
        Stopword'lerden arındırılmış token listesi.
    """
    return [t for t in tokens if t.lower() not in STOPWORDS]
