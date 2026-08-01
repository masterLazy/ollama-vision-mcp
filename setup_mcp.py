#!/usr/bin/env python3
"""Thin launcher: lets `python setup_mcp.py` work before the package is installed.

Adds the local `src/` tree to sys.path and delegates to the real setup module
(`ollama_vision_mcp.setup_mcp`), which also ships as the `ollama-vision-setup`
console script after `pip install -e .`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ollama_vision_mcp.setup_mcp import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
