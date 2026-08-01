# ollama-vision-mcp

[English](README.md) · [中文](README.zh-CN.md)

A minimal **local vision bridge** for text-only VS Code Copilot (e.g. DeepSeek).

Copilot with a text-only model cannot see images. This MCP server fills that gap:
you drop a screenshot into a folder, and Copilot reads the image through this
bridge, which sends it to a **local Ollama vision model** over HTTP and returns a
**text description** the text-only model can understand.

```
VS Code Copilot Chat (Agent mode, text-only model)
        │  MCP stdio
        ▼
ollama-vision-mcp (this package)
        │  reads local image → base64 → POST /v1/chat/completions
        ▼
Ollama (local vision model, e.g. qwen2.5vl:7b)
```

## What this tool is — and what it is NOT

This package is **only a bridge layer**. It talks to Ollama purely over HTTP
(OpenAI-compatible `/v1/chat/completions` and `/v1/models`).

It does **not**:
- install Ollama, start `ollama serve`, pull models, or manage model config;
- touch the clipboard, IDE internals, or network beyond your local Ollama server.

Ollama setup is entirely up to you (see [Prerequisites](#prerequisites)).

## Tools

| Tool            | Params                                  | Behavior                                        |
|-----------------|-----------------------------------------|-------------------------------------------------|
| `describe_image`| `path` (req), `mode?`, `question?`      | Read a local image → text description           |
| `list_images`   | `directory?` (default: inbox)           | List image files available for reading          |
| `extract_text`  | `path` (req)                            | OCR a local image verbatim                      |
| `vision_status` | —                                       | Show config + Ollama connectivity / models      |

`mode` is one of `general` (default), `ocr`, `ui`, `diagram`.

## Prerequisites (managed by you)

- **Python 3.10+**
- **Ollama** installed and running: `ollama serve`
- A **vision model** pulled, e.g.:
  ```bash
  ollama pull qwen2.5vl:7b
  ```
  Other options: `qwen3-vl:8b`, `gemma3:12b`, `llama3.2-vision:11b`, `llava:7b`.
  Pick one that fits your GPU. Configure it via `VISION_MCP_MODEL`.

## Install / build

```bash
cd ollama-vision-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -e .
```

## Register with VS Code Copilot

The server is launched as a stdio MCP server. There are two ways to register it,
depending on where you want it available. **In both cases Copilot Chat must be in
Agent mode** to use MCP tools.

### Option A — single project (`.vscode/mcp.json`)

Copy this into the project where you want to use it (adjust the python path):

```json
{
  "servers": {
    "ollama-vision": {
      "type": "stdio",
      "command": "D:/working/ollama-vision-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "ollama_vision_mcp"],
      "env": {
        "VISION_MCP_BASE_URL": "http://localhost:11434/v1",
        "VISION_MCP_MODEL": "qwen2.5vl:7b",
        "VISION_MCP_INBOX": ".agents/inbox"
      }
    }
  }
}
```

Then **Reload Window** (Ctrl+Shift+P → "Developer: Reload Window").

> ⚠️ `command` must be the **absolute path** of the Python interpreter inside the
> project's virtualenv. A ready-made copy lives at `ollama-vision-mcp/.vscode/mcp.json`.

### Option B — all projects (user-global)

To make the tools available in every project, add the same `"ollama-vision"` entry
under `"servers"` in your **user-level** MCP file:

- `%APPDATA%\Code\User\mcp.json` (VS Code)

Reload the window afterwards. The server uses `os.getcwd()` at call time, so
relative `path`s and the inbox folder resolve against whichever project you are
working in.

### Verify

Open Copilot Chat (Agent mode) and ask:

```
Run vision_status
```

You should see a JSON with `"ollama": { "ok": true, ... }` and your available
models. If `ok` is false, start Ollama with `ollama serve` and try again.

## Usage

1. Drop a screenshot into the project's inbox folder (default `.agents/inbox`).
   The server creates it on demand.
2. In Copilot Chat (Agent mode), ask something like:
   > "Look at the screenshot in the inbox and tell me what the error is."
3. The agent calls `list_images` → `describe_image` and answers from the text
   description.

Optionally, add a project instruction file (`.github/copilot-instructions.md`)
so the agent auto-checks the inbox when you reference an image:

```markdown
## Vision
Your model cannot see images directly. When the user references a screenshot or
image, look in `.agents/inbox/`: first call `list_images`, then `describe_image`
(and `extract_text` if OCR is needed) before answering.
```

## Environment variables

| Variable              | Default                  | Description                                   |
|-----------------------|--------------------------|-----------------------------------------------|
| `VISION_MCP_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible base URL (Ollama)        |
| `VISION_MCP_MODEL`    | `qwen2.5vl:7b`           | Vision model to use                           |
| `VISION_MCP_API_KEY`  | (empty → `ollama`)       | API key (Ollama ignores it)                   |
| `VISION_MCP_INBOX`    | `.agents/inbox`          | Default folder for `list_images`              |
| `VISION_MCP_MAX_TOKENS`| `2048`                  | Max output tokens for the vision model        |
| `VISION_MCP_COMPRESS` | `1`                      | Auto-downscale images > 50 KB to 768px JPEG   |

Aliases: `VISION_MODEL`, `VISION_BASE_URL`, `VISION_INBOX`, `VISION_API_KEY`.

## Smoke test

```bash
python examples/smoke_test.py
```

Checks Ollama connectivity, lists the inbox, and runs one real vision call on
the first inbox image.

## License

MIT
