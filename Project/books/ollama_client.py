import json
import requests
from dataclasses import dataclass
from typing import Any, Generator


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
            "options": {
                "num_predict": self._config.max_tokens,
                "temperature": self._config.temperature,
                "num_ctx": self._config.num_ctx,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self._config.timeout)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            raise OllamaError(f"Ollama API request failed: {e}")

    def stream_generate(self, prompt: str) -> Generator[str, None, None]:
        """Yields chunks of the generated response."""
        if not prompt.strip():
            raise OllamaError("Prompt is empty")

        url = f"{self._config.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._config.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": self._config.max_tokens,
                "temperature": self._config.temperature,
                "num_ctx": self._config.num_ctx,
            },
        }

        try:
            response = requests.post(url, json=payload, stream=True, timeout=self._config.timeout)
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    if "response" in chunk:
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
        except Exception as e:
            raise OllamaError(f"Ollama Streaming failed: {e}")
