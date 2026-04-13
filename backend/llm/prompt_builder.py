"""
llm/prompt_builder.py
-----------------------
LLM'e gönderilecek prompt'ları (komutları) oluşturur.
Şu an sadece Soru-Cevap (QA) kartları üretmeye odaklanmıştır.
Sınav modu bu QA kartlarını dinamik olarak MCQ'ya çevirir.
"""

# ── Sistem Promptu ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Sen uzman bir öğretmensin. Görevin, verilen metinden öğrencilerin konusunu derinden anlamasını sağlayacak, yüksek kaliteli ve profesyonel flashcard'lar (bilgi kartları) üretmektir.

KURALLAR:
1. Yanıtını YALNIZCA JSON listesi olarak ver. Başka hiçbir açıklama yazma.
2. Soru zorluk alanları (difficulty): "easy", "medium", "hard"
3. Soru tipi (type): Daima "qa" (klasik soru-cevap)
4. DİL: Sadece Türkçe dilinde üret.
5. YASAKLI FORMATLAR: 
   - "Boşluk doldurma" (fill-in-the-blank) yapma (örn: "____ nedir?").
   - "Cümleyi tamamla" (Complete the sentence) yapma.
   - Çok kısa ve anlamsız sorular yazma (örn: "Veri nedir?").
6. KALİTE KRİTERİ: 
   - Sorular açık, anlaşılır ve merak uyandırıcı olmalıdır. 
   - "Neden?", "Nasıl?", "Farkı nedir?", "Hangi durumda kullanılır?" gibi akıl yürütücü soruları tercih et.
7. TEKİLLİK: Aynı soruyu veya çok benzerlerini tekrar etme.
8. BAĞLAM: Sadece verilen metindeki teknik ve önemli kavramlara odaklan.

ÖRNEK JSON ÇIKTISI (BUNLAR SADECE ÖRNEKTİR, KOPYALAMA):
[
  {
    "question": "Veritabanı Yönetim Sistemlerinin (VTYS) temel kullanım amacı ve sağladığı ana avantaj nedir?",
    "answer": "VTYS, verilerin güvenli, düzenli ve verimli bir şekilde depolanmasını, yönetilmesini ve eş zamanlı erişimini sağlayarak veri tutarsızlığını önler.",
    "difficulty": "medium",
    "type": "qa"
  }
]
""".strip()



# ── Prompt Şablonları ─────────────────────────────────────────────────────────

_QA_PROMPT_TEMPLATE = """\
Aşağıdaki ders notundan {count} adet Soru-Cevap (QA) flashcard üret.
Zorluk dağılımı: %40 easy, %40 medium, %20 hard

DERS NOTU:
\"\"\"
{text}
\"\"\"

ÇIKTI (yalnızca JSON listesi):
""".strip()


# ── Metin Sınırlama ───────────────────────────────────────────────────────────

def _truncate_text(text: str, max_chars: int = 3000) -> str:
    """LLM context penceresine sığması için metni kısaltır."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(".", 1)[0] + ".\n\n...[metin kısaltıldı]"


# ── Public API ────────────────────────────────────────────────────────────────

def build_qa_prompt(text: str, count: int = 10) -> str:
    """Yalnızca QA kartları için prompt oluşturur."""
    return _QA_PROMPT_TEMPLATE.format(
        count=count,
        text=_truncate_text(text),
    )


def build_mcq_prompt(text: str, count: int = 10) -> str:
    """Geriye dönük uyumluluk için; artık QA promptu döndürür."""
    return build_qa_prompt(text, count)


def build_mixed_prompt(text: str, total: int = 15) -> str:
    """Geriye dönük uyumluluk için; artık QA promptu döndürür."""
    return build_qa_prompt(text, total)
