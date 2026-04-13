/**
 * api.js
 * Tüm backend API çağrılarını yöneten yardımcı modül.
 * Base URL: window.location.origin (sunucuyla aynı host)
 */

const API_BASE = `${window.location.origin}/api`;

/**
 * Temel fetch sarmalayıcı — JSON döndürür, hataları fırlatır.
 */
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.message || data.detail || `HTTP ${res.status}`);
  }
  return data;
}

/** LLM / Ollama durum bilgisini getir */
export async function getLLMStatus() {
  return apiFetch("/llm/status");
}

/**
 * Düz metin gönder → document_id döndürür
 * @param {string} text
 * @param {string} title
 */
export async function submitText(text, title = "Manuel Metin") {
  return apiFetch("/text", {
    method: "POST",
    body: JSON.stringify({ text, title }),
  });
}

/**
 * PDF veya DOCX dosyası yükle → document_id döndürür
 * @param {File} file
 */
export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  form.append("title", file.name);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: form,       // Content-Type'ı tarayıcı otomatik ayarlar (multipart)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || data.detail || `HTTP ${res.status}`);
  return data;
}

/**
 * Belge için flashcard üret
 * @param {number} documentId
 * @param {object} opts
 */
export async function generateFlashcards(documentId, opts = {}) {
  return apiFetch("/generate", {
    method: "POST",
    body: JSON.stringify({
      document_id:  documentId,
      max_cards:    opts.maxCards    ?? 15,
      include_qa:   opts.includeQA   ?? true,
      include_mcq:  opts.includeMCQ  ?? true,
    }),
  });
}

/**
 * Belirli bir kartı güncelle
 * @param {number} cardId
 * @param {object} payload
 */
export async function updateFlashcard(cardId, payload) {
  return apiFetch(`/flashcards/${cardId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * Kartı sil
 * @param {number} cardId
 */
export async function deleteFlashcard(cardId) {
  return apiFetch(`/flashcards/${cardId}`, { method: "DELETE" });
}

/**
 * Tekrar sistemine doğru/yanlış gönder
 * @param {number} cardId
 * @param {boolean} wasCorrect
 */
export async function reviewCard(cardId, wasCorrect) {
  return apiFetch(`/flashcards/${cardId}/review`, {
    method: "POST",
    body: JSON.stringify({ flashcard_id: cardId, was_correct: wasCorrect }),
  });
}

/** Tüm dokümanları listele */
export async function listDocuments() {
  return apiFetch("/documents");
}
