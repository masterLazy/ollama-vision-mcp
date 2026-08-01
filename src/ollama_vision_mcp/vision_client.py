"""OpenAI-compatible vision client — pure HTTP bridge to a local Ollama server.

This module never manages Ollama (no install / serve / pull). It only talks to
Ollama's OpenAI-compatible endpoints: `/v1/chat/completions` and `/v1/models`.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(180.0, connect=10.0)


class VisionError(RuntimeError):
    """Raised when the vision backend cannot produce a result."""


class VisionClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "qwen2.5vl:7b",
        max_tokens: int = 2048,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "ollama"  # Ollama ignores the key but expects the field
        self.model = model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def health(self) -> dict[str, Any]:
        """Probe `/v1/models` and list locally available models.

        Returns {"ok": bool, "models": [...], "error": "..."} — never raises.
        """
        try:
            resp = await self._client.get(
                f"{self.base_url}/models", headers=self._headers()
            )
        except Exception as e:  # network / connection refused
            return {"ok": False, "models": [], "error": str(e)}
        if resp.status_code != 200:
            return {
                "ok": False,
                "models": [],
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        data = resp.json()
        models = [m.get("id", "") for m in data.get("data", [])]
        return {"ok": True, "models": models, "error": ""}

    async def chat(self, data_url: str, prompt: str, temperature: float = 0.2) -> str:
        """Send one image (as a data URL) plus a text prompt to the vision model."""
        body = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }

        try:
            resp = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
        except httpx.HTTPError as e:
            raise VisionError(
                f"Failed to reach vision API at {self.base_url}. "
                f"Is Ollama running? (ollama serve) — {e}"
            ) from e

        if resp.status_code == 404 and "not found" in resp.text.lower():
            raise VisionError(
                f"Model '{self.model}' is not available locally. "
                f"Pull it with: ollama pull {self.model}"
            )

        if resp.status_code != 200:
            raise VisionError(
                f"Vision API HTTP {resp.status_code}: {resp.text[:400]}"
            )

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise VisionError("Vision API returned no choices")
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        content = (content or "").strip()
        if not content:
            raise VisionError("Vision API returned empty content")
        return content
