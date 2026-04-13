import sqlite3
import os

db_path = "C:\\Users\\HP\\.gemini\\antigravity\\scratch\\smart-flashcard\\flashcards.db"

if os.path.exists(db_path):
    print(f"Veritabanı bulundu: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("SRS sütunları ekleniyor...")
        cursor.execute("ALTER TABLE flashcards ADD COLUMN easiness_factor FLOAT DEFAULT 2.5")
        cursor.execute("ALTER TABLE flashcards ADD COLUMN interval INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE flashcards ADD COLUMN repetitions INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE flashcards ADD COLUMN next_review_at DATETIME")
        
        # Varsayılan değer olarak şu anki zamanı ata
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        cursor.execute(f"UPDATE flashcards SET next_review_at = '{now}' WHERE next_review_at IS NULL")
        
        conn.commit()
        print("✅ Başarıyla güncellendi!")
    except sqlite3.OperationalError as e:
        print(f"Not: Sütunlar zaten var olabilir veya bir hata oluştu: {e}")
    finally:
        conn.close()
else:
    print("Veritabanı dosyası bulunamadı, yeni başlatmada otomatik oluşacaktır.")
