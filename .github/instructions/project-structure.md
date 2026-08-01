# ollama-vision-mcp — 项目结构与开发速查

> 用途：让 agent 接到新任务时无需重新通读全部代码即可上手。
> 文档约定：本仓库只允许在 `.github/instructions/` 下放置说明 / 复盘类文档，**不要新建** `docs/` 等其它文档目录。

## 一句话定位

纯桥接层：在**本地 Ollama 视觉模型**与 **VS Code Copilot（纯文本模型）** 之间搭 MCP 桥。
Copilot 调用 MCP 工具 → 本包读取本地图片 → 发给本地 Ollama 的 OpenAI 兼容接口 → 返回文字描述。

**边界（务必遵守）**：本包**绝不**安装 / 启动 / 管理 Ollama、不拉取模型、不访问本地 Ollama 以外的网络。
Ollama 安装、`ollama serve`、`ollama pull` 全部由用户自理。

## 目录结构

```
setup_mcp.py                 # 仓库根：预安装启动器（sys.path 加 src/ 后调 setup_mcp.main()）
src/ollama_vision_mcp/
  __init__.py                # __version__ = "0.1.0"
  __main__.py                # python -m ollama_vision_mcp 入口 → server.run()
  config.py                  # 配置读取（纯环境变量，无第三方依赖）
  server.py                  # MCP 服务器（mcp>=2.0.0 新 API）+ run() 入口 + 4 个工具
  vision_client.py           # OpenAI 兼容 HTTP 客户端（httpx 异步）：/v1/chat/completions、/v1/models
  image_loader.py            # 图片 → base64 data URL；扩展名白名单、magic 校验、>50KB 自动缩 768px JPEG
  setup_mcp.py               # 交互式配置脚本（纯 stdlib，不依赖本包其它模块）
examples/
  smoke_test.py              # 冒烟测试：Ollama 连通性 + inbox + 一次真实视觉调用
  test_mcp.py                # MCP 协议端到端测试（stdio 拉起服务器，走 initialize/tools/list 流程）
```

## 配置（config.py）

- 全部来自**环境变量**，无配置文件。优先级：`VISION_MCP_*` > `VISION_*` 兼容别名 > 默认值。
- 默认值：`BASE_URL=http://localhost:11434/v1`、`MODEL=qwen2.5vl:7b`、`INBOX=.ai/inbox`、
  `MAX_TOKENS=2048`、`COMPRESS=1`。
- `VISION_MCP_API_KEY` 为空时客户端用占位 `ollama`（Ollama 忽略 key 但期望该字段存在）。
- **同步陷阱**：默认值同时散落在 `config.py` / `.env.example` / `README.md`(x2) / `setup_mcp.py` 的 `DEFAULTS`
  中——改动任何一处必须同步全部。

## MCP 工具（server.py）

| 工具              | 参数                     | 作用                     |
|-------------------|--------------------------|--------------------------|
| `describe_image`  | `path`(必填), `mode?`, `question?` | 读图→描述（general/ocr/ui/diagram） |
| `list_images`     | `directory?`(默认 inbox) | 列出目录中的图片         |
| `extract_text`    | `path`(必填)             | OCR 逐字提取             |
| `vision_status`   | —                        | 配置 + Ollama 连通性/模型列表 |

## API 陷阱（重要）

- **mcp SDK 2.x API 已重构**：mcp 2.0.0 已移除旧的 `mcp.server.Server.list_tools()/call_tool()`
  装饰器 API。必须用 `mcp.server.mcpserver.MCPServer` + `@server.tool()`（async 可用），
  `server.run(transport='stdio')` 是**同步阻塞**方法。依赖写 `mcp>=2.0.0`。
  参考 vision-mcp / deepseek-eyes 等 `mcp>=1.0.0` 旧仓库不能照抄。
- **stdio 的 stdout 是协议通道**：server.py 的启动提示只能写 stderr，绝不能 print 到 stdout，
  否则破坏协议帧。
- 纯桥接哲学：`vision_client.py` 里 404 模型不存在 → 提示 `ollama pull <model>`；
  连接失败 → 提示 `ollama serve`。不要在代码里改回自动管理 Ollama。

## 常用命令

```bash
# 一键安装 + 配置（推荐/默认）：自动创建 .venv、pip install -e .、检测 Ollama、写 mcp.json
python setup_mcp.py

# 手动安装（Windows）
python -m venv .venv
.venv\Scripts\activate
pip install -e .            # 安装两个命令：ollama-vision-mcp 与 ollama-vision-setup

# 运行 / 验证
ollama-vision-mcp                        # 启动 MCP 服务器（stdio）
ollama-vision-setup                      # 交互式配置（已安装后；检测本地 Ollama 模型，写 mcp.json）
python setup_mcp.py --yes --print        # 非交互：只打印配置 JSON（不建环境、不装包）
python examples/smoke_test.py            # 冒烟测试（真实视觉调用往返）
python examples/test_mcp.py              # MCP 协议端到端测试

# Ollama（用户自理，代码绝不代管）
ollama serve
ollama pull qwen2.5vl:7b
```

## 开发 / 交付约定

- UI 文案、日志、注释一律**英文**；`.github/instructions/` 下的说明/复盘文档可中文。
- 交付前跑 `examples/smoke_test.py` 做端到端验证，不能只"能编译"就交付。
- 若改动了工具签名，同步更新 `examples/test_mcp.py` 中 `expected` 集合与两份 README 的工具表。
- 模型检测在 `setup_mcp.py`：依次探测 `/v1/models`（OpenAI 兼容，与桥本体一致）→ `/api/tags`（原生）
  → `ollama list`（CLI 兜底）；按名称子串（vl/vision/llava/gemma3/...）标视觉模型。
- `setup_mcp.py` 的交互 UX：ANSI 颜色/下划线（TTY 下启用，`NO_COLOR` 或管道输出时自动关闭）；
  无可用环境时默认**创建专属 venv（.venv）并 `pip install -e .`**（避免装到全局；`--print` 不建环境），
  并检查目标解释器是否装了本包（`importlib.util.find_spec`），未装则警告并可选一键安装。
