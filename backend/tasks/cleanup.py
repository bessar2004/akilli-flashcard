"""
tasks/cleanup.py
----------------
Eski verileri (24 saatten eski) otomatik temizleyen arka plan görevi.
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Document
from config import settings

logger = logging.getLogger(__name__)

def cleanup_old_data():
    """
    Kullanım süresi dolmuş (varsayılan 24 saat) dokümanları ve 
    bunlara bağlı flashcard'ları veritabanından siler.
    """
    db: Session = SessionLocal()
    try:
        threshold_time = datetime.utcnow() - timedelta(hours=settings.AUTO_CLEANUP_HOURS)
        
        # Eşiğin altında kalan dokümanları bul (Cascade delete kartları da siler)
        old_docs = db.query(Document).filter(Document.created_at < threshold_time).all()
        
        count = len(old_docs)
        if count > 0:
            logger.info(f"🧹 Temizlik başlatıldı: {count} adet eski doküman siliniyor...")
            for doc in old_docs:
                db.delete(doc)
            db.commit()
            logger.info(f"✅ Temizlik tamamlandı. {count} doküman veritabanından başarıyla temizlendi.")
        else:
            logger.debug("Temizlik: Silinecek eski veri bulunamadı.")
            
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Temizlik sırasında hata oluştu: {str(e)}")
    finally:
        db.close()

def _cleanup_worker():
    """Arka plan döngüsü (Worker)"""
    logger.info(f"🚀 Auto-Cleanup Worker başlatıldı. (Eşik: {settings.AUTO_CLEANUP_HOURS} saat)")
    
    while True:
        if settings.AUTO_CLEANUP_ENABLED:
            cleanup_old_data()
        
        # Saatte bir kontrol et
        time.sleep(3600)

def start_cleanup_worker():
    """Temizlik işçisini bir thread olarak başlatır."""
    thread = threading.Thread(target=_cleanup_worker, daemon=True)
    thread.start()
