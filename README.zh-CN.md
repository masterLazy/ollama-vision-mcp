# ollama-vision-mcp

[English](README.md) · [中文](README.zh-CN.md)

为纯文本的 VS Code Copilot（例如 DeepSeek）提供**本地视觉能力**的极简桥接服务。

Copilot 使用纯文本模型时无法直接"看见"图片。本 MCP 服务器填补这一缺口：你把截图放进一个文件夹，
Copilot 通过本桥接读取图片 → 发送给**本地 Ollama 视觉模型** → 返回**文字描述**，纯文本模型即可理解。

```
VS Code Copilot Chat（Agent 模式，纯文本模型）
        │  MCP stdio
        ▼
ollama-vision-mcp（本包）
        │  读取本地图片 → base64 → POST /v1/chat/completions
        ▼
Ollama（本地视觉模型，如 qwen2.5vl:7b）
```

## 本工具是什么 —— 以及不是什么

本包**仅仅是桥接层**。它纯粹通过 HTTP 与 Ollama 通信（OpenAI 兼容的 `/v1/chat/completions` 与
`/v1/models`）。

它**不负责**：
- 安装 Ollama、启动 `ollama serve`、拉取模型或管理模型配置；
- 访问剪贴板、IDE 内部机制，或你本地 Ollama 以外的任何网络。

Ollama 的安装配置完全由你自行完成（见[前置条件](#前置条件)）。

## 工具

| 工具             | 参数                                     | 行为                                   |
|------------------|------------------------------------------|----------------------------------------|
| `describe_image` | `path`（必填）, `mode?`, `question?`      | 读取本地图片 → 文字描述                |
| `list_images`    | `directory?`（默认：inbox 目录）          | 列出可读取的图片文件                   |
| `extract_text`   | `path`（必填）                            | 对本地图片做 OCR，逐字提取             |
| `vision_status`  | —                                        | 显示配置 + Ollama 连通性 / 可用模型    |

`mode` 取值：`general`（默认）、`ocr`、`ui`、`diagram`。

## 前置条件（由你管理）

- **Python 3.10+**
- **Ollama** 已安装并运行：`ollama serve`
- 已**拉取视觉模型**，例如：
  ```bash
  ollama pull qwen2.5vl:7b
  ```
  其他可选：`qwen3-vl:8b`、`gemma3:12b`、`llama3.2-vision:11b`、`llava:7b`。
  按你的显卡选择一个，通过 `VISION_MCP_MODEL` 配置。

## 安装 / 构建

```bash
cd ollama-vision-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -e .
```

## 注册到 VS Code Copilot

服务器以 stdio MCP 方式启动。根据你希望它生效的范围，有两种注册方式。
**两种方式都要求 Copilot Chat 处于 Agent 模式**才能使用 MCP 工具。

### 方式 A —— 单个项目（`.vscode/mcp.json`）

复制以下内容到你想使用的项目的 `.vscode/mcp.json`（注意修改 python 绝对路径）：

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

然后 **Reload Window**（Ctrl+Shift+P → "Developer: Reload Window"）。

> ⚠️ `command` 必须是项目虚拟环境内 Python 解释器的**绝对路径**。`ollama-vision-mcp/.vscode/mcp.json`
> 已有一份现成模板。

### 方式 B —— 所有项目（用户级全局）

若希望在每个项目都能用，把同样的 `"ollama-vision"` 配置加到你的**用户级** MCP 文件：

- `%APPDATA%\Code\User\mcp.json`（VS Code）

之后重载窗口。服务器在调用时使用 `os.getcwd()`，因此相对路径 `path` 和 inbox 目录会相对于你当前所在的项目解析。

### 验证

打开 Copilot Chat（Agent 模式），输入：

```
Run vision_status
```

应能看到一段 JSON，其中 `"ollama": { "ok": true, ... }` 以及可用的模型列表。若 `ok` 为 false，
先启动 Ollama（`ollama serve`）再重试。

## 使用流程

1. 把截图放进项目的 inbox 目录（默认 `.agents/inbox`）。服务器会在需要时自动创建该目录。
2. 在 Copilot Chat（Agent 模式）中提问，例如：
   > "看看 inbox 里的截图，告诉我这个报错是什么。"
3. Agent 会调用 `list_images` → `describe_image`，并依据文字描述回答。

可选：添加项目指令文件（`.github/copilot-instructions.md`），让 Agent 在你提到图片时自动检查 inbox：

```markdown
## Vision
Your model cannot see images directly. When the user references a screenshot or
image, look in `.agents/inbox/`: first call `list_images`, then `describe_image`
(and `extract_text` if OCR is needed) before answering.
```

## 环境变量

| 变量                    | 默认值                   | 说明                                    |
|-------------------------|--------------------------|-----------------------------------------|
| `VISION_MCP_BASE_URL`   | `http://localhost:11434/v1` | OpenAI 兼容基础 URL（Ollama）        |
| `VISION_MCP_MODEL`      | `qwen2.5vl:7b`           | 使用的视觉模型                          |
| `VISION_MCP_API_KEY`    | （空 → `ollama`）        | API Key（Ollama 忽略它）                |
| `VISION_MCP_INBOX`      | `.agents/inbox`          | `list_images` 的默认目录                |
| `VISION_MCP_MAX_TOKENS` | `2048`                   | 视觉模型的最大输出 token 数             |
| `VISION_MCP_COMPRESS`   | `1`                      | 图片 > 50 KB 时自动缩放到 768px JPEG    |

兼容别名：`VISION_MODEL`、`VISION_BASE_URL`、`VISION_INBOX`、`VISION_API_KEY`。

## 冒烟测试

```bash
python examples/smoke_test.py
```

检查 Ollama 连通性、列出 inbox 内容，并对 inbox 中的第一张图片执行一次真实视觉调用。

## License

MIT
