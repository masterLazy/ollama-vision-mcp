---
description: "Use when the user references a screenshot, image, error dialog, terminal output, UI, or diagram; asks you to look at or analyze an image; or you need vision but are text-only. Covers ollama-vision MCP tools (list_images, describe_image, extract_text, vision_status): correct call order, mode selection, image path handling, troubleshooting, and guiding the user to drop screenshots into the inbox instead of pasting them."
name: "ollama-vision vision tools"
---

# Vision Tools — ollama-vision-mcp

You are text-only and cannot see images. When a screenshot, image, error dialog, terminal output, UI, or diagram is involved, use the local `ollama-vision` MCP tools. Never invent image content.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_images(directory=None)` | List image files. Defaults to inbox (`.ai/inbox`), creates folder if missing. |
| `describe_image(path, mode="general", question=None)` | Describe image via local Ollama vision model. |
| `extract_text(path)` | OCR: extract all visible text verbatim (code, errors, terminal output). |
| `vision_status()` | Show bridge config, Ollama connectivity, available models. |

`path` may be absolute or relative to the server's startup directory. **Prefer absolute paths** — relative paths are resolved from the server’s start directory, which may differ from the VS Code workspace root, causing `list_images()` to report an empty inbox even when files exist. Images >50 KB are auto-compressed to 768px JPEG; small or cropped details may be lost.

## Standard workflow

1. **Find the image** — call `list_images()` to see inbox contents and get the path.
2. **Describe it** — use `describe_image(path, mode, question)` with the most suitable mode (below). `question` focuses the analysis (e.g., "What does this error mean?").
3. **Extract exact text when needed** — for code screenshots, dialogs, or terminal output, call `extract_text(path)`.
4. **Answer from tool output only** — never fabricate image content.

## Choosing a mode

| mode | Use when |
| --- | --- |
| `general` (default) | Most cases — full description with visible text, UI elements, errors, colors, layout. |
| `ocr` | Exact wording matters: code, error messages, terminal output, dialogs. |
| `ui` | Decomposing UI: layout, components, buttons, inputs, errors, URLs, states. |
| `diagram` | Flowcharts, ERDs, architecture diagrams, wireframes — type, nodes, edges, labels. |

Each mode maps to a preset English prompt in `server.py` (`PROMPTS`). Your `question` is appended to that prompt, steering focus but not output format. To change the output structure, edit the prompt directly in `server.py`.

## When the user pastes an image or wants you to see a screenshot

Images pasted directly into chat cannot be read. Guide the user:

1. Save the screenshot into the project’s inbox folder `.ai/inbox` (auto-created).
2. Call `list_images()` to confirm visibility, then follow the standard workflow.

> Suggested: “I can analyze that with the local vision model — please save the screenshot into `.ai/inbox/`, then let me know and I’ll take a look.”

## Boundaries

- **Read-only**: tools only read local images — never modify or move them.
- **No fabrication**: if `list_images` finds nothing or a tool returns `Error: ...`, report that honestly.
- **Bridge only**: this MCP server does not install Ollama, start `ollama serve`, or pull models — that’s the user’s responsibility.

## Known limitations

- **Long/complex pages may truncate silently**: `max_tokens` defaults to 2048, and dense output can be cut off mid-sentence with no marker. If a reply ends abruptly, retry with a cropped image or a more focused `question`; do not treat the tail as complete.
- **CJK OCR is imperfect**: small models misread similar-looking Chinese characters (e.g., 算力→权力, 内存→内容). For exact wording, cross-check against the source; never treat OCR as authoritative for CJK.
- **Reply language follows `question`/image content**: the built-in prompts are English, but the model answers in the language of the question and screenshot (Chinese screenshot + Chinese question → Chinese answer). Expected.
- **Restricted networks may block certain sites**: if you capture your own screenshots, write them to disk with an absolute path and pass that same path to `describe_image`/`extract_text` to avoid the inbox-path mismatch.

## Troubleshooting

1. Run `vision_status()`. If `"ollama": { "ok": true }`, the bridge is healthy — retry the failing tool.
2. If `ok` is `false`, Ollama is unreachable: tell the user to start `ollama serve` (or check `VISION_MCP_BASE_URL`, default `http://localhost:11434/v1`).
3. If a call fails with "model not found": the vision model is not pulled. Ask the user to run `ollama pull <model>` (set via `VISION_MCP_MODEL`, default `qwen2.5vl:7b`).
4. Tools return errors as plain strings (`Error: ...`) — surface the message to the user along with the appropriate fix above.