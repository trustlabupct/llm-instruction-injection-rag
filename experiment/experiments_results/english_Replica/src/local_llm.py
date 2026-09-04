"""Access to the generative model.

Single backend: Ollama (a real local model via its HTTP API at http://localhost:11434).
This is the backend with which all the thesis results are produced. The URL is
configurable via environment variables (OLLAMA_URL / OLLAMA_HOST) to point to the
service in Docker.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Configurable via environment variables so it can point to the Ollama service in Docker.
# Accepts OLLAMA_URL (full /api/chat endpoint) or OLLAMA_HOST (host:port only).
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
        except urllib.error.HTTPError as e:
            # Ollama IS reachable but returned an error status; show its actual message
            # instead of masking it behind a generic "unreachable" error.
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Ollama returned HTTP {e.code} for model '{self.model}': {body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                "Could not reach Ollama at localhost:11434. "
                "Check that 'ollama serve' is running and that the model has been pulled."
            ) from e


def get_llm(backend: str = "ollama", **kwargs):
    if backend == "ollama":
        return OllamaLLM(**kwargs)
    raise ValueError(f"unknown backend: {backend!r} (only 'ollama' is supported)")