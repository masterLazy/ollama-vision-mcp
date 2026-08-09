"""Configuration for ollama-vision-mcp.

Pure bridge: this package never manages Ollama. It only reads configuration
from environment variables and talks to Ollama over HTTP.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5vl:7b"
DEFAULT_INBOX = ".ai/inbox"
DEFAULT_MAX_TOKENS = 2048
# Thinking models (e.g. qwen3.5) burn output tokens on a `reasoning` trace and
# frequently return empty `content`; disable thinking by default.
DEFAULT_THINK = False


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    inbox_dir: str
    max_tokens: int
    compress: bool
    think: bool


def _first(*keys: str, default: str) -> str:
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    return default


def load_config() -> Config:
    base_url = _first(
        "VISION_MCP_BASE_URL",
        "VISION_BASE_URL",
        default=DEFAULT_BASE_URL,
    ).rstrip("/")

    api_key = _first("VISION_MCP_API_KEY", "VISION_API_KEY", default="")

    model = _first(
        "VISION_MCP_MODEL",
        "VISION_MODEL",
        default=DEFAULT_MODEL,
    )

    inbox_dir = _first(
        "VISION_MCP_INBOX",
        "VISION_INBOX",
        default=DEFAULT_INBOX,
    )

    try:
        max_tokens = int(os.environ.get("VISION_MCP_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS

    compress = os.environ.get("VISION_MCP_COMPRESS", "1") != "0"

    think_raw = os.environ.get("VISION_MCP_THINK", "0").strip().lower()
    think = think_raw not in ("", "0", "false", "no", "off")

    return Config(
        base_url=base_url,
        api_key=api_key,
        model=model,
        inbox_dir=inbox_dir,
        max_tokens=max_tokens,
        compress=compress,
        think=think,
    )
