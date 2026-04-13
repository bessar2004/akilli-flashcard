"""
data_processing/pdf_reader.py
------------------------------
PyMuPDF (fitz) kullanarak PDF dosyasından ham metin çıkarır.
"""

import fitz  # PyMuPDF


def extract_text_from_pdf(file_path: str) -> str:
    """
    Verilen PDF dosyasının tüm sayfalarından metin çıkarır.

    Args:
        file_path: PDF dosyasının mutlak yolu.

    Returns:
        Tüm sayfaların birleştirilmiş ham metni.

    Raises:
        RuntimeError: Dosya açılamazsa veya metin çıkarılamazsa.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise RuntimeError(f"PDF açılamadı: {e}")

    pages_text: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Metni bloklar halinde çıkar, satır sırasını koru
        text = page.get_text("text")
        if text.strip():
            pages_text.append(text)

    doc.close()

    if not pages_text:
        raise RuntimeError("PDF'ten metin çıkarılamadı. Dosya taranmış görsel olabilir.")

    return "\n\n".join(pages_text)
