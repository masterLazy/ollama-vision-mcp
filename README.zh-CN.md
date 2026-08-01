# ollama-vision-mcp

[English](README.md) · [中文](README.zh-CN.md)

为使用纯文本模型的 VS Code Copilot（例如 DeepSeek）提供**本地视觉能力**的极简桥接服务。

Copilot 使用纯文本模型时无法直接“看见”图片。本 MCP 服务器填补这一缺口：你把截图放进一个文件夹，  
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

## 功能工具

| 工具             | 参数                                 | 说明                                                         |
| ---------------- | ------------------------------------ | ------------------------------------------------------------ |
| `describe_image` | `path`（必填）, `mode?`, `question?` | 读取图片并生成文字描述。<br>`mode` 可选：`general`（默认）、`ocr`、`ui`、`diagram`；`question` 可附加提问。 |
| `list_images`    | `directory?`（默认：inbox 目录）     | 列出可读取的图片文件。                                       |
| `extract_text`   | `path`（必填）                       | OCR 提取图片中的文字。                                       |
| `vision_status`  | —                                    | 显示当前配置、Ollama 连接状态和可用模型列表。                |

## 本工具的范围

本包**仅仅是桥接层**。它纯粹通过 HTTP 与 Ollama 通信（兼容 OpenAI 的 `/v1/chat/completions` 与 `/v1/models`）。

**它不负责**：
- 安装 Ollama、启动 `ollama serve`、拉取模型或管理模型配置；
- 访问剪贴板、IDE 内部机制，或任何本地 Ollama 以外的网络服务。

Ollama 的安装与模型拉取完全由你自行完成（见[前置条件](#前置条件)）。

## 前置条件（自行准备）

- **Python 3.10+**
- **Ollama** 已安装并正在运行：`ollama serve`
- 已拉取至少一个视觉模型，推荐：
  ```bash
  ollama pull qwen2.5vl:7b
  ```
  其他可选模型：`qwen3-vl:8b`、`gemma3:12b`、`llama3.2-vision:11b`、`llava:7b`。  
  根据你的显卡选择合适的模型，后续通过 `VISION_MCP_MODEL` 环境变量指定。

## 🚀 快速安装（推荐）

在仓库根目录下，运行一条命令完成安装和配置：

```bash
cd ollama-vision-mcp
python setup_mcp.py
```

该脚本会自动：
1. 创建专属虚拟环境（`.venv`）并安装本包（不会污染全局环境）。
2. 检测本地 Ollama 服务，列出已有的视觉模型。
3. 以交互方式引导你设置 `base_url`、`model`、`inbox`、`max_tokens`、图片压缩及可选的 API Key。
4. 将配置写入当前项目的 `.vscode/mcp.json` 和/或用户级全局 MCP 文件（`%APPDATA%\Code\User\mcp.json`），**合并写入**，不会覆盖你已有的其他 MCP 服务器。

非交互式用法（适合 CI/脚本）：

```bash
python setup_mcp.py --yes --project --model qwen2.5vl:7b
python setup_mcp.py --print         # 仅打印配置 JSON，不写入文件
```

安装完成后，在 VS Code 中 **重新加载窗口**（Ctrl+Shift+P → “Developer: Reload Window”）使配置生效。

> 如果之前已经运行过，也可以直接使用命令 `ollama-vision-setup` 重新配置。

## 验证安装

在 VS Code Copilot Chat（**Agent 模式**）中输入：

```
Run vision_status
```

若返回的 JSON 中包含 `"ollama": { "ok": true, ... }` 及模型列表，则表示连接成功。  
如果 `ok` 为 false，请先启动 Ollama（`ollama serve`）再重试。

## 使用流程

1. 将截图放入项目的 inbox 目录（默认为 `.ai/inbox`）。服务器会在需要时自动创建该目录。
2. 在 Copilot Chat 中提问，例如：
   > “看看 inbox 里的截图，告诉我这个报错是什么。”
3. Agent 会自动调用 `list_images` → `describe_image`，并依据文字描述回答。

**让 Agent 更智能（可选）**：将现成指令文件 [`.github/instructions/ollama-vision/vision-tools.instructions.md`](.github/instructions/ollama-vision/vision-tools.instructions.md) 复制到你的项目相同路径即可。它教会 Agent 完整的视觉工作流——调用顺序（`list_images` → `describe_image` → `extract_text`）、模式选择、排障方法，以及引导你把截图放入 inbox。作为 VS Code 的 *file instruction*，只要任务涉及图片就会按需自动加载，开箱即用，无需额外配置。

## 环境变量参考

| 变量                    | 默认值                      | 说明                                |
| ----------------------- | --------------------------- | ----------------------------------- |
| `VISION_MCP_BASE_URL`   | `http://localhost:11434/v1` | Ollama 的 OpenAI 兼容基础 URL       |
| `VISION_MCP_MODEL`      | `qwen2.5vl:7b`              | 使用的视觉模型                      |
| `VISION_MCP_API_KEY`    | 空（实际使用 `ollama`）     | API Key（Ollama 忽略此项）          |
| `VISION_MCP_INBOX`      | `.ai/inbox`                 | `list_images` 的默认目录            |
| `VISION_MCP_MAX_TOKENS` | `2048`                      | 视觉模型的最大输出 token 数         |
| `VISION_MCP_COMPRESS`   | `1`                         | 图片 > 50KB 时自动缩放到 768px JPEG |

兼容别名：`VISION_MODEL`、`VISION_BASE_URL`、`VISION_INBOX`、`VISION_API_KEY`。

## 手动安装（备选）

如果需要完全手动控制每一步，可参考以下过程。

### 1. 创建环境并安装

```bash
cd ollama-vision-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -e .
```

安装后会得到两个命令：
- `ollama-vision-mcp` —— 启动 MCP 服务器
- `ollama-vision-setup` —— 交互式配置快捷入口

### 2. 注册到 VS Code

将以下内容复制到项目的 `.vscode/mcp.json`（仅该项目），或用户级文件 `%APPDATA%\Code\User\mcp.json`（所有项目）。**务必将 `command` 改为你的虚拟环境 Python 绝对路径**：

```json
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

> ⚠️ `command` 必须是虚拟环境内 Python 解释器的**绝对路径**。  
> 也可以运行 `ollama-vision-setup --project` 自动生成此文件。  
> 服务器在调用时使用 `os.getcwd()`，因此相对路径（如 `path` 和 inbox 目录）会相对于服务器启动时所在的项目根目录解析。

## 冒烟测试

运行以下脚本，检验 Ollama 连通性、列出 inbox 内容并对第一张图片执行一次真实视觉调用：

```bash
python examples/smoke_test.py
```

## License

MIT
