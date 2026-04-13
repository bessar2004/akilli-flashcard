/**
 * js/tts.js
 * Browser Speech Synthesis API (Metin-Ses Dönüştürücü) modülü.
 */

let currentUtterance = null;

/**
 * Verilen metni sesli okur.
 * @param {string} text Okunacak metin.
 */
export function speak(text) {
  if (!text) return;

  // Eğer zaten bir şey okunuyorsa durdur
  stopSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  
  // Basit Dil Algılama (Türkçe karakterler varsa Türkçe, yoksa İngilizce için ipucu)
  const isTurkish = /[çğıöşüÇĞİÖŞÜ]/.test(text) || text.length > 20; // Türkçe karakter varsa veya uzunsa (varsayılan TR)
  utterance.lang = isTurkish ? 'tr-TR' : 'en-US';

  // Ses ayarları
  utterance.rate = 1.0;  // Hız
  utterance.pitch = 1.0; // Ses tonu

  // Mevcut dillerden en iyisini seçmeye çalış
  const voices = window.speechSynthesis.getVoices();
  if (voices.length > 0) {
    const preferredVoice = voices.find(v => v.lang.startsWith(utterance.lang) && v.localService) 
                        || voices.find(v => v.lang.startsWith(utterance.lang));
    if (preferredVoice) utterance.voice = preferredVoice;
  }

  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

/**
 * Seslendirmeyi durdurur.
 */
export function stopSpeech() {
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
  }
}
