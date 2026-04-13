/**
 * app.js
 * Uygulama ana kontrolcüsü.
 * - Tab navigation (Yükle / Kartlar / Çalış)
 * - LLM durum badge'i
 * - Dosya / metin gönderme
 * - Flashcard üretimi ve önizleme
 * - Flip-card etkileşimi
 * - MCQ seçenek kontrolü
 * - Kart silme & düzenleme
 * - Çalışma modu (Study mode)
 */

import {
  getLLMStatus, submitText, uploadFile,
  generateFlashcards, updateFlashcard, deleteFlashcard, reviewCard,
} from "./api.js";
import { initQuiz, loadQuizDocuments } from "./quiz.js";
import { speak, stopSpeech } from "./tts.js";
import { initTheme, toggleTheme } from "./theme.js";

// ── State ─────────────────────────────────────────────────────────────────────
let state = {
  documentId:   null,
  cards:        [],         // Güncel flashcard listesi
  studyIndex:   0,          // Çalışma modundaki aktif kart indeksi
  studyScore:   { correct: 0, incorrect: 0 },
  llmActive:    false,
  filter:       "all",      // all | easy | medium | hard | qa | mcq
};

// ── DOM Referansları ──────────────────────────────────────────────────────────
const tabs        = document.querySelectorAll(".tab-btn");
const tabPanels   = document.querySelectorAll(".tab-panel");
const llmBadge    = document.getElementById("llm-badge");
const llmText     = document.getElementById("llm-text");

// Yükleme paneli
const dropZone    = document.getElementById("drop-zone");
const fileInput   = document.getElementById("file-input");
const textArea    = document.getElementById("text-input");
const titleInput  = document.getElementById("title-input");
const maxSlider   = document.getElementById("max-cards");
const maxLabel    = document.getElementById("max-cards-label");
const chkQA       = document.getElementById("chk-qa");
const chkMCQ      = document.getElementById("chk-mcq");
const generateBtn = document.getElementById("generate-btn");
const sourceStatus= document.getElementById("source-status");

// Kartlar paneli
const cardsGrid   = document.getElementById("cards-grid");
const emptyState  = document.getElementById("empty-state");
const filterBtns  = document.querySelectorAll(".filter-btn");
const cardCount   = document.getElementById("card-count");

// Çalışma paneli
const studyCard   = document.getElementById("study-card");
const btnNext     = document.getElementById("btn-next");
const btnPrev     = document.getElementById("btn-prev");
const btnCorrect  = document.getElementById("btn-correct");
const btnWrong    = document.getElementById("btn-wrong");
const studyScore  = document.getElementById("study-score");
// studyFinish, studyQ, studyA vb. elemanları fonksiyon içinden çekeceğiz (Stale reference önlemek için)
const studyFinish = document.getElementById("study-finish");

// Düzenleme modalı
const editModal   = document.getElementById("edit-modal");
const editQ       = document.getElementById("edit-question");
const editA       = document.getElementById("edit-answer");
const editDiff    = document.getElementById("edit-difficulty");
const editSaveBtn = document.getElementById("edit-save");
const editCloseBtn= document.getElementById("edit-close");
let   editingCardId = null;

// Toast
const toast       = document.getElementById("toast");
let   toastTimer  = null;

// ── Başlangıç ─────────────────────────────────────────────────────────────────
(async function init() {
  try {
    initTheme();
    setupTabs();
    setupDragDrop();
    setupSlider();
    setupFilters();
    setupExportButtons();
    setupStudyButtons();
    setupEditModal();
    initQuiz();
    checkLLMStatus(); // await kaldırılarak arka planda çalışması sağlandı

    const thBtn = document.getElementById("theme-toggle");
    if (thBtn) thBtn.addEventListener("click", toggleTheme);

    setInterval(checkLLMStatus, 30_000);
  } catch (err) {
    console.error("Uygulama başlatılamadı:", err);
    // Hata durumunda kullanıcıya göster
    const llmText = document.getElementById("llm-text");
    if (llmText) llmText.textContent = "⚠️ Başlatma Hatası";
  }
})();

// ── LLM Durum Kontrolü ───────────────────────────────────────────────────────
async function checkLLMStatus() {
  try {
    const s = await getLLMStatus();
    state.llmActive = s.ollama_available;
    llmBadge.className = `llm-badge ${s.ollama_available ? "llm-on" : "llm-off"}`;
    llmText.textContent = s.ollama_available
      ? `🤖 LLM Aktif · ${s.configured_model}`
      : `⚙️ NLP Modu (Ollama kapalı)`;
  } catch {
    llmBadge.className = "llm-badge llm-off";
    llmText.textContent = "⚙️ NLP Modu";
  }
}

function setupTabs() {
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabs.forEach(b => b.classList.remove("active"));
      tabPanels.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`panel-${target}`).classList.add("active");

      if (target === "study") {
        loadStudyCards(true);
      }
      if (target === "cards") {
        renderCards(); // Sekmeye geçince kartları tazele
      }
      if (target === "quiz") {
        loadQuizDocuments();
      }
      stopSpeech(); // Tab değişince sesi kes
    });
  });
}

// ── Drag & Drop ───────────────────────────────────────────────────────────────
function setupDragDrop() {
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
  });
}

function handleFileSelect(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx", "txt"].includes(ext)) {
    showToast("⚠️ Yalnızca PDF, DOCX veya TXT dosyaları desteklenir.", "error");
    return;
  }
  sourceStatus.textContent = `📎 Seçilen: ${file.name}`;
  sourceStatus.dataset.file = "1";
  // Dosyayı state'e sakla
  state.pendingFile = file;
  textArea.value = "";
}

// ── Slider ────────────────────────────────────────────────────────────────────
function setupSlider() {
  maxSlider.addEventListener("input", () => {
    maxLabel.textContent = maxSlider.value;
  });
}

// ── Filtreleme ────────────────────────────────────────────────────────────────
function setupFilters() {
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.filter = btn.dataset.filter;
      renderCards();
    });
  });
}

// ── Export Fonksiyonları ──────────────────────────────────────────────────────
function setupExportButtons() {
  const btnAnki = document.getElementById("export-anki");

  btnAnki.addEventListener("click", () => {

    if (!state.documentId) {
      showToast("Önce bir döküman seçin veya yükleyin.", "error");
      return;
    }
    window.location.href = `/api/export/anki/${state.documentId}`;
  });
}

// ── Flashcard Üretimi ─────────────────────────────────────────────────────────
generateBtn.addEventListener("click", async () => {
  const hasFile   = !!state.pendingFile;
  const hasText   = textArea.value.trim().length >= 20;

  if (!hasFile && !hasText) {
    showToast("⚠️ Bir dosya seçin veya en az 20 karakter metin girin.", "error");
    return;
  }

  setLoading(true);
  state.cards = []; // Yeni yükleme öncesi listeyi boşalt
  renderCards();
  
  try {
    // 1. Dokümanı yükle / metin gönder
    let docResp;
    if (hasFile) {
      docResp = await uploadFile(state.pendingFile);
    } else {
      docResp = await submitText(
        textArea.value.trim(),
        titleInput.value.trim() || "Manuel Metin"
      );
    }
    state.documentId = docResp.id;

    // 2. Flashcard üret
    const result = await generateFlashcards(state.documentId, {
      maxCards:   parseInt(maxSlider.value),
      includeQA:  chkQA ? chkQA.checked : true,
      includeMCQ: chkMCQ ? chkMCQ.checked : false,
    });


    state.cards = (result.flashcards || []).filter(c => !c.is_duplicate);
    showToast(`✅ ${state.cards.length} kart üretildi!`, "success");

    // Kartlar sekmesine geç
    document.querySelector('[data-tab="cards"]').click();
    renderCards();

    // Kaynağı temizle
    state.pendingFile = null;
    sourceStatus.textContent = "Henüz dosya seçilmedi.";
    fileInput.value = "";

  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  } finally {
    setLoading(false);
  }
});

function setLoading(on) {
  generateBtn.disabled = on;
  generateBtn.textContent = on ? "⏳ Üretiliyor..." : "✨ Flashcard Üret";
}

// ── Kart Render ───────────────────────────────────────────────────────────────
function getFilteredCards() {
  if (state.filter === "all") return state.cards;
  if (["easy","medium","hard"].includes(state.filter))
    return state.cards.filter(c => c.difficulty === state.filter);
  if (["qa","mcq"].includes(state.filter))
    return state.cards.filter(c => c.card_type === state.filter);
  return state.cards;
}

function renderCards() {
  const filtered = getFilteredCards();
  cardCount.textContent = `${filtered.length} kart`;
  cardsGrid.innerHTML = "";

  if (filtered.length === 0) {
    emptyState.style.display = "flex";
    return;
  }
  emptyState.style.display = "none";

  filtered.forEach(card => {
    cardsGrid.appendChild(buildCardElement(card));
  });
}

function buildCardElement(card) {
  const isMCQ = card.card_type === "mcq";
  const diffClass = { easy: "diff-easy", medium: "diff-medium", hard: "diff-hard" }[card.difficulty] || "diff-medium";
  const diffLabel = { easy: "Kolay", medium: "Orta", hard: "Zor" }[card.difficulty] || "Orta";
  const typeLabel = isMCQ ? "MCQ" : "QA";

  // Parse options
  let options = [];
  if (isMCQ) {
    try {
      options = typeof card.options === "string"
        ? JSON.parse(card.options)
        : (card.options || []);
    } catch { options = []; }
  }

  const el = document.createElement("div");
  el.className = "flip-card";
  el.dataset.id = card.id;

  el.innerHTML = `
    <div class="flip-inner">
      <!-- ÖN YÜZ: SORU -->
      <div class="flip-front">
        <div class="card-badges">
          <span class="badge ${diffClass}">${diffLabel}</span>
          <span class="badge badge-type">${typeLabel}</span>
        </div>
        <div class="card-question">${escHtml(card.question)}</div>
        ${isMCQ && options.length ? `
          <div class="mcq-options" data-correct="${card.correct_idx ?? 0}">
            ${options.map((opt, i) => `
              <button class="mcq-opt" data-idx="${i}">
                <span style="font-weight: bold; margin-right: 0.5rem;">${String.fromCharCode(65 + i)})</span>
                ${escHtml(opt)}
              </button>
            `).join("")}
          </div>
          <div class="mcq-hint">← Bir seçenek seç</div>
        ` : `
          <div class="flip-hint">↻ Cevap için tıkla</div>
        `}
        <button class="tts-btn card-tts-trigger" title="Dinle">🔊</button>
      </div>

      <!-- ARKA YÜZ: CEVAP -->
      <div class="flip-back">
        <div class="card-badges">
          <span class="badge ${diffClass}">${diffLabel}</span>
          <span class="badge badge-type">${typeLabel}</span>
        </div>
        <div class="card-answer">${escHtml(card.answer)}</div>
        ${card.topic ? `<div class="card-topic">🏷️ ${escHtml(card.topic)}</div>` : ""}
        <div class="flip-hint">↻ Soruya dön</div>
        <button class="tts-btn card-tts-trigger" title="Dinle">🔊</button>
      </div>
    </div>

    <!-- EYLEM BUTONLARI -->
    <div class="card-actions">
      <button class="act-btn act-edit" title="Düzenle" data-id="${card.id}">✏️</button>
      <button class="act-btn act-del"  title="Sil"     data-id="${card.id}">🗑️</button>
    </div>
  `;

  // Flip (MCQ'da sadece arka yüzden dön)
  const inner = el.querySelector(".flip-inner");
  if (!isMCQ) {
    inner.addEventListener("click", () => el.classList.toggle("flipped"));
  } else {
    el.querySelector(".flip-back").addEventListener("click", () => el.classList.remove("flipped"));
  }

  // MCQ seçenek tıklaması
  if (isMCQ) {
    const correctIdx = card.correct_idx ?? 0;
    el.querySelectorAll(".mcq-opt").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx);
        el.querySelectorAll(".mcq-opt").forEach(b => b.classList.remove("opt-correct","opt-wrong"));
        btn.classList.add(idx === correctIdx ? "opt-correct" : "opt-wrong");
        if (idx !== correctIdx) {
          el.querySelector(`.mcq-opt[data-idx="${correctIdx}"]`).classList.add("opt-correct");
        }
        el.querySelector(".mcq-hint").textContent = idx === correctIdx ? "✅ Doğru!" : "❌ Yanlış";
        // Arka yüze geç
        setTimeout(() => el.classList.add("flipped"), 800);
      });
    });
  }

  // Düzenle
  el.querySelector(".act-edit").addEventListener("click", e => {
    e.stopPropagation();
    openEditModal(card);
  });

  // Sil
  el.querySelector(".act-del").addEventListener("click", async e => {
    e.stopPropagation();
    if (!confirm("Bu kartı silmek istiyor musunuz?")) return;
    try {
      await deleteFlashcard(card.id);
      state.cards = state.cards.filter(c => c.id !== card.id);
      renderCards();
      showToast("🗑️ Kart silindi.", "info");
    } catch (err) {
      showToast(`❌ ${err.message}`, "error");
    }
  });

  // TTS Butonları
  el.querySelectorAll(".card-tts-trigger").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const isBack = btn.closest(".flip-back");
      speak(isBack ? card.answer : card.question);
    });
  });

  return el;
}

// ── Düzenleme Modalı ──────────────────────────────────────────────────────────
function setupEditModal() {
  editCloseBtn.addEventListener("click", closeEditModal);
  editModal.addEventListener("click", e => {
    if (e.target === editModal) closeEditModal();
  });
  editSaveBtn.addEventListener("click", async () => {
    if (!editingCardId) return;
    try {
      const updated = await updateFlashcard(editingCardId, {
        question:   editQ.value.trim(),
        answer:     editA.value.trim(),
        difficulty: editDiff.value,
      });
      const idx = state.cards.findIndex(c => c.id === editingCardId);
      if (idx !== -1) state.cards[idx] = { ...state.cards[idx], ...updated };
      renderCards();
      closeEditModal();
      showToast("✏️ Kart güncellendi.", "success");
    } catch (err) {
      showToast(`❌ ${err.message}`, "error");
    }
  });
}

function openEditModal(card) {
  editingCardId    = card.id;
  editQ.value      = card.question;
  editA.value      = card.answer;
  editDiff.value   = card.difficulty;
  editModal.classList.add("open");
}

function closeEditModal() {
  editModal.classList.remove("open");
  editingCardId = null;
}

// ── Çalışma Modu ──────────────────────────────────────────────────────────────
function setupStudyButtons() {
  async function handleReview(wasCorrect) {
    const card = state.cards[state.studyIndex];
    if (!card) return;

    try {
      const res = await reviewCard(card.id, wasCorrect);
      
      if (wasCorrect) state.studyScore.correct++;
      else state.studyScore.incorrect++;

      const msg = wasCorrect 
        ? `Doğru! Sonraki tekrar: ${res.interval} gün sonra`
        : `Yanlış! Tekrar edilecek.`;
      showToast(msg, wasCorrect ? "success" : "warning");

      // Bir sonraki karta geç
      state.studyIndex++;
      renderStudyCard();
    } catch (err) {
      showToast("İnceleme kaydedilemedi.", "error");
    }
  }

  btnCorrect.addEventListener("click", () => handleReview(true));
  btnWrong.addEventListener("click", () => handleReview(false));

  btnNext.addEventListener("click", () => {
    stopSpeech();
    state.studyIndex = Math.min(state.studyIndex + 1, state.cards.length - 1);
    renderStudyCard();
  });

  btnPrev.addEventListener("click", () => {
    stopSpeech();
    state.studyIndex = Math.max(state.studyIndex - 1, 0);
    renderStudyCard();
  });

  studyCard.addEventListener("click", () => {
    const card = state.cards[state.studyIndex];
    if (card && card.card_type !== "mcq") {
      studyCard.classList.toggle("flipped");
    }
  });
}

/**
 * Kartları yükler ve çalışma modunu başlatır.
 * @param {boolean} dueOnly Yalnızca zamanı gelenleri mi getir?
 */
async function loadStudyCards(dueOnly = false) {
  if (!state.documentId) {
    // Eğer döküman seçili değilse listeden temiz başla
    state.cards = [];
    renderStudyCard();
    return;
  }

  try {
    const url = `/api/flashcards?document_id=${state.documentId}&is_duplicate=false&limit=100${dueOnly ? "&due_only=true" : ""}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Kartlar yüklenemedi.");
    const cards = await response.json();
    
    state.cards = cards;
    state.studyIndex = 0;
    state.studyScore = { correct: 0, incorrect: 0 };
    
    renderStudyCard();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.loadStudyCards = loadStudyCards;

function renderStudyCard() {
  const card = state.cards[state.studyIndex];
  
  // Elemanları her seferinde taze çekelim (Kritik: innerHTML değişimlerinden etkilenmez)
  const studyCard   = document.getElementById("study-card");
  const studyQ      = document.getElementById("study-question");
  const studyA      = document.getElementById("study-answer");
  const studyOpts   = document.getElementById("study-options");
  const studyProg   = document.getElementById("study-progress");
  const studyFinish = document.getElementById("study-finish");
  
  if (!studyCard || !studyQ) return;

  studyCard.classList.remove("flipped");
  if (studyProg) studyProg.textContent = `${state.studyIndex + 1} / ${state.cards.length}`;
  updateStudyScore();

  if (state.cards.length === 0) {
    studyCard.classList.remove("flipped", "no-flip");
    studyQ.textContent = "Henüz çalışılacak kart yok.";
    studyA.textContent = "İlk sekmeye gidip kart üretebilirsiniz.";
    if (studyFinish) studyFinish.style.display = "none";
    if (studyProg) studyProg.textContent = "0 / 0";
    return;
  }

  // Oturum Bitti mi?
  if (state.studyIndex >= state.cards.length) {
    if (studyFinish) studyFinish.style.display = "flex";
    if (studyProg) studyProg.textContent = `${state.cards.length} / ${state.cards.length}`;
    return;
  }

  if (studyFinish) studyFinish.style.display = "none";


  studyQ.innerHTML = `${escHtml(card?.question || "Soru bulunamadı")} <button class="tts-btn study-tts-btn" id="study-tts-q" title="Dinle">🔊</button>`;
  studyA.innerHTML = `${escHtml(card?.answer || "Cevap bulunamadı")} <button class="tts-btn study-tts-btn" id="study-tts-a" title="Dinle">🔊</button>`;
  studyOpts.innerHTML = "";

  const ttsQ = document.getElementById("study-tts-q");
  const ttsA = document.getElementById("study-tts-a");
  if (ttsQ && card) ttsQ.addEventListener("click", e => { e.stopPropagation(); speak(card.question); });
  if (ttsA && card) ttsA.addEventListener("click", e => { e.stopPropagation(); speak(card.answer); });

  if (card && card.card_type === "mcq") {
    let options = [];
    try {
      options = typeof card.options === "string"
        ? JSON.parse(card.options) : (card.options || []);
    } catch {}

    const correctIdx = card.correct_idx ?? 0;
    studyCard.classList.add("no-flip");
    options.forEach((opt, i) => {
      const btn = document.createElement("button");
      btn.className = "study-opt";
      btn.innerHTML = `<span style="font-weight: bold; margin-right: 0.5rem;">${String.fromCharCode(65 + i)})</span> ${escHtml(opt)}`;
      btn.addEventListener("click", e => {
        e.stopPropagation();
        studyOpts.querySelectorAll(".study-opt").forEach(b => b.disabled = true);
        btn.classList.add(i === correctIdx ? "opt-correct" : "opt-wrong");
        if (i !== correctIdx)
          studyOpts.querySelector(`.study-opt:nth-child(${correctIdx + 1})`).classList.add("opt-correct");
      });
      studyOpts.appendChild(btn);
    });
  } else {
    studyCard.classList.remove("no-flip");
  }
}

function nextStudyCard() {
  const total = getFilteredCards().length;
  if (state.studyIndex < total - 1) {
    state.studyIndex++;
    renderStudyCard();
  } else {
    studyQ.textContent = "🎉 Tur bitti!";
    studyA.textContent = "";
    studyOpts.innerHTML = "";
    updateStudyScore();
  }
}

function updateStudyScore() {
  if (!studyScore) return;
  const { correct, incorrect } = state.studyScore;
  const total = correct + incorrect;
  const pct   = total ? Math.round((correct / total) * 100) : 0;
  studyScore.textContent = `✅ ${correct}  ❌ ${incorrect}  |  ${pct}% doğru`;
}

// ── Yardımcılar ───────────────────────────────────────────────────────────────
function escHtml(str = "") {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
            .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

function showToast(msg, type = "info") {
  toast.textContent = msg;
  toast.className = `toast toast-${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3500);
}
