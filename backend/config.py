"""
config.py
---------
Merkezi yapılandırma dosyası.
Pydantic-Settings ile ortam değişkenlerini ya da varsayılan değerleri okur.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Projenin kök dizini: smart-flashcard/
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── Uygulama ─────────────────────────────────────────────
    APP_NAME: str = "Smart Flashcard API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ── Veritabanı ────────────────────────────────────────────
    # SQLite dosyası proje kökünde oluşturulur
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'flashcards.db'}"

    # ── Dosya Yükleme ─────────────────────────────────────────
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50           # Maks yükleme boyutu (MB)
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx", "txt"]

    # ── Flashcard Üretim Parametreleri ────────────────────────
    MAX_CARDS_PER_DOCUMENT: int = 50     # Doküman başına maks kart sayısı
    MIN_SENTENCE_LENGTH: int = 10        # Kart için minimum cümle uzunluğu (kelime)
    TOP_KEYWORDS: int = 15               # Çıkarılacak anahtar kelime sayısı
    TOP_SENTENCES: int = 20             # Değerlendirilecek cümle sayısı

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]     # Production'da spesifik originler ekle

    # ── Auto-Cleanup (Otomatik Temizlik) ─────────────────────────────────────
    AUTO_CLEANUP_ENABLED: bool = True
    AUTO_CLEANUP_HOURS:   int  = 24
    # ─────────────────────────────────────────────────────────────────────────

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Uygulama genelinde tek örnek (singleton)
settings = Settings()

# Yükleme klasörünü oluştur (yoksa)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
