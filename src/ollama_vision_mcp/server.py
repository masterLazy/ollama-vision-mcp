"""ollama-vision-mcp MCP server — minimal local vision bridge.

Exposes four tools over MCP stdio for VS Code Copilot (Agent mode):
  - describe_image : read a local image -> text description (via local Ollama)
  - list_images    : list image files in the inbox directory
  - extract_text   : OCR a local image verbatim
  - vision_status  : show config + Ollama connectivity / available models

This is a pure bridge: Ollama installation, `ollama serve`, and model pulls
are the user's responsibility.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Literal

from mcp.server.mcpserver import MCPServer

from .config import Config, load_config
from .image_loader import list_image_files, load_image
from .vision_client import VisionClient, VisionError

SERVER_NAME = "ollama-vision-mcp"
SERVER_VERSION = "0.1.0"

# English prompts per analysis mode (tailored for small local models).
PROMPTS = {
    "general": (
        "Describe this image in full detail for a text-only agent. Include ALL "
        "visible text verbatim, UI elements, errors, diagrams, colors and "
        "layout. Use Markdown. Be factual."
    ),
    "ocr": (
        "Extract ALL visible text verbatim. Preserve line breaks. Include "
        "buttons, errors, code and captions. If there is no text: "
        "[no text detected]."
    ),
    "ui": (
        "Decompose this UI screenshot: layout, components, buttons, inputs, "
        "errors, URLs and states. Use a Markdown list."
    ),
    "diagram": (
        "Analyze this technical diagram (flowchart / ERD / architecture / "
        "wireframe). Return its type, nodes, edges, labels and a summary. "
        "Use Markdown bullets."
    ),
}


Mode = Literal["general", "ocr", "ui", "diagram"]


def _prompt_for(mode: str, question: str | None) -> str:
    prompt = PROMPTS.get(mode, PROMPTS["general"])
    if question:
        prompt = f"{prompt}\nQuestion: {question}"
    return prompt


def create_server(config: Config, client: VisionClient) -> MCPServer:
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        description=(
            "Minimal local vision bridge: read local images and get text "
            "descriptions from a local Ollama vision model."
        ),
    )

    @server.tool()
    async def describe_image(
        path: str,
        mode: Mode = "general",
        question: str | None = None,
    ) -> str:
        """Read a local image and return a text description from the local Ollama vision model.

        Use when the user references a screenshot or image you cannot see.
        `path` is absolute, or relative to the project directory.
        """
        try:
            cwd = os.getcwd()
            data_url, _ = load_image(path, cwd, compress=config.compress)
            return await client.chat(data_url, _prompt_for(mode, question))
        except (FileNotFoundError, NotADirectoryError, ValueError, VisionError) as e:
            return f"Error: {e}"
        except Exception as e:  # keep the server alive on unexpected failures
            return f"Unexpected error: {e}"

    @server.tool()
    async def list_images(directory: str | None = None) -> str:
        """List image files in a directory.

        Defaults to the configured inbox folder where the user drops
        screenshots. Use this before describe_image to find what is available.
        """
        try:
            cwd = os.getcwd()
            target = directory or config.inbox_dir
            create_if_missing = directory is None
            files = list_image_files(target, cwd, create_if_missing=create_if_missing)
            if not files:
                return (
                    f"No images found in {target}. "
                    "Drop a screenshot there, then call list_images again."
                )
            body = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(files))
            return f"Images in {target}:\n{body}"
        except (FileNotFoundError, NotADirectoryError, ValueError) as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    @server.tool()
    async def extract_text(path: str) -> str:
        """Extract all visible text (OCR) from a local image verbatim.

        Use for code screenshots, terminal output, or error dialogs.
        """
        try:
            cwd = os.getcwd()
            data_url, _ = load_image(path, cwd, compress=config.compress)
            return await client.chat(data_url, _prompt_for("ocr", None))
        except (FileNotFoundError, NotADirectoryError, ValueError, VisionError) as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    @server.tool()
    async def vision_status() -> str:
        """Show bridge configuration and Ollama connectivity / available models."""
        try:
            health = await client.health()
        except Exception as e:  # pragma: no cover - defensive
            health = {"ok": False, "models": [], "error": str(e)}
        status = {
            "server": f"{SERVER_NAME} v{SERVER_VERSION}",
            "base_url": config.base_url,
            "model": config.model,
            "inbox_dir": config.inbox_dir,
            "max_tokens": config.max_tokens,
            "compress": config.compress,
            "think": config.think,
            "ollama": health,
        }
        return json.dumps(status, ensure_ascii=False, indent=2)

    return server


def run() -> None:
    """Entry point (console script and `python -m ollama_vision_mcp`)."""
    config = load_config()
    client = VisionClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        max_tokens=config.max_tokens,
        think=config.think,
    )
    server = create_server(config, client)

    # Best-effort startup hint (stdout is reserved for the MCP protocol).
    # IMPORTANT: probe with a SEPARATE throwaway client, not the shared one.
    # asyncio.run() creates a fresh event loop and closes it afterwards; if the
    # shared client were used here, its httpx.AsyncClient would bind to that
    # closed loop and every later tool call would fail with
    # "Event loop is closed" (cold-start bug).
    async def _probe() -> dict:
        probe = VisionClient(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            think=config.think,
        )
        try:
            return await probe.health()
        finally:
            await probe.aclose()

    try:
        health = asyncio.run(_probe())
        if not health["ok"]:
            print(
                f"[{SERVER_NAME}] Warning: cannot reach {config.base_url} "
                f"({health['error']}). Start Ollama with `ollama serve` and pull a "
                f"vision model: `ollama pull {config.model}`.",
                file=sys.stderr,
            )
    except Exception:
        pass

    try:
        server.run(transport="stdio")
    finally:
        try:
            asyncio.run(client.aclose())
        except Exception:
            pass
