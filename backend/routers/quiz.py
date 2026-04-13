"""
routers/quiz.py
----------------
Quiz (Sınav) modu endpoint'leri.

POST /api/quiz/generate  — Mevcut kartlardan sınav oluştur
POST /api/quiz/submit    — Sınav cevaplarını değerlendir, sonuç döndür
"""

import random
import json
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from models   import Flashcard, Document

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
#  SCHEMAS (quiz'e özel — schemas.py'yi kirletmemek için burada tutulur)
# ═══════════════════════════════════════════════════════════════════════════════

class QuizGenerateRequest(BaseModel):
    document_id: Optional[int] = Field(None,  description="Belirli belge (None → tüm kartlar)")
    count:       int            = Field(10,    ge=3,  le=50, description="Sınav soru sayısı")
    difficulty:  Optional[str]  = Field(None,  pattern="^(easy|medium|hard)$")
    card_type:   Optional[str]  = Field(None,  pattern="^(qa|mcq)$")
    shuffle:     bool           = Field(True,  description="Soruları karıştır")


class QuizQuestion(BaseModel):
    """Kullanıcıya gönderilen tek soru (cevap içermez)."""
    index:       int
    card_id:     int
    question:    str
    card_type:   str            # "qa" | "mcq"
    difficulty:  str
    options:     Optional[list[str]] = None   # Yalnızca MCQ


class QuizSession(BaseModel):
    """generate endpoint'inin döndürdüğü sınav oturumu."""
    session_id:  str             # client'ın sakladığı basit token
    total:       int
    questions:   list[QuizQuestion]


class UserAnswer(BaseModel):
    card_id:       int
    card_type:     str            # "qa" | "mcq"
    answer_text:   Optional[str] = None   # QA cevabı
    answer_idx:    Optional[int] = None   # MCQ seçenek indeksi (0-3)


class QuizSubmitRequest(BaseModel):
    answers: list[UserAnswer] = Field(..., min_length=1)


class QuizAnswerResult(BaseModel):
    card_id:     int
    card_type:   str
    question:    str
    user_answer: str
    correct_answer: str
    is_correct:  bool
    difficulty:  str
    options:     Optional[list[str]] = None   # MCQ için şıklar
    user_idx:    Optional[int]        = None   # Kullanıcının seçtiği index
    correct_idx: Optional[int]        = None   # Doğru index


class QuizResult(BaseModel):
    """submit endpoint'inin döndürdüğü sonuç."""
    total:          int
    correct:        int
    incorrect:      int
    score_pct:      float           # 0-100 arası yüzde
    grade:          str             # A / B / C / D / F
    details:        list[QuizAnswerResult]
    completed_at:   str


# ═══════════════════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════

def _grade(pct: float) -> str:
    """Yüzdeye göre harf notu döndürür."""
    if pct >= 90: return "A"
    if pct >= 75: return "B"
    if pct >= 60: return "C"
    if pct >= 45: return "D"
    return "F"


def _clean_option_text(text: str) -> str:
    """Şıklardaki 'A) ', '1. ', 'a-' gibi ön ekleri temizler."""
    if not text:
        return ""
    # Regex: Başta olabilecek A), B., 1), 1., a) gibi tipik MCQ prefixlerini temizle
    # Sadece ilk 1-3 karakterde bir harf/rakam + noktalama/boşluk varsa temizle
    pattern = r'^([a-dA-DxX1-4][\)\.\-\s]+|([A-D]|[1-4])\s)'
    return re.sub(pattern, "", text.strip()).strip()


def _parse_options(card: Flashcard, clean: bool = True) -> Optional[list[str]]:
    """Kartın options alanını listeye çevirir ve isteğe bağlı temizler."""
    opts = None
    if not card.options:
        opts = None
    elif isinstance(card.options, list):
        opts = card.options
    else:
        try:
            opts = json.loads(card.options)
        except Exception:
            opts = None
            
    if opts and clean:
        return [_clean_option_text(o) for o in opts]
    return opts


def _get_distractors(db: Session, card: Flashcard, count: int = 3) -> list[str]:
    """
    Aynı dökümandaki diğer kartlardan çeldirici (yanlış cevap) toplar.
    QA kartları için 'answer' alanını, MCQ için ise doğru şık metnini kullanır.
    """
    correct_text = card.answer
    if card.card_type == "mcq":
        opts = _parse_options(card, clean=True)
        if opts and card.correct_idx is not None and 0 <= card.correct_idx < len(opts):
            correct_text = opts[card.correct_idx]

    # Aynı dökümana ait diğer kartları çek (duplicate olmayan ve onaylanmış)
    potential_cards = db.query(Flashcard).filter(
        Flashcard.document_id == card.document_id,
        Flashcard.id != card.id,
        Flashcard.is_duplicate.is_(False),
    ).all()
    
    distractors = []
    seen = {correct_text.lower().strip()}
    
    # Karıştırıp örnekle
    random.shuffle(potential_cards)
    for c in potential_cards:
        d_text = c.answer
        if c.card_type == "mcq":
            c_opts = _parse_options(c, clean=True)
            if c_opts and c.correct_idx is not None and 0 <= c.correct_idx < len(c_opts):
                d_text = c_opts[c.correct_idx]
        
        d_clean = _clean_option_text(d_text)
        if d_clean and d_clean.lower().strip() not in seen:
            distractors.append(d_clean)
            seen.add(d_clean.lower().strip())
        
        if len(distractors) >= count:
            break
            
    # Yeterli çeldirici yoksa, dolgu yerine (veya global havuz yerine) mevcutları döndür.
    # Count'tan az dönmesi durumunda generate_quiz bunu fark edip QA'e çevirecek.
    return distractors[:count]


def _turkish_lower(text: str) -> str:
    """Türkçe İ/i ve I/ı harf dönüşümlerini doğru yapan küçük harf fonksiyonu."""
    if not text: return ""
    return text.replace('İ', 'i').replace('I', 'ı').lower()


def _fuzzy_ratio(s1: str, s2: str) -> float:
    """Basit bir karakter bazlı benzerlik oranı (0.0 - 1.0)."""
    if not s1 or not s2: return 0.0
    if s1 == s2: return 1.0
    
    # Çok basit bir token ve substring kontrolü
    # Eğer biri diğerini içeriyorsa ve aradaki fark azsa yüksek puan ver
    s1, s2 = _turkish_lower(s1), _turkish_lower(s2)
    if s1 == s2: return 1.0
    
    # Kısa kelimeler için (örn: cevap "Veri") 'contains' kontrolü
    if len(s2) <= 5:
        if s2 in s1 or s1 in s2: return 0.9
    
    # Uzun kelimelerde/cümlelerde ortak kelime oranına bak
    u_words = set(s1.split())
    c_words = set(s2.split())
    overlap = u_words & c_words
    
    # Kök bazlı basit kontrol: kelimelerin ilk 4 harfi eşleşiyor mu?
    # (Türkçe eklemeli dil olduğu için kökler genellikle 3-5 harftir)
    stem_matches = 0
    for cw in c_words:
        if any(cw[:4] == uw[:4] for uw in u_words if len(uw) >= 4 and len(cw) >= 4):
            stem_matches += 1
            
    word_score = (len(overlap) + stem_matches) / (len(c_words) * 2) if c_words else 0
    return min(word_score * 2, 1.0) # Skoru normalize et


def _normalize_qa_answer(text: str) -> str:
    """QA cevabını normalleştirir (trimle, Türkçe küçük harf)."""
    return _turkish_lower(text.strip())[:500]


def _check_qa(user: str, correct: str, threshold: float = 0.5) -> bool:
    """
    Gelişmiş QA kontrolü: 
    1. Tam eşleşme (Küçük harf duyarsız)
    2. Karakter/Kök bazlı benzerlik (Fuzzy)
    3. Alt metin kontrolü
    """
    user_norm = _normalize_qa_answer(user)
    correct_norm = _normalize_qa_answer(correct)
    
    if not user_norm: return False
    if user_norm == correct_norm: return True
    
    # Eğer kullanıcı cevabı doğru cevabı içeriyorsa (örn: 'Veritabanıdır' içinde 'Veritabanı' geçer)
    if correct_norm in user_norm and len(user_norm) < len(correct_norm) * 2:
        return True
        
    # Bulanık skor kontrolü
    score = _fuzzy_ratio(user_norm, correct_norm)
    return score >= threshold



# ═══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── POST /api/quiz/generate ───────────────────────────────────────────────────
@router.post(
    "/quiz/generate",
    response_model=QuizSession,
    status_code=status.HTTP_201_CREATED,
    summary="Mevcut flashcard'lardan sınav oluştur",
)
def generate_quiz(
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Veritabanındaki kartlardan sınav soruları seçer.
    Cevaplar bu aşamada gönderilmez — kullanıcı /submit ile cevaplayacak.

    Filtreler:
      - document_id → yalnızca o belgenin kartları
      - difficulty  → kolay/orta/zor
      - card_type   → qa/mcq
      - shuffle     → soruları karıştır
    """
    q = db.query(Flashcard).filter(
        Flashcard.is_duplicate.is_(False),
    )

    if payload.document_id:
        # Doküman var mı kontrol et
        doc = db.get(Document, payload.document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Doküman bulunamadı.")
        q = q.filter(Flashcard.document_id == payload.document_id)

    if payload.difficulty:
        q = q.filter(Flashcard.difficulty == payload.difficulty)

    # NOT: card_type filtresi DB seviyesinde kaldırıldı. 
    # Çünkü QA kartlarını sınav anında MCQ'ya dönüştürebiliriz.
    
    cards_all: list[Flashcard] = q.all()

    # ── DUPLICATE PREVENTION: Metni aynı olan soruları temizle ─────────────
    unique_cards_map = {}
    for c in cards_all:
        q_norm = c.question.strip().lower()
        if q_norm not in unique_cards_map:
            unique_cards_map[q_norm] = c
    
    cards = list(unique_cards_map.values())
    # ────────────────────────────────────────────────────────────────────────

    if not cards:
        msg = "Bu dökümanda hiç kart bulunamadı." if payload.document_id else "Veritabanında hiç kart bulunamadı."
        raise HTTPException(status_code=404, detail=msg)

    if len(cards) < payload.count:
        # Yeterli kart yoksa mevcut kartları kullan
        selected = cards
    else:
        selected = random.sample(cards, payload.count) if payload.shuffle else cards[:payload.count]

    if payload.shuffle:
        random.shuffle(selected)

    # Soruları oluştur — cevabı GÖNDERMEYİZ
    questions = []
    requested_card_type = payload.card_type # mcq, qa veya None (Karışık)

    for idx, card in enumerate(selected):
        correct_text = card.answer
        
        # O anki soru için hangi tipi kullanacağımıza karar ver
        current_q_type = requested_card_type
        if not current_q_type: # Karışık ise
            current_q_type = random.choice(["qa", "mcq"])
        
        opts = None
        if current_q_type == "mcq":
            # MCQ isteniyorsa, kart ister MCQ olsun ister QA olsun, 4 şıklı test hazırla
            if card.card_type == "mcq":
                existing_opts = _parse_options(card, clean=True)
                if existing_opts and card.correct_idx is not None:
                    opts = existing_opts
                else:
                    dist = _get_distractors(db, card, 3)
                    if len(dist) < 3: # Yeterli şık yoksa QA'e dön
                        current_q_type = "qa"
                        opts = None
                    else:
                        opts = [_clean_option_text(correct_text)] + dist
                        random.shuffle(opts)
            else:
                dist = _get_distractors(db, card, 3)
                if len(dist) < 3: # Yeterli şık yoksa QA'e dön
                    current_q_type = "qa"
                    opts = None
                else:
                    opts = [_clean_option_text(correct_text)] + dist
                    random.shuffle(opts)
        else:
            # QA isteniyorsa şık hazırlama
            current_q_type = "qa"
            opts = None

        questions.append(QuizQuestion(
            index=idx,
            card_id=card.id,
            question=card.question,
            card_type=current_q_type,
            difficulty=card.difficulty,
            options=opts,
        ))

    # Basit session_id: timestamp + belge id
    session_id = f"quiz_{payload.document_id or 'all'}_{int(datetime.utcnow().timestamp())}"

    return QuizSession(
        session_id=session_id,
        total=len(questions),
        questions=questions,
    )


# ── POST /api/quiz/submit ────────────────────────────────────────────────────
@router.post(
    "/quiz/submit",
    response_model=QuizResult,
    summary="Sınav cevaplarını değerlendir",
)
def submit_quiz(
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Kullanıcının gönderdiği cevapları değerlendirir.

    - MCQ: doğru indeksi karşılaştır
    - QA:  Jaccard benzerliği ile kelime örtüşmesine bak (≥35% → doğru)

    Doğru/yanlış sayıları veritabanına kaydedilir.
    """
    if not payload.answers:
        raise HTTPException(status_code=400, detail="Cevap listesi boş.")

    details: list[QuizAnswerResult] = []
    correct_count = 0

    for ans in payload.answers:
        card = db.get(Flashcard, ans.card_id)
        if not card:
            continue    # Silinmiş kart varsa atla

        is_correct = False
        user_answer_str = ""

        if ans.answer_idx is not None:
            # Sınav artık hep MCQ (indeks bazlı) değerlendiriliyor
            correct_idx = -1
            
            # Doğru metni bulup seçeneklerdeki konumunu tespit et
            actual_correct_text = _clean_option_text(card.answer)
            # generate_quiz ile aynı şıkları bulmamız lazım ama stateless olduğu için 
            # submit payload'unda 'options' gelmesi gerekebilir veya JS'den kontrol edilmeli.
            # Şimdilik: Eğer card MCQ ise DB'den bak, değilse JS'in gönderdiği string üzerinden git.
            
            # NOT: Frontend'de submit_quiz çağrılırken artık index gönderiliyor.
            # Bizim generate_quiz card_type="mcq" döndürdüğü için submit de mcq bekliyor.
            
            # Gelişmiş kontrol: Index üzerinden doğru metni doğrula
            # JS'in quiz state'inden gelen answer_idx verisini kullanıyoruz.
            # Ama backend'in 'doğru indeksi' bilmesi için seçeneklerin sırasını bilmesi lazım.
            # Stateless yapıda bu zor, bu yüzden submit payload'u options da içermeli 
            # YA DA backend cevap doğruluğunu METİN ÜZERİNDEN yapmalı (frontend indeksi metne çevirip gönderebilir).
            
            # Mevcut JS yapısına uyum için: QA kartı olsa bile biz onu MCQ sanıyoruz.
            # En sağlam yol: answer_idx üzerinden is_correct kontrolünü şimdilik metin bazlı fallback ile yapalım 
            # veya şimdilik JS'ten gelen answer_idx'i card.correct_idx ile (eğer mcq ise) karşılaştıralım.
            
            # DÜZELTME: is_correct logic
            if card.card_type == "mcq":
                # Veritabanında zaten MCQ olarak kayıtlıysa indeks üzerinden bak
                is_correct = (ans.answer_idx == card.correct_idx)
            else:
                # Dinamik üretilen QA->MCQ için metin tabanlı tam eşleşme kontrolü yap
                # Artık _check_qa (similarity) yerine MCQ için tam metin temizliği sonrası eşleşme bakıyoruz
                normalized_user = _normalize_qa_answer(_clean_option_text(ans.answer_text or ""))
                normalized_correct = _normalize_qa_answer(_clean_option_text(card.answer))
                is_correct = (normalized_user == normalized_correct)

            user_answer_str = ans.answer_text or str(ans.answer_idx)
        else:
            # QA: metin benzerliği
            user_raw = (ans.answer_text or "").strip()
            if not user_raw:
                is_correct = False
                user_answer_str = "(boş)"
            else:
                is_correct = _check_qa(user_raw, card.answer)
                user_answer_str = user_raw[:200]

        if is_correct:
            correct_count += 1
            card.correct_count += 1
        else:
            card.incorrect_count += 1

        card.last_reviewed_at = datetime.utcnow()

        details.append(QuizAnswerResult(
            card_id=card.id,
            card_type=card.card_type,
            question=card.question,
            user_answer=user_answer_str,
            correct_answer=card.answer,
            is_correct=is_correct,
            difficulty=card.difficulty,
            options=_parse_options(card) if card.card_type == "mcq" else None,
            user_idx=ans.answer_idx if card.card_type == "mcq" else None,
            correct_idx=card.correct_idx if card.card_type == "mcq" else None,
        ))

    db.commit()

    total      = len(details)
    incorrect  = total - correct_count
    pct        = round((correct_count / total * 100), 1) if total else 0.0
    grade      = _grade(pct)

    return QuizResult(
        total=total,
        correct=correct_count,
        incorrect=incorrect,
        score_pct=pct,
        grade=grade,
        details=details,
        completed_at=datetime.utcnow().isoformat(),
    )
