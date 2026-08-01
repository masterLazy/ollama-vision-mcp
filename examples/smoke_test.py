"""Smoke test for ollama-vision-mcp.

Verifies:
  1. Ollama is reachable at the configured base URL (`/v1/models`).
  2. The inbox directory is visible / created.
  3. A real vision call succeeds on the first image in the inbox (if any).

Run from the project root:
    python examples/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys

from ollama_vision_mcp.config import load_config
from ollama_vision_mcp.image_loader import list_image_files, load_image
from ollama_vision_mcp.vision_client import VisionClient

CWD = "."


async def main() -> int:
    config = load_config()
    print(f"config: base_url={config.base_url} model={config.model} inbox={config.inbox_dir}")

    client = VisionClient(config.base_url, config.api_key, config.model, config.max_tokens)

    # 1) Connectivity + available models
    health = await client.health()
    print(f"ollama health: ok={health['ok']}")
    if not health["ok"]:
        print(f"  error: {health['error']}")
        print("  -> Start Ollama with `ollama serve` first.")
        await client.aclose()
        return 1
    print(f"  available models ({len(health['models'])}): {health['models']}")
    if config.model not in health["models"]:
        print(f"  NOTE: configured model '{config.model}' not found. Pull it with:")
        print(f"    ollama pull {config.model}")

    # 2) Inbox
    inbox = list_image_files(config.inbox_dir, CWD, create_if_missing=True)
    print(f"inbox images ({config.inbox_dir}): {len(inbox)}")
    for p in inbox:
        print(f"  - {p}")

    # 3) Real vision call on the first inbox image
    if not inbox:
        print("No image in inbox to describe. Drop a screenshot into the inbox and rerun.")
        await client.aclose()
        return 0
    path = inbox[0]
    data_url, mime = load_image(path, CWD, compress=config.compress)
    print(f"describing: {path} (mime={mime}, data_url_len={len(data_url)})")
    text = await client.chat(data_url, "Describe this image briefly.")
    print(f"vision response:\n{text[:500]}")

    await client.aclose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
