# Hermes Agent 项目全景图谱

> 生成日期: 2026-06-08 | CodeGraph 索引: 3,103 files, 81,732 nodes, 198,181 edges

---

## 一、双仓库架构

```
~/.hermes/                           # 主仓：配置 + 脚本 + 文档
│
├── config/                          # 运行时配置
│   ├── managed-agents.yaml          # 托管 agent 配置
│   ├── model-subscriptions.yaml     # 模型订阅
│   ├── models.yaml                  # 模型定义
│   ├── agent-registry.json          # Agent 注册表
│   └── client_directory_map.json    # 客户端目录映射
│
├── scripts/                         # 9 个 task-pipeline 脚本
│   ├── compile-task.py              # 编译任务
│   ├── dispatch-task.py             # 分发任务
│   ├── gate-policy.py               # 门控策略
│   ├── opencode-agent.py            # OpenCode agent
│   ├── review-task.py               # 审查任务
│   ├── run-ledger.py                # 运行账本
│   ├── run-task-gate.py             # 任务门控
│   ├── task-status.py               # 任务状态
│   └── verify-task.py               # 验证任务
│
├── tests/                           # 配置/脚本的测试
│   ├── test_opencode_agent.py
│   └── test_run_ledger_default_paths.py
│
├── bin/
│   └── hermes-system-doctor.py      # 系统诊断工具
│
├── docs/                            # 架构/研究/发布/评审文档
│   ├── architecture/                # 架构设计文档
│   ├── research/                    # 调研报告
│   ├── releases/                    # 发布说明
│   ├── review/                      # 代码评审
│   ├── roadmap/                     # 路线图
│   ├── design/                      # 详细设计
│   └── adr/                         # 架构决策记录
│
└── hermes-agent/                    # 代码仓：核心代码 (3,103 files)
      ├── agent/                     # AI Agent 核心引擎
      ├── hermes_cli/                # CLI 入口 + Web 服务器
      ├── gateway/                   # IM 平台网关
      ├── apps/                      # 前端/桌面应用
      │   ├── desktop/               # Electron 桌面应用
      │   └── bootstrap-installer/   # Tauri 安装器
      ├── plugins/                   # 插件系统 (~50 个)
      ├── browser-host/              # 浏览器 workspace 子进程
      ├── acp_adapter/               # ACP 协议适配器
      ├── cron/                      # 定时任务系统
      ├── providers/                 # Provider 基类
      ├── tests/                     # 测试套件
      ├── locales/                   # 16 语言 i18n
      └── skills/                    # 内置技能
```

---

## 二、双入口架构

### 2.1 CLI 入口 — `hermes_cli/main.py:main()`

```
main()
│
├── chat             → cmd_chat() → agent/conversation_loop.py
│
├── gateway          → gateway/run.py (start/stop/status/install/uninstall)
│
├── web/dashboard    → hermes_cli/web_server.py (FastAPI + Vite/React SPA)
│
├── cron             → cron/scheduler.py (list/status/start/stop)
│
├── setup            → hermes_cli/setup.py 交互设置向导
│
├── model            → 模型/提供商选择
├── tools            → 工具配置 (MCP, 平台工具集)
├── plugins          → 插件发现与管理
├── acp              → acp_adapter/entry.py (IDE 集成)
├── doctor           → 系统诊断
├── status           → 组件状态总览
├── version          → 版本信息
├── update           → 自更新
├── uninstall        → 卸载
├── logout           → 清除认证凭证
├── sessions browse  → 会话浏览器
├── kanban           → 看板管理
├── mcp              → MCP 服务器/工具配置
├── skills           → 技能管理
├── backup           → 备份/恢复
├── voice            → 语音配置
├── secrets          → 密钥管理
└── +20 更多子命令
```

### 2.2 桌面应用入口 — `apps/desktop/` (Electron + React + xterm.js)

```
apps/desktop/
│
├── electron/
│   ├── main.cjs                    # Electron 主进程 (285 symbols)
│   ├── preload.cjs                 # 渲染进程 preload
│   ├── browser-session.cjs         # 浏览器会话管理
│   ├── terminal-shell.cjs          # 终端 shell
│   ├── connection-config.cjs       # 连接配置
│   ├── bootstrap-runner.cjs        # 后端引导
│   └── hardening.cjs               # 安全加固
│
├── src/
│   ├── app/
│   │   ├── chat/                   # 聊天界面
│   │   │   ├── composer/           # 编辑器 (rich-editor, attachments, slash 等)
│   │   │   ├── sidebar/            # 会话侧栏
│   │   │   └── right-rail/         # 右侧面板 (preview, console)
│   │   ├── session/                # 会话管理 (message stream, prompt actions)
│   │   ├── settings/               # 8 个设置面板
│   │   ├── shell/                  # 应用壳层 (titlebar, statusbar)
│   │   ├── agents/                 # Agent 管理界面
│   │   ├── browser-runtime/        # 浏览器运行时 (action-gateway)
│   │   ├── cron/                   # 定时任务 UI
│   │   ├── skills/                 # 技能管理 UI
│   │   ├── gateway/                # 网关状态
│   │   └── messaging/              # 消息平台管理
│   │
│   ├── components/
│   │   ├── assistant-ui/           # AI 助手渲染 (markdown, tool, thread)
│   │   ├── chat/                   # 聊天组件 (code-card, diff, shiki, timer)
│   │   ├── pane-shell/             # 面板布局系统
│   │   └── ui/                     # 通用 UI (~40 组件: button, dialog, select 等)
│   │
│   ├── store/                      # Zustand 状态管理
│   ├── hooks/                      # 通用 hooks
│   ├── i18n/                       # 国际化
│   └── themes/                     # 主题系统
│
├── dist/                           # Vite 构建产物
└── release/                        # 发行版 (Hermes.app)
```

---

## 三、核心模块详解

### 3.1 `agent/` — AI Agent 引擎 (~70 文件)

| 模块 | 文件 | 职责 | 大小 |
|------|------|------|------|
| **对话主循环** | `conversation_loop.py` | AI ↔ 用户消息流编排 | 40 symbols |
| **工具执行** | `tool_executor.py` | 工具调度与执行 | 25 symbols |
| **上下文引擎** | `context_engine.py` | Prompt assembly 编排 | 18 symbols |
| **上下文压缩** | `context_compressor.py` | 长上下文压缩/摘要 | 69 symbols |
| **Prompt 构建** | `prompt_builder.py` | System/user prompt 组装 | 69 symbols |
| **记忆管理** | `memory_manager.py` | 记忆读写/路由 | 48 symbols |
| **辅助 LLM 客户端** | `auxiliary_client.py` | 辅助 LLM 调用 (压缩/分类等) | 198 symbols |
| **系统提示** | `system_prompt.py` | 系统提示模板 | 11 symbols |
| **凭证池** | `credential_pool.py` | API 密钥管理/轮换 | 95 symbols |
| **消息清理** | `message_sanitization.py` | 敏感信息脱敏 | 18 symbols |
| **结果显示** | `display.py` | 终端渲染 | 66 symbols |
| **Shell hooks** | `shell_hooks.py` | Shell 集成钩子 | 59 symbols |
| **文件安全** | `file_safety.py` | 文件操作安全校验 | 21 symbols |
| **模型元数据** | `model_metadata.py` | 模型参数/定价 | 89 symbols |
| **速率限制** | `rate_limit_tracker.py` | API 调用限速 | 20 symbols |
| **错误分类** | `error_classifier.py` | LLM 错误分类/恢复 | 37 symbols |

#### `agent/transports/` — LLM 传输层

| 文件 | 适配目标 |
|------|----------|
| `anthropic.py` | Anthropic API |
| `bedrock.py` | AWS Bedrock |
| `chat_completions.py` | OpenAI Chat Completions |
| `codex.py` | GitHub Copilot Codex |
| `codex_app_server.py` | Codex App Server |
| `codex_event_projector.py` | Codex Event Projector |
| `gemini_native_adapter.py` | Google Gemini (62 symbols) |
| `gemini_cloudcode_adapter.py` | Google Cloud Code |
| `anthropic_adapter.py` | Anthropic Adapter 层 (97 symbols) |
| `copilot_acp_client.py` | GitHub Copilot ACP |

#### `agent/lsp/` — LSP 集成

| 文件 | 职责 |
|------|------|
| `client.py` | LSP 客户端 (58 symbols) |
| `manager.py` | LSP 服务器管理 |
| `servers.py` | 语言服务器配置 (72 symbols) |
| `workspace.py` | 工作区管理 |
| `protocol.py` | LSP 协议定义 |
| `cli.py` | CLI 接口 |

### 3.2 `gateway/` — IM 平台网关 (~25 文件)

```
gateway/
│
├── run.py                  # Gateway 主循环 (380 symbols)
│                           #   - 服务生命周期管理
│                           #   - Agent 缓存 (LRU, 128 slots, 1h TTL)
│                           #   - 消息路由 / 会话绑定
│
├── platforms/              # 平台适配器
│   │
│   ├── feishu.py           # 飞书 (340 symbols) — 最大适配器
│   ├── telegram.py         # Telegram (178 symbols)
│   ├── slack.py            # Slack
│   ├── dingtalk.py         # 钉钉
│   ├── wecom.py            # 企业微信
│   ├── weixin.py           # 微信
│   ├── signal.py           # Signal
│   ├── signal_rate_limit.py
│   ├── matrix.py           # Matrix
│   ├── email.py            # Email
│   ├── sms.py              # SMS
│   ├── webhook.py          # Webhook
│   ├── bluebubbles.py      # BlueBubbles (iMessage)
│   ├── homeassistant.py    # Home Assistant
│   └── api_server.py       # REST API 服务器 (146 symbols)
│
├── session.py              # 会话管理
├── config.py               # 网关配置 (50 symbols)
├── delivery.py             # 消息投递路由 (DeliveryTarget/Router)
├── stream_consumer.py      # LLM 流式消费 (49 symbols)
├── stream_dispatch.py      # 流分发
├── stream_events.py        # 流事件
├── pairing.py              # 配对绑定
├── status.py               # 运行状态 (74 symbols)
├── platform_registry.py    # 平台注册表
└── hooks.py                # 钩子系统
```

### 3.3 `hermes_cli/` — CLI + Web 层 (~100 文件)

| 文件 | 职责 | 大小 |
|------|------|------|
| `main.py` | CLI 入口, ~60 子命令 | 259 symbols |
| `web_server.py` | **FastAPI Web 服务器** (dashboard + API + browser-host proxy) | **554 symbols** |
| `config.py` | 配置加载/保存/环境变量 | 122 symbols |
| `plugins.py` | 插件管理器 (discover/load/hook/invoke) | 86 symbols |
| `commands.py` | 斜杠命令注册表 | 82 symbols |
| `auth.py` | 认证系统 (飞书/OAuth/device flow) | 302 symbols |
| `_parser.py` | 参数解析器 | 6 symbols |
| `setup.py` | 安装向导 | 80 symbols |
| `kanban*.py` (4 文件) | Kanban 看板系统 | ~340 symbols |
| `mcp_*.py` (3 文件) | MCP 服务器配置 | ~90 symbols |
| `plugins_cmd.py` | 插件 CLI 命令 | 63 symbols |
| `tools_config.py` | 工具配置 | 86 symbols |
| `pty_bridge.py` | PTY 桥接 | 33 symbols |
| `gateway.py` | Gateway 服务管理 | 171 symbols |
| `models.py` | 模型管理 CLI | 135 symbols |
| `cron.py` | 定时任务 CLI | 19 symbols |
| `clipboard.py` | 剪贴板集成 | 43 symbols |
| `browser_connect.py` | 浏览器连接 | 23 symbols |

#### `web_server.py` 路由结构

```
/api/status             → 系统状态
/api/config             → 配置管理
/api/env                → 环境变量管理
/api/auth/*             → 认证
/api/sessions/*         → 会话管理
/api/plugins/*          → 插件发现/管理
/api/kanban/*           → 看板 API
/api/cron/*             → 定时任务 API
/api/backup             → 备份管理
/api/browser-host/*     → 浏览器子进程代理 (start/stop/status/snapshot/screenshot/context)
/ws/*                   → WebSocket (终端/事件)
```

### 3.4 `plugins/` — 插件系统 (~50 插件)

#### 按类别分组

| 类别 | 数量 | 插件列表 |
|------|------|----------|
| **model-providers/** | 27 | Anthropic, OpenAI, DeepSeek, Gemini, xAI, Bedrock, Copilot, Azure, Nous, OpenRouter, 阿里, 小米, 阶跃, MiniMax, 零一, NVIDIA, Novita, HuggingFace, KiloCode, Kimi, OpenCode, Qwen, StepFun, Arcee, Ollama Cloud, GMI, ZAI |
| **platforms/** | 8 | Discord, Google Chat, IRC, LINE, Mattermost, ntfy, Simplex, Teams |
| **memory/** | 7 | RetainDB, Mem0, Honcho, Holographic, ByteRover, Hindsight, SuperMemory |
| **web/** | 6 | Brave, DuckDuckGo, Exa, Firecrawl, SearXNG, Tavily |
| **browser/** | 3 | Browser Use, Browserbase, Firecrawl |
| **image_gen/** | 5 | FAL, Krea, OpenAI, OpenAI Codex, xAI |
| **video_gen/** | 2 | FAL, xAI |
| **dashboard_auth/** | 3 | Basic, Nous, Self-hosted |
| **observability/** | 2 | Langfuse, Nemo Relay |
| **其他** | ~8 | Kanban, Spotify, Google Meet, Teams Pipeline, Disk Cleanup, Security Guidance, Context Engine, Hermes Achievements |

#### 插件生命周期

```
manifest.json (plugin.yaml) → discover_plugins() → PluginManager
  → 加载 plugin_api.py (如适用)
  → 注册 dashboard 路由 (FastAPI)
  → invoke_hook() 在各阶段触发
```

### 3.5 `browser-host/` — 浏览器 Workspace 子进程

```
browser-host/
├── dist/
│   ├── main.js               # Electron 主进程 (TypeScript → JS)
│   ├── preload.js             # 渲染进程 preload
│   ├── renderer.html          # 渲染页面
│   └── schema.js              # BrowserContextSnapshot 契约
```

**职责**: 启动独立的 Electron 子进程，提供浏览器上下文快照、截图、URL 分析。

**管理方式**: `web_server.py` 通过 `/api/browser-host/*` 代理:
- `start` — 启动 browser-host 子进程
- `stop` — 停止子进程
- `status` — 检查运行状态
- `snapshot` — 获取当前页面快照
- `screenshot` — 获取截屏
- `context` — 获取 bounded context block

### 3.6 `acp_adapter/` — ACP 协议适配器

| 文件 | 职责 |
|------|------|
| `__main__.py` | `python -m acp_adapter` 入口 |
| `entry.py` | main() 入口函数 (19 symbols) |
| `server.py` | ACP 服务器 (87 symbols) |
| `session.py` | ACP 会话管理 (41 symbols) |
| `tools.py` | 工具定义 (42 symbols) |
| `auth.py` | 认证 (6 symbols) |
| `permissions.py` | 权限管理 (15 symbols) |
| `edit_approval.py` | 编辑审批 (33 symbols) |
| `events.py` | 事件处理 (17 symbols) |

**用途**: 让 Cursor/VSCode 等 IDE 通过 ACP 协议接入 Hermes Agent。

### 3.7 `cron/` — 定时任务系统

| 文件 | 职责 |
|------|------|
| `__init__.py` | 公共 API (create/get/list/remove/update/pause/resume/trigger) |
| `jobs.py` | 任务定义/存储/CRUD (63 symbols) |
| `scheduler.py` | 调度器主循环 (73 symbols) |

**工作方式**: Gateway 后台每 60 秒 tick scheduler，文件锁防重复执行。

### 3.8 `apps/` — 前端/桌面应用

| 应用 | 技术栈 | 用途 |
|------|--------|------|
| **desktop/** | Electron + React + Vite | 主桌面应用 (macOS/Windows/Linux) |
| **bootstrap-installer/** | Tauri + Rust + React | 安装引导程序 (占位/过渡) |
| **shared/** | TypeScript | 共享库 (JSON-RPC Gateway) |

---

## 四、数据流图

```
用户输入
  │
  ├─ CLI:  terminal → hermes_cli/main.py → conversation_loop.py → LLM → 回复
  │
  ├─ Web:  browser → web_server.py (FastAPI) → conversation_loop.py → LLM → stream → xterm.js
  │
  ├─ Desktop: Electron → React UI → hermes.ts (IPC) → conversation_loop.py → LLM → stream → UI
  │                                                                                        │
  │                              ┌──────────────────────────────────────────────────────────┘
  │                              ↓
  │                         agent/ 核心模块
  │                         ├── context_engine.py    (组装 prompt)
  │                         ├── prompt_builder.py    (system + user prompt)
  │                         ├── memory_manager.py    (注入记忆)
  │                         ├── system_prompt.py     (系统角色)
  │                         ├── tool_executor.py     (工具执行)
  │                         ├── auxiliary_client.py   (辅助 LLM 调用)
  │                         └── context_compressor.py (上下文压缩)
  │
  ├─ Gateway: Telegram/飞书/Slack → gateway/run.py → session → agent → LLM → reply → delivery
  │
  ├─ ACP:  IDE (Cursor/VSCode) → acp_adapter/server.py → agent → LLM → reply
  │
  └─ Cron:  scheduler tick → 执行 job → 可选 deliver 到 IM 平台
```

---

## 五、插件系统架构

```
plugins/
│
├── __init__.py               # 包标记
│
├── model-providers/          # 每个子目录 = 一个 provider 插件
│   ├── anthropic/
│   │   ├── __init__.py       # 适配器实现
│   │   └── plugin.yaml       # 插件清单
│   ├── deepseek/
│   └── ...
│
├── plugins.py (hermes_cli/)  # PluginManager 核心
│   ├── get_plugin_manager()  # 全局单例
│   ├── discover_plugins()    # 扫描 plugins/ 目录
│   └── invoke_hook()         # 触发插件钩子
│
└── 各插件效果:
    ├── 模型 provider → 注册到 credential_pool/model_metadata
    ├── 平台适配器 → 注册到 gateway/platform_registry
    ├── 记忆后端 → 注册到 memory_manager
    └── dashboard 插件 → 注入 FastAPI 路由
```

---

## 六、关键架构特性

1. **CLI 优先 + 五端统一** — 同一个 `conversation_loop.py` 被 CLI / Web / Desktop / Gateway / ACP 复用
2. **插件即一切** — 模型、记忆、搜索、浏览器、图片/视频生成全通过 `plugins/` 发现加载
3. **双模式运行** — `hermes gateway` 后台守护 (长连接) + `hermes chat` 前台交互 (短会话)
4. **Web Dashboard** — FastAPI + Vite/React SPA，状态/配置/插件/看板/浏览器 workspace 一站式管理
5. **Electron 桌面** — 原生体验，内嵌 xterm.js 终端，支持 CUA 浏览器集成、文件管理
6. **国际化** — 16 种语言，`locales/*.yaml`
7. **记忆系统** — 7 种后端可选 (RetainDB/Mem0/Honcho/Holographic 等)
8. **安全边界** — 文件安全校验、凭证池轮换、消息脱敏、速率限制、安全审计

---

## 七、代码仓关键统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 3,103 |
| 总节点数 | 81,732 |
| 总边数 | 198,181 |
| Python 文件 | 2,085 |
| TypeScript 文件 | 523 |
| TSX 文件 | 266 |
| JavaScript 文件 | 64 |
| Rust 文件 | 9 |
| function 节点 | 19,801 |
| method 节点 | 30,014 |
| class 节点 | 6,443 |
| interface 节点 | 869 |
| route 节点 | 213 |

---

## 八、快速索引 — 关键文件位置

| 想找什么 | 去哪里 |
|----------|--------|
| CLI 入口 | `hermes_cli/main.py:12785` → `main()` |
| Web 服务器 | `hermes_cli/web_server.py` (554 symbols) |
| Agent 对话循环 | `agent/conversation_loop.py` |
| Tool 执行 | `agent/tool_executor.py` |
| Prompt 构建 | `agent/prompt_builder.py` |
| 上下文压缩 | `agent/context_compressor.py` |
| 记忆管理 | `agent/memory_manager.py` |
| 凭证池 | `agent/credential_pool.py` |
| LLM 传输层 | `agent/transports/` |
| Gateway 主循环 | `gateway/run.py` (380 symbols) |
| 平台适配器 | `gateway/platforms/` |
| 消息投递 | `gateway/delivery.py` |
| 插件管理 | `hermes_cli/plugins.py` |
| 看板系统 | `hermes_cli/kanban*.py` |
| 定时任务 | `cron/jobs.py` + `cron/scheduler.py` |
| ACP 适配器 | `acp_adapter/server.py` |
| 浏览器子进程 | `browser-host/dist/main.js` |
| 桌面应用 | `apps/desktop/src/app/` |
| 插件列表 | `plugins/` 各子目录 |
| 国际化 | `locales/*.yaml` (16 种语言) |
| 配置管理 | `hermes_cli/config.py` |
| 安装向导 | `hermes_cli/setup.py` |
| 系统诊断 | `bin/hermes-system-doctor.py` |
| 任务脚本 | `scripts/` (9 个) |
