from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any


class OllamaError(Exception):
    """Raised when the Ollama API fails or returns invalid data."""


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    model: str
    timeout: float
    max_tokens: int
    temperature: float
    num_ctx: int


class OllamaClient:
    def __init__(self, config: OllamaConfig) -> None:
        self._config = config

    def generate(self, prompt: str) -> str:
        if not prompt.strip():
            raise OllamaError("Prompt is empty")

        url = f"{self._config.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "num_predict": self._config.max_tokens,
                "temperature": self._config.temperature,
                "num_ctx": self._config.num_ctx,
            },
        }

        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - depends on network
            raise OllamaError("Failed to reach Ollama") from exc

        try:
            data: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OllamaError("Invalid JSON from Ollama") from exc

        text = data.get("response")
        if not isinstance(text, str):
            raise OllamaError("Missing response text from Ollama")

        return text
