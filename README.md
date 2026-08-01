# ollama-vision-mcp

[English](https://readme.md/) · [中文](https://readme.zh-cn.md/)

A minimal bridging service that provides **local vision capabilities** for VS Code Copilot using text-only models (e.g., DeepSeek).

When Copilot uses a text-only model, it cannot directly "see" images. This MCP server fills that gap: you drop a screenshot into a folder; Copilot reads the image via this bridge → sends it to a **local Ollama vision model** → gets back a **text description**, which the text-only model can understand.

text

```
VS Code Copilot Chat (Agent mode, text-only model)
        │  MCP stdio
        ▼
ollama-vision-mcp (this package)
        │  Read local image → base64 → POST /v1/chat/completions
        ▼
Ollama (local vision model, e.g., qwen2.5vl:7b)
```



## Tools

| Tool             | Parameters                              | Description                                                  |
| :--------------- | :-------------------------------------- | :----------------------------------------------------------- |
| `describe_image` | `path` (required), `mode?`, `question?` | Reads an image and generates a text description. `mode` is optional: `general` (default), `ocr`, `ui`, `diagram`; `question` can provide an additional query. |
| `list_images`    | `directory?` (default: inbox directory) | Lists image files available for reading.                     |
| `extract_text`   | `path` (required)                       | Extracts text from the image via OCR.                        |
| `vision_status`  | —                                       | Displays the current configuration, Ollama connection status, and list of available models. |

## Scope of This Tool

This package is **only a bridge layer**. It communicates with Ollama purely over HTTP (OpenAI-compatible `/v1/chat/completions` and `/v1/models`).

**It does not handle**:

- Installing Ollama, starting `ollama serve`, pulling models, or managing model configuration;
- Accessing the clipboard, IDE internal mechanisms, or any network service other than your local Ollama.

You are fully responsible for installing Ollama and pulling models (see Prerequisites).

## Prerequisites

*You must set up the following on your own:*

- **Python 3.10+**

- **Ollama** installed and running: `ollama serve`

- At least one vision model pulled; recommended:

  bash

  ```
  ollama pull qwen2.5vl:7b
  ```

  

  Other options: `qwen3-vl:8b`, `gemma3:12b`, `llama3.2-vision:11b`, `llava:7b`.
  Choose a model suitable for your GPU; specify it later via the `VISION_MCP_MODEL` environment variable.

## 🚀 Quick Install (Recommended)

Run a single command in the repository root to complete installation and configuration:

bash

```
cd ollama-vision-mcp
python setup_mcp.py
```



The script will automatically:

1. Create a dedicated virtual environment (`.venv`) and install this package (without polluting the global environment).
2. Detect the local Ollama service and list the available vision models.
3. Interactively guide you to set `base_url`, `model`, `inbox`, `max_tokens`, image compression, and an optional API Key.
4. Write the configuration to the project’s `.vscode/mcp.json` and/or the user‑level global MCP file (`%APPDATA%\Code\User\mcp.json`), **merging** with existing settings and not overwriting your other MCP servers.

Non-interactive usage (suitable for CI/scripts):

bash

```
python setup_mcp.py --yes --project --model qwen2.5vl:7b
python setup_mcp.py --print         # Only prints the config JSON, does not write to file
```



After installation, **reload the window** in VS Code (Ctrl+Shift+P → “Developer: Reload Window”) for the configuration to take effect.

> If you have run it before, you can also reconfigure by simply using the command `ollama-vision-setup`.

## Verify Installation

In VS Code Copilot Chat (**Agent mode**), enter:

text

```
Run vision_status
```



If the returned JSON contains `"ollama": { "ok": true, ... }` and the model list, the connection is successful.
If `ok` is false, start Ollama (`ollama serve`) first and try again.

## Usage

1. Put screenshots into the project’s inbox directory (default `.ai/inbox`). The server will create this directory automatically when needed.

2. Ask a question in Copilot Chat, for example:

   > “Look at the screenshots in the inbox and tell me what this error is about.”

3. The agent will automatically call `list_images` → `describe_image` and answer based on the text description.

**Make the Agent Smarter (Optional)**: Copy the ready-made instruction file [`.github/instructions/ollama-vision/vision-tools.instructions.md`](.github/instructions/ollama-vision/vision-tools.instructions.md) into the same path in your project. It teaches the agent the full vision workflow — call order (`list_images` → `describe_image` → `extract_text`), mode selection, troubleshooting, and guiding you to drop screenshots into the inbox. As a VS Code *file instruction* it is discovered on-demand whenever the task involves images, so it works out of the box with no setup.

## Environment Variables Reference

| Variable                | Default                        | Description                                         |
| :---------------------- | :----------------------------- | :-------------------------------------------------- |
| `VISION_MCP_BASE_URL`   | `http://localhost:11434/v1`    | Ollama’s OpenAI-compatible base URL                 |
| `VISION_MCP_MODEL`      | `qwen2.5vl:7b`                 | Vision model to use                                 |
| `VISION_MCP_API_KEY`    | empty (actually uses `ollama`) | API Key (ignored by Ollama)                         |
| `VISION_MCP_INBOX`      | `.ai/inbox`                    | Default directory for `list_images`                 |
| `VISION_MCP_MAX_TOKENS` | `2048`                         | Maximum output tokens for the vision model          |
| `VISION_MCP_COMPRESS`   | `1`                            | If image > 50KB, automatically resize to 768px JPEG |

Compatibility aliases: `VISION_MODEL`, `VISION_BASE_URL`, `VISION_INBOX`, `VISION_API_KEY`.

## Manual Install (Alternative)

If you need full manual control over each step, refer to the process below.

### 1. Create an environment and install

bash

```
cd ollama-vision-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -e .
```



After installation, you get two commands:

- `ollama-vision-mcp` — start the MCP server
- `ollama-vision-setup` — interactive configuration shortcut

### 2. Register with VS Code

Copy the following into your project’s `.vscode/mcp.json` (project only) or the user-level file `%APPDATA%\Code\User\mcp.json` (all projects). **Make sure to change `command` to the absolute path of your virtual environment’s Python interpreter**:

json

```
{
  "servers": {
    "ollama-vision": {
      "type": "stdio",
      "command": "D:/MyRepos/ollama-vision-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "ollama_vision_mcp"],
      "env": {
        "VISION_MCP_BASE_URL": "http://localhost:11434/v1",
        "VISION_MCP_MODEL": "qwen2.5vl:7b",
        "VISION_MCP_INBOX": ".ai/inbox"
      }
    }
  }
}
```



> ⚠️ `command` must be the **absolute path** to the Python interpreter inside the virtual environment.
> You can also run `ollama-vision-setup --project` to generate this file automatically.
> The server uses `os.getcwd()` when invoked, so relative paths (like `path` and the inbox directory) will be resolved relative to the project root where the server is started.

## Smoke Test

Run the following script to check Ollama connectivity, list the inbox contents, and perform a real vision call on the first image:

bash

```
python examples/smoke_test.py
```



## License

MIT
