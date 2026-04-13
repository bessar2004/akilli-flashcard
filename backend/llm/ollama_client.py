"""
llm/ollama_client.py
----------------------
Ollama REST API ile iletişimi yöneten düşük seviyeli istemci.

Varsayılan ayarlar:
  endpoint : http://localhost:11434
  model    : gemma3:1b

Kullanılan endpoint:
  POST /api/generate   →  tek seferlik (non-streaming) yanıt
  GET  /api/tags       →  yüklü modellerin listesi

Bağımlılık:
  pip install httpx      (async destekli HTTP istemcisi)
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Varsayılan Sabitler ───────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL   = "gemma3:1b"
DEFAULT_TIMEOUT = 120          # saniye — uzun metinlerde LLM yavaş olabilir


class OllamaClient:
    """
    Ollama API için senkron HTTP istemcisi.

    Örnek kullanım:
        client = OllamaClient()
        response = client.generate("Fotosentezi açıkla.")
        print(response)
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str    = DEFAULT_MODEL,
        timeout: int  = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self.timeout  = timeout

    # ── Temel Üretim ─────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float       = 0.9,
        max_tokens: int    = 2048,
    ) -> str:
        """
        Ollama /api/generate endpoint'ini çağırır.

        Args:
            prompt:        Kullanıcı komutu (ders notu vb.)
            system_prompt: Model kişiliği / görev tanımı (opsiyonel).
            temperature:   Yaratıcılık seviyesi (0: deterministik, 1: yaratıcı).
            top_p:         Nucleus sampling eşiği.
            max_tokens:    Maksimum üretilecek token sayısı.

        Returns:
            LLM'in ürettiği ham metin yanıtı.

        Raises:
            ConnectionError:  Ollama sunucusuna bağlanılamazsa.
            ValueError:       Yanıt ayrıştırılamazsa.
            RuntimeError:     API hata kodu dönerse.
        """
        payload = {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,          # Tek blokta yanıt al
            "options": {
                "temperature": temperature,
                "top_p":       top_p,
                "num_predict": max_tokens,
            },
        }

        # System prompt varsa ekle
        if system_prompt:
            payload["system"] = system_prompt

        url = f"{self.base_url}/api/generate"
        logger.debug("Ollama isteği gönderiliyor → model=%s, url=%s", self.model, url)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Ollama sunucusuna bağlanılamadı: {self.base_url}\n"
                "Ollama'nın çalıştığından emin olun: 'ollama serve'"
            )
        except httpx.TimeoutException:
            raise TimeoutError(
                f"Ollama {self.timeout}s içinde yanıt döndürmedi. "
                "Daha büyük bir timeout değeri veya daha küçük bir metin deneyin."
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama API hatası [{e.response.status_code}]: {e.response.text}")

        # Yanıtı ayrıştır
        try:
            data = resp.json()
            response_text = data.get("response", "")
            logger.debug("Ollama yanıt uzunluğu: %d karakter", len(response_text))
            return response_text
        except Exception as e:
            raise ValueError(f"Ollama yanıtı JSON olarak ayrıştırılamadı: {e}")

    # ── Durum Kontrolü ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """
        Ollama sunucusunun çalışıp çalışmadığını kontrol eder.

        Returns:
            True — sunucu erişilebilir ve model yüklü.
            False — bağlantı hatası veya model bulunamadı.
        """
        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]

            # Model adı tam eşleşme veya prefix eşleşmesi
            match = any(
                m == self.model or m.startswith(self.model.split(":")[0])
                for m in models
            )
            if not match:
                logger.warning(
                    "Model '%s' bulunamadı. Yüklü modeller: %s",
                    self.model, models
                )
            return match
        except Exception as e:
            logger.warning("Ollama erişilebilirlik kontrolü başarısız: %s", e)
            return False

    def list_models(self) -> list[str]:
        """Ollama'da yüklü model adlarını döndürür."""
        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []


# ── Modül Düzeyinde Tekil (Singleton) İstemci ────────────────────────────────
# Tüm modüller bu tek örneği kullanır.
default_client = OllamaClient(
    base_url=OLLAMA_BASE_URL,
    model=DEFAULT_MODEL,
)
