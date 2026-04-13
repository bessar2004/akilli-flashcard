/**
 * js/quiz.js
 * Quiz (Sınav) modu kontrolcüsü.
 *
 * Akış:
 *   1. Kullanıcı "Sınav Başlat" der → /api/quiz/generate çağırılır
 *   2. Sorular sırayla gösterilir (MCQ tıklanabilir, QA metin input)
 *   3. Son soruda "Sınavı Bitir" → /api/quiz/submit çağırılır
 *   4. Özet Sonuç ekranı gösterilir (Puan, Doğru Sayısı, Harf Notu)
 *   5. "Detayları Gör" butonuyla adım adım detay inceleme ekranı açılır
 */

const QUIZ_API = `${window.location.origin}/api`;
import { speak, stopSpeech } from "./tts.js";

// ── State ──────────────────────────────────────────────────────────────────
let quizState = {
  questions:    [],
  answers:      [],        // { card_id, card_type, answer_text?, answer_idx? }
  currentIndex: 0,
  sessionId:    null,
  isRunning:    false,
};

let resultState = {
  details: [],
  currentIndex: 0
};

// ── DOM elemanları ──────────────────────────────────────────────────────────
const screen   = id => document.getElementById(id);

// Setup ekranı
const setupScreen    = screen("quiz-setup");
const docIdInput     = screen("quiz-doc-id");
const countInput     = screen("quiz-count");
const diffSelect     = screen("quiz-diff");
const typeSelect     = screen("quiz-type");
const startBtn       = screen("quiz-start-btn");
const setupError     = screen("quiz-setup-error");

// Soru ekranı
const questionScreen = screen("quiz-question-screen");
const qProgress      = screen("quiz-q-progress");
const qDifficulty    = screen("quiz-q-difficulty");
const qType          = screen("quiz-q-type");
const qText          = screen("quiz-q-text");
const qMcqOpts       = screen("quiz-mcq-opts");
const qaInput        = screen("quiz-qa-input");
const btnPrevQ       = screen("quiz-btn-prev");
const btnNextQ       = screen("quiz-btn-next");
const btnSubmit      = screen("quiz-btn-submit");

// Sonuç ekranı (Özet)
const resultScreen   = screen("quiz-result-screen");
const resScore       = screen("quiz-res-score");
const resGrade       = screen("quiz-res-grade");
const resCorrect     = screen("quiz-res-correct");
const resTotal       = screen("quiz-res-total");
const resBar         = screen("quiz-res-bar");
const btnRetry       = screen("quiz-btn-retry");
const btnShowDetails = screen("quiz-btn-show-details");

// Sonuç ekranı (Detay / Adım Adım)
const stepDetailsScreen = screen("quiz-step-details-screen");
const detailProgress    = screen("quiz-detail-progress");
const btnBackToSummary  = screen("quiz-btn-back-to-summary");
const detailCard        = screen("quiz-detail-card");
const detailBtnPrev     = screen("quiz-detail-btn-prev");
const detailBtnNext     = screen("quiz-detail-btn-next");
const detailActionsEnd  = screen("quiz-detail-actions-end");
const detailBtnRetry    = screen("quiz-detail-btn-retry");
const detailBtnBack     = screen("quiz-detail-btn-back");

// ── Ekran Kontrolü ─────────────────────────────────────────────────────────
function switchView(activeScreen) {
  const allScreens = [setupScreen, questionScreen, resultScreen, stepDetailsScreen];
  allScreens.forEach(s => {
    if (s) s.classList.add("hidden");
  });
  if (activeScreen) {
    activeScreen.classList.remove("hidden");
  }
}

import { listDocuments } from "./api.js";

// ── Başlatma ────────────────────────────────────────────────────────────────
export function initQuiz() {
  startBtn.addEventListener("click",  handleStart);
  btnPrevQ.addEventListener("click",  () => navigate(-1));
  btnNextQ.addEventListener("click",  () => navigate(+1));
  btnSubmit.addEventListener("click", handleSubmit);
  
  // Özet ekranından
  btnRetry.addEventListener("click",  resetQuiz);
  btnShowDetails.addEventListener("click", showStepDetails);

  // Detay ekranından
  btnBackToSummary.addEventListener("click", backToSummary);
  detailBtnPrev.addEventListener("click", () => navigateDetails(-1));
  detailBtnNext.addEventListener("click", () => navigateDetails(+1));
  detailBtnRetry.addEventListener("click", resetQuiz);
  detailBtnBack.addEventListener("click", backToSummary);

  // İlk yükleme
  loadQuizDocuments();
}

/**
 * Mevcut dokümanları API'den çeker ve dropdown'ı doldurur.
 */
export async function loadQuizDocuments() {
  try {
    const docs = await listDocuments();
    // Mevcut seçimi korumak için (opsiyonel)
    const currentVal = docIdInput.value;
    
    // Temizle (ilk "Hepsini Seç" opsiyonunu koru)
    docIdInput.innerHTML = '<option value="">Tüm Kayıtlı Kartlar (Karışık)</option>';
    
    docs.forEach(doc => {
      const opt = document.createElement("option");
      opt.value = doc.id;
      opt.textContent = `${doc.title} (${doc.filename || 'Metin'})`;
      docIdInput.appendChild(opt);
    });

    if (currentVal) docIdInput.value = currentVal;
  } catch (err) {
    console.error("Doküman listesi yüklenemedi:", err);
  }
}

// ── Sınav Başlat ────────────────────────────────────────────────────────────
async function handleStart() {
  setupError.textContent = "";
  startBtn.disabled      = true;
  startBtn.textContent   = "⏳ Hazırlanıyor...";

  const body = {
    count:   parseInt(countInput.value) || 10,
    shuffle: true,
  };
  const docId = docIdInput.value.trim();
  if (docId) body.document_id = parseInt(docId);
  if (diffSelect.value) body.difficulty = diffSelect.value;
  if (typeSelect.value) body.card_type  = typeSelect.value;

  try {
    const res = await fetch(`${QUIZ_API}/quiz/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || data.detail || `HTTP ${res.status}`);

    quizState.questions    = data.questions;
    quizState.sessionId    = data.session_id;
    quizState.answers      = data.questions.map(q => ({
      card_id:     q.card_id,
      card_type:   q.card_type,
      answer_text: null,
      answer_idx:  null,
    }));
    quizState.currentIndex = 0;
    quizState.isRunning    = true;

    switchView(questionScreen);
    renderQuestion();
  } catch (err) {
    setupError.textContent = `❌ ${err.message}`;
  } finally {
    startBtn.disabled    = false;
    startBtn.textContent = "🚀 Sınavı Başlat";
  }
}

// ── Soru Render ─────────────────────────────────────────────────────────────
function renderQuestion() {
  const q    = quizState.questions[quizState.currentIndex];
  const ans  = quizState.answers[quizState.currentIndex];
  const idx  = quizState.currentIndex;
  const total= quizState.questions.length;

  // İlerleme
  qProgress.textContent = `Soru ${idx + 1} / ${total}`;
  updateProgressBar(idx + 1, total, "quiz-progress-bar");

  // Badges
  const diffMap = { easy:"🟢 Kolay", medium:"🟡 Orta", hard:"🔴 Zor" };
  qDifficulty.textContent = diffMap[q.difficulty] || q.difficulty;
  qType.textContent       = q.card_type === "mcq" ? "MCQ" : "QA";
  qType.className = `quiz-badge badge-type`;
  qDifficulty.className   = `quiz-badge diff-${q.difficulty}`;

  // Soru metni
  qText.innerHTML = `${escHtml(q.question)} <button class="tts-btn quiz-tts-btn" id="quiz-tts-q" title="Dinle">🔊</button>`;
  document.getElementById("quiz-tts-q").addEventListener("click", e => { e.stopPropagation(); speak(q.question); });

  // MCQ / QA içeriği
  if (q.card_type === "mcq" && q.options?.length) {
    qMcqOpts.classList.remove("hidden");
    qaInput.classList.add("hidden");
    renderMcqOptions(q, ans.answer_idx);
  } else {
    qMcqOpts.classList.add("hidden");
    qaInput.classList.remove("hidden");
    qaInput.value = ans.answer_text || "";
  }

  // Butonlar
  btnPrevQ.disabled   = idx === 0;
  btnNextQ.classList.toggle("hidden",   idx >= total - 1);
  btnSubmit.classList.toggle("hidden",  idx <  total - 1);
}

function renderMcqOptions(q, selectedIdx) {
  qMcqOpts.innerHTML = "";
  q.options.forEach((opt, i) => {
    const btn = document.createElement("button");
    btn.className = `quiz-opt${i === selectedIdx ? " selected" : ""}`;
    btn.innerHTML = `<span class="opt-label">${String.fromCharCode(65 + i)})</span> ${escHtml(opt)}`;
    btn.addEventListener("click", () => {
      const currentAns = quizState.answers[quizState.currentIndex];
      currentAns.answer_idx = i;
      currentAns.answer_text = opt; // Backend'de metin bazlı doğrulama için gerekli
      renderMcqOptions(q, i);
    });
    qMcqOpts.appendChild(btn);
  });
}

function updateProgressBar(current, total, barId) {
  const bar = document.getElementById(barId);
  if (bar) bar.style.width = `${(current / total) * 100}%`;
}

// ── Navigasyon ───────────────────────────────────────────────────────────────
function navigate(dir) {
  stopSpeech();
  saveCurrentAnswer();
  quizState.currentIndex = Math.max(0,
    Math.min(quizState.currentIndex + dir, quizState.questions.length - 1));
  renderQuestion();
}

function saveCurrentAnswer() {
  const q   = quizState.questions[quizState.currentIndex];
  const ans = quizState.answers[quizState.currentIndex];
  if (q.card_type !== "mcq") {
    ans.answer_text = qaInput.value.trim() || null;
    ans.answer_idx  = null;
  }
  // MCQ için answer_idx zaten butona tıklandıkça kaydediliyor
}

// ── Sınavı Bitir & Gönder ────────────────────────────────────────────────────
async function handleSubmit() {
  saveCurrentAnswer();

  // Boş cevapları kontrol et
  const unanswered = quizState.answers.filter(a =>
    a.answer_idx === null && !a.answer_text
  ).length;

  if (unanswered > 0) {
    const go = confirm(`${unanswered} soru cevaplanmadı. Yine de göndermek istiyor musunuz?`);
    if (!go) return;
  }

  btnSubmit.disabled    = true;
  btnSubmit.textContent = "⏳ Değerlendiriliyor...";

  const payload = {
    answers: quizState.answers.map(a => ({
      card_id:     a.card_id,
      card_type:   a.card_type,
      answer_text: a.answer_text || undefined,
      answer_idx:  a.answer_idx  ?? undefined,
    })),
  };

  try {
    const res = await fetch(`${QUIZ_API}/quiz/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.message || result.detail || `HTTP ${res.status}`);

    // Sonuç verilerini state'e al
    resultState.details = result.details;
    resultState.currentIndex = 0;
    
    renderResultSummary(result);
  } catch (err) {
    alert(`❌ Gönderim hatası: ${err.message}`);
  } finally {
    btnSubmit.disabled    = false;
    btnSubmit.textContent = "✅ Sınavı Bitir";
  }
}

// ── Sonuç Ekranı (Özet) ─────────────────────────────────────────────────────
const gradeColors = { A:"#22c55e", B:"#84cc16", C:"#eab308", D:"#f97316", F:"#ef4444" };

function renderResultSummary(result) {
  switchView(resultScreen);

  const pct   = result.score_pct;
  const grade = result.grade;

  // Puan & not
  resScore.textContent    = `${pct}%`;
  resScore.style.color    = gradeColors[grade] || "#e8eaf0";
  resGrade.textContent    = grade;
  resGrade.style.color    = gradeColors[grade] || "#e8eaf0";
  resCorrect.textContent  = result.correct;
  resTotal.textContent    = result.total;

  // Animasyonlu bar
  resBar.style.width      = "0%";
  resBar.style.background = gradeColors[grade] || "#6c63ff";
  setTimeout(() => { resBar.style.width = `${pct}%`; }, 50);
}

// ── Sonuç Ekranı (Detay Adım Adım) ────────────────────────────────────────────────
function showStepDetails() {
  switchView(stepDetailsScreen);
  resultState.currentIndex = 0;
  renderDetailScreen();
}

function backToSummary() {
  switchView(resultScreen);
}

function navigateDetails(dir) {
  resultState.currentIndex = Math.max(0,
    Math.min(resultState.currentIndex + dir, resultState.details.length - 1));
  renderDetailScreen();
}

function renderDetailScreen() {
  const details = resultState.details;
  const idx = resultState.currentIndex;
  const total = details.length;
  const d = details[idx];

  // Başlık / İlerleme
  detailProgress.textContent = `Detay ${idx + 1} / ${total}`;

  // Kart İçeriği
  detailCard.className = `panel-box quiz-detail-item ${d.is_correct ? "detail-correct" : "detail-wrong"}`;
  detailCard.innerHTML = `
    <div class="detail-header" style="margin-bottom: 1.5rem;">
      <span class="detail-num" style="font-size: 1.2rem;">S${idx + 1}</span>
      <span class="detail-icon" style="font-size: 1.5rem;">${d.is_correct ? "✅" : "❌"}</span>
      <span class="detail-difficulty diff-pill diff-${d.difficulty}">${d.difficulty}</span>
    </div>
    
    <div class="detail-question" style="font-size: 1.1rem; margin-bottom: 2rem;">
      ${escHtml(d.question)}
    </div>
    
    <div class="detail-answers">
      ${d.card_type === 'mcq' || d.options ? renderDetailMcqOptions(d) : `
        <div style="background: var(--surface); padding: 1.2rem; border-radius: 8px; border: 1px solid var(--border);">
          <div style="margin-bottom: ${d.is_correct ? '0' : '1rem'};">
            <span class="detail-label" style="display: block; margin-bottom: 0.3rem; font-size: 0.8rem; color: var(--text-muted);">Senin cevabın:</span>
            <span class="detail-user ${d.is_correct ? "ans-correct" : "ans-wrong"}" style="font-size: 1.05rem; font-weight: 500;">
              ${escHtml(d.user_answer || "(boş)")}
            </span>
          </div>
          
          ${!d.is_correct ? `
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
              <span class="detail-label" style="display: block; margin-bottom: 0.3rem; font-size: 0.8rem; color: var(--text-muted);">Doğru cevap:</span>
              <span class="detail-correct-ans" style="font-size: 1.05rem; color: var(--green); font-weight: 500;">
                ${escHtml(d.correct_answer)}
              </span>
            </div>
          ` : ""}
        </div>
      `}
    </div>
  `;

  // Butonları Yönet
  detailBtnPrev.disabled = (idx === 0);
  detailBtnNext.classList.toggle("hidden", idx >= total - 1);
  detailActionsEnd.classList.toggle("hidden", idx < total - 1);
}


// ── Tekrar ─────────────────────────────────────────────────────────────────
function resetQuiz() {
  quizState = { questions:[], answers:[], currentIndex:0, sessionId:null, isRunning:false };
  resultState = { details:[], currentIndex:0 };
  
  switchView(setupScreen);
  setupError.textContent = "";
}

function renderDetailMcqOptions(d) {
  if (!d.options || !d.options.length) return `<p>Seçenek bulunamadı.</p>`;
  
  return d.options.map((opt, i) => {
    let stateClass = "";
    if (i === d.correct_idx) stateClass = "correct";
    else if (i === d.user_idx && !d.is_correct) stateClass = "wrong";
    
    return `
      <div class="quiz-opt ${stateClass}" style="margin-bottom: 0.6rem; cursor: default;">
        <span style="font-weight: bold; margin-right: 0.5rem;">${String.fromCharCode(64 + (i+1))})</span>
        ${escHtml(opt)}
      </div>
    `;
  }).join('');
}

// ── Yardımcı ───────────────────────────────────────────────────────────────
function escHtml(str = "") {
  if (typeof str !== 'string') return "";
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
            .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
