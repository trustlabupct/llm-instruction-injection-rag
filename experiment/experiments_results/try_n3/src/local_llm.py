"""Acceso al modelo generativo.

Backend unico: Ollama (modelo local real via su API HTTP en http://localhost:11434).
Es el backend con el que se producen todos los resultados del TFG. La URL es
configurable por entorno (OLLAMA_URL / OLLAMA_HOST) para apuntar al servicio en Docker.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Configurable por entorno para poder apuntar al servicio de Ollama en Docker.
# Acepta OLLAMA_URL (endpoint /api/chat completo) o OLLAMA_HOST (solo host:puerto).
_host = os.environ.get("OLLAMA_HOST")
OLLAMA_URL = os.environ.get(
    "OLLAMA_URL",
    (f"{_host.rstrip('/')}/api/chat" if _host else "http://localhost:11434/api/chat"),
)


class OllamaLLM:
    def __init__(self, model: str = "llama3.1:8b", temperature: float = 0.0,
                 seed: int = 42, num_ctx: int = 8192, timeout: int = 180):
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.num_ctx = num_ctx
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def generate(self, system_prompt: str, user_prompt: str, **_) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": self.temperature,
                        "seed": self.seed,
                        "num_ctx": self.num_ctx},
        }
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())["message"]["content"]
        except urllib.error.URLError as e:
            raise RuntimeError(
                "No se pudo contactar con Ollama en localhost:11434. "
                "Comprueba que 'ollama serve' esta en marcha y que el modelo esta descargado."
            ) from e


def get_llm(backend: str = "ollama", **kwargs):
    if backend == "ollama":
        return OllamaLLM(**kwargs)
    raise ValueError(f"backend desconocido: {backend!r} (solo se admite 'ollama')")
