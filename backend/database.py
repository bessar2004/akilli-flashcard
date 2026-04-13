"""
database.py
-----------
SQLAlchemy bağlantı motoru ve oturum (session) yönetimi.
FastAPI dependency injection ile entegre çalışır.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

# ── Motor ─────────────────────────────────────────────────────────────────────
# SQLite için check_same_thread=False gereklidir (FastAPI async desteği)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,          # SQL sorgularını terminale yaz (debug)
)

# SQLite performansı için WAL modu ve yabancı anahtar desteği aç
@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")      # Yazma kilitleme azaltır
    cursor.execute("PRAGMA foreign_keys=ON")        # FK kısıtları aktif
    cursor.close()


# ── Oturum Fabrikası ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   # Manuel commit zorunlu
    autoflush=False,    # Manuel flush zorunlu
)

# ── Taban Sınıf ───────────────────────────────────────────────────────────────
# Tüm ORM modelleri bu sınıftan miras alır
Base = declarative_base()


# ── FastAPI Dependency ────────────────────────────────────────────────────────
def get_db():
    """
    Her HTTP isteği için bağımsız bir veritabanı oturumu açar.
    İstek bitince oturumu otomatik kapatır.
    Kullanım: def some_endpoint(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Tüm tanımlı tabloları veritabanında oluşturur (varsa atlar)."""
    Base.metadata.create_all(bind=engine)
