/**
 * js/theme.js
 * Karanlık / Aydınlık Mod yönetim sistemi.
 * Kullanıcı tercihlerini saklar ve uygular.
 */

const THEME_KEY = "flashcard_theme";

/**
 * Temayı başlatır (load anında çağrılmalı).
 */
export function initTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY);
  // Kayıtlı tema yoksa sistem tercihine bak
  const defaultTheme = savedTheme || 
    (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  
  applyTheme(defaultTheme);
}

/**
 * Temayı değiştirir.
 */
export function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const target = current === "dark" ? "light" : "dark";
  applyTheme(target);
}

/**
 * Temayı uygular ve kaydeder.
 * @param {'light'|'dark'} theme 
 */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
  updateToggleIcon(theme);
}

/**
 * Toggle butonu ikonunu günceller.
 */
function updateToggleIcon(theme) {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.innerHTML = theme === "dark" ? "🌙" : "☀️";
  btn.title = theme === "dark" ? "Aydınlık Moda Geç" : "Karanlık Moda Geç";
}
