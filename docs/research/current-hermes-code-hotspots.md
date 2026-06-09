# Hermes 当前代码结构快速扫雷

> 目标：为 Hermes Desktop Codex-like 改造做快速扫雷。只读不写。输出问题清单和热点文件列表。

扫描日期：2026-06-03
扫描范围：`~/.hermes/hermes-agent/` 核心 Python/TypeScript 源码

---

## 1. 当前 UI 入口文件

| 文件 | 行数 | 技术栈 | 角色 |
|------|------|--------|------|
| `hermes_cli/main.py` | 12,355 | Python argparse | 主 CLI 入口，所有子命令 dispatch（`hermes chat/gateway/acp/setup/...`） |
| `cli.py` | 14,246 | Python prompt_toolkit | 交互式 TUI REPL，HermesCLI 类，直接实例化 AIAgent |
| `ui-tui/src/entry.tsx` | 99 | Node.js + Ink + React | Node.js TUI 入口，通过 stdio JSON-RPC 连接 tui_gateway |
| `web/src/main.tsx` | 25 | React + react-router | Web 仪表盘入口，BrowserRouter 挂载 |
| `web/src/App.tsx` | 858 | React | Web 路由 + 侧边栏 + 页面 layout |
| `hermes_cli/curses_ui.py` | 472 | Python curses | 终端多选清单（`hermes tools/skills` 命令使用） |

**关键发现**：
- `cli.py` 和 `hermes_cli/main.py` 合计超过 26,000 行，是 UI 层最大的两个单体文件
- `cli.py` 内部包含完整的 prompt_toolkit Application 构建、KeyBindings、自动补全、slash 命令处理
- `ui-tui` 是**独立的 Node.js 进程**，通过 stdio 与 Python `tui_gateway` 子进程通信——这是一个重要的 IPC 边界

---

## 2. Workspace / Session / Task 相关组件

### 2.1 Session 管理

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `hermes_state.py` | 2,966 | SQLite + FTS5 持久化，`SessionDB` 类，Schema v11，sessions/messages/state_meta 表 |
| `gateway/session.py` | 1,398 | `SessionSource` dataclass、会话上下文跟踪、reset 策略、系统提示词注入 |
| `gateway/session_context.py` | 156 | `contextvars.ContextVar` 替换旧 `os.environ` 方案，解决 asyncio 并发安全 |
| `acp_adapter/session.py` | 628 | `SessionManager` + `SessionState`，ACP 会话与 AIAgent 映射，支持 fork/resume |
| `hermes_cli/session_recap.py` | 316 | `/recap` 命令，纯本地计算，从内存会话历史生成摘要 |
| `agent/session_event_log.py` | - | 会话事件日志（tool calls、gate reviews 等） |

### 2.2 Workspace

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `agent/managed_agents/workspace.py` | 97 | `Workspace` dataclass，按 entrypoint（feishu/discord/web/cli/mac_app）分组 session |
| `agent/managed_agents/session.py` | - | Managed Agent 会话绑定 |
| `agent/managed_agents/session_binding.py` | - | 飞书等平台的 session 绑定桥接 |

### 2.3 Task

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `agent/task_card.py` | 220 | `TaskCard` schema v2.8.0，含 `CompiledIntent`、`ExecutionPlan`、`AcceptanceCriteria` |
| `agent/task_card.py` | - | `save_task_card()` 持久化到 JSON 文件 |
| `agent/managed_agents/execution_policy.py` | - | 执行策略（self_execute / single_agent / pipeline / review_only） |
| `hermes_cli/kanban.py` | - | `/kanban` 命令，看板管理 |
| `hermes_cli/kanban_db.py` | - | Kanban SQLite DB |

**关键发现**：
- Session 存储目前**两套并行**：`hermes_state.py` 的 SQLite（CLI + Gateway）和 `acp_adapter/session.py` 的 ACP 会话管理
- Workspace 概念已存在但很简单（97 行），尚未深度集成到所有入口
- Task 模型使用 dataclass + JSON 文件持久化，状态变更历史存在 Event Log 而非 Task Card 自身

---

## 3. 当前状态模型

### 3.1 核心数据库

| 数据库 | 路径 | 用途 |
|--------|------|------|
| `state.db` | `~/.hermes/state.db` | 主会话存储（sessions + messages + FTS5 索引） |
| `kanban.db` | `~/.hermes/kanban.db` | 看板任务管理 |
| `events.db` | `~/.hermes/events.db` | 事件日志 |
| `response_store.db` | `~/.hermes/response_store.db` | 响应缓存 |
| `sessions.db` | `~/.hermes/sessions.db` | 旧版会话存储（可能仍在使用） |

### 3.2 state.db Schema（`hermes_state.py` v11）

```sql
sessions (id, source, user_id, model, model_config, system_prompt,
          parent_session_id, started_at, ended_at, end_reason,
          message_count, tool_call_count, token counters,
          billing info, title, handoff state, ...)

messages (id, session_id, role, content, tool_call_id, tool_calls,
          tool_name, timestamp, token_count, finish_reason,
          reasoning, reasoning_content, reasoning_details, ...)

state_meta (key, value)  -- key-value 元数据
```

### 3.3 其他状态存储

| 存储方式 | 位置 | 内容 |
|----------|------|------|
| JSON 文件 | `~/.hermes/agent-runs.json` | Agent 运行记录 |
| JSON 文件 | `~/.hermes/data/workspaces.json` | Workspace 持久化 |
| JSON 文件 | `~/.hermes/data/session_bindings.json` | Session 绑定 |
| 内存 | `AIAgent` 实例属性 | 当前会话消息历史、工具定义、模型配置 |
| contextvars | `gateway/session_context.py` | asyncio 安全的 session 上下文 |

**关键发现**：
- 状态存储**碎片化严重**——SQLite（3+ 数据库）、JSON 文件、内存、contextvars 四层混用
- `state.db` Schema v11 已较成熟，有 parent_session_id 支持分支，但没有显式的 "workspace" 外键
- `AIAgent` 初始化时**60+ 参数**（`agent_init.py` 1,482 行），状态分散在实例属性上
- session 压缩时会通过 `parent_session_id` 创建子 session 链，这个机制需要保留

---

## 4. API / IPC / Adapter 调用位置

### 4.1 IPC 通道

| 通道 | 方向 | 文件 |
|------|------|------|
| **ACP stdio** | Editor ↔ Python | `acp_adapter/server.py`（1,787 行）、`acp_adapter/entry.py`（291 行） |
| **TUI Gateway stdio** | Node.js TUI ↔ Python | `tui_gateway/server.py`（6,622 行）、`tui_gateway/transport.py`、`tui_gateway/ws.py` |
| **TUI WebSocket** | TUI Sidecar ↔ Dashboard | `tui_gateway/event_publisher.py` |
| **Gateway REST** | Messaging platforms ↔ Gateway | `gateway/platforms/api_server.py` |
| **Dashboard REST** | Web UI ↔ Python | `dashboard/main.py`、`hermes_cli/web_server.py` |

### 4.2 LLM Adapter 层

| 文件 | 协议 |
|------|------|
| `agent/transports/chat_completions.py` | OpenAI-compatible REST |
| `agent/transports/anthropic.py` | Anthropic Messages API |
| `agent/transports/bedrock.py` | AWS Bedrock |
| `agent/transports/codex.py` | Codex 协议 |
| `agent/transports/codex_app_server.py` | Codex App Server |
| `agent/anthropic_adapter.py` | Anthropic 适配层 |
| `agent/gemini_native_adapter.py` | Gemini 原生适配 |
| `agent/bedrock_adapter.py` | Bedrock 适配 |
| `agent/codex_responses_adapter.py` | Codex Responses 适配 |
| `agent/process_bootstrap.py` | OpenAI SDK 延迟加载 + SafeWriter |

### 4.3 平台 Adapter（20+ 平台）

| 目录 | 文件数 |
|------|--------|
| `gateway/platforms/` | 36 文件（telegram, discord, slack, feishu, whatsapp, signal, wecom, dingtalk, matrix, ...） |

**关键发现**：
- IPC 通道有**4 条独立的通信路径**（ACP stdio、TUI stdio、Gateway REST、Dashboard REST），但底层都调用同一个 `AIAgent` 核心
- TUI Gateway 使用**子进程模式**——Python 作为 JSON-RPC stdio 服务端，Node.js 作为客户端——这是 Desktop 改造最直接的 IPC 参考
- ACP Adapter 是官方 `agent-client-protocol` 库的实现，已有 session fork/resume/setModel 等协议能力
- LLM Adapter 层解耦较好，每种模型协议有独立文件

---

## 5. 改造热点文件（按风险排序）

### 🔴 高危热点（必须重构/拆分）

| 文件 | 行数 | 问题 | 建议 |
|------|------|------|------|
| `cli.py` | 14,246 | 单体 TUI + Agent 交互 + Slash 命令 + 状态管理全部混在一起 | 拆分为 UI 层（仅渲染）+ Command Handler + Session Store 三层 |
| `gateway/run.py` | 17,207 | 单体 Gateway 运行器，包含所有平台生命周期、消息路由、Agent 缓存 | 提取 Agent 生命周期管理为独立模块 |
| `tui_gateway/server.py` | 6,622 | TUI Gateway JSON-RPC 调度器，协议层与业务逻辑耦合 | 提取协议无关的 dispatch 接口 |
| `hermes_cli/main.py` | 12,355 | CLI 入口臃肿，argparse 子命令直接在 main.py 实现 | 子命令 handler 抽取到独立文件 |

### 🟡 中危热点（需要接口抽象）

| 文件 | 行数 | 问题 | 建议 |
|------|------|------|------|
| `run_agent.py` | 4,157 | AIAgent 类仍然很大，直接暴露给所有 UI 层 | 定义 `AgentHandle` / `AgentSession` 接口 |
| `agent/conversation_loop.py` | 4,374 | 已从 run_agent 抽出，但仍是巨型函数 | 可进一步拆分为 pre/post hooks |
| `agent/agent_init.py` | 1,482 | 60+ 参数初始化，与配置系统紧耦合 | 引入 AgentConfig dataclass |
| `hermes_state.py` | 2,966 | Schema v11 已成熟，但 SessionDB 是唯一入口 | 定义 Repository 接口，支持未来替换存储 |
| `acp_adapter/server.py` | 1,787 | ACP 协议实现，与 AIAgent 直接耦合 | 通过 AgentHandle 接口解耦 |

### 🟢 低危但需关注

| 文件 | 行数 | 问题 |
|------|------|------|
| `web/src/lib/api.ts` | 1,787 | Dashboard REST API 客户端，包含大量类型定义 |
| `hermes_cli/commands.py` | 1,729 | Slash 命令注册表，命令分散在多个文件实现 |
| `agent/tool_executor.py` | 920 | 工具并发执行，使用 ThreadPoolExecutor |

---

## 6. 强耦合风险清单

### 6.1 AIAgent 直接实例化链

```
cli.py → HermesCLI.__init__() → AIAgent(base_url=..., model=...)
tui_gateway/server.py → HermesCLI(...) → AIAgent(...)
gateway/run.py → _get_or_create_agent() → AIAgent(...)
acp_adapter/session.py → SessionManager._build_agent() → AIAgent(...)
```

**风险**：所有入口都直接 `import run_agent` 并调用 `AIAgent(...)`。改造时需要统一通过 Factory / AgentHandle 创建。

### 6.2 Session 状态碎片化

```
hermes_state.SessionDB      → SQLite (state.db)
gateway/session.py          → 内存 SessionCache + JSON 文件
acp_adapter/session.py      → 内存 SessionManager + SessionDB
agent/managed_agents/       → JSON 文件 (workspaces.json, session_bindings.json)
gateway/session_context.py  → contextvars (运行时上下文)
AIAgent 实例属性             → 内存 (messages, tools, config)
```

**风险**：没有一个统一的 "Session" 对象，多个系统各自维护自己的 session 视图。Desktop 需要一个统一的 Session Repository。

### 6.3 配置系统多层引用

```
hermes_cli/config.py (cfg_get)
hermes_cli/env_loader.py (load_hermes_dotenv)
config.yaml (YAML 主配置)
config/agent-registry.json (Agent 编制)
config/models.yaml (模型路由)
.env (API 密钥)
```

**风险**：配置读取分散在多个模块，Desktop 改造需要统一的 ConfigProvider。

### 6.4 CLI ↔ Gateway 共享代码但初始化路径不同

`cli.py` 的 `HermesCLI` 类同时被以下模块 import：
- `cli.py` 自身（交互式 TUI）
- `tui_gateway/server.py`（TUI Gateway dispatch）
- `tui_gateway/slash_worker.py`（Slash 命令子进程）
- `hermes_cli/main.py`（oneshot、chat 模式）
- `gateway/run.py`（messaging gateway）

但每个调用者**初始化 HermesCLI 的参数组合不同**（`compact`、`resume`、`model`、`verbose` 等 flag 组合）。

**风险**：HermesCLI 承担了太多职责（UI 渲染 + Agent 管理 + 命令处理），改造时需要先拆出纯 Agent 管理层。

### 6.5 工具系统与 Agent 紧耦合

```
tools/registry.py → get_tool_definitions()
agent/tool_executor.py → execute_tool_calls_concurrent/sequential()
tools/terminal_tool.py → _get_approval_callback() (由 AIAgent 设置)
```

**风险**：工具审批回调通过模块全局变量传递（`set_approval_callback`），Desktop 改造时需要一个 RequestContext 来承载审批状态。

---

## 7. 建议先不碰的区域

| 区域 | 原因 |
|------|------|
| `gateway/platforms/` 全部 36 个文件 | 平台适配器隔离良好，每个平台独立处理 I/O，不依赖 UI 层 |
| `gateway/run.py` | 运行时 Daemon，功能稳定，改动风险高。Desktop 只需复用其 Agent 创建路径 |
| `tools/` 目录 80+ 文件 | 工具注册表结构清晰（`registry.py` → 各 `_tool.py`），与 Agent 的接口通过 `get_tool_definitions()` 抽象 |
| `web/src/` + `dashboard/` | Web 仪表盘是独立产品面，不与 Desktop 直接竞争 |
| `skills/` + `hermes_cli/skills_*.py` | 内容层，129+ 个 skill，不在 Desktop 改造范围内 |
| `hermes_cli/curses_ui.py` | 小程序，只有终端多选清单 |
| `agent/transports/` | LLM 适配层已经解耦良好，通过 `AIAgent` 的 `base_url` + `api_key` 参数注入 |
| `config/` + `config.yaml` | 配置格式本身不需要改动，Desktop 只需新增配置段 |
| `hermes_cli/checkpoints.py` | 会话 checkpoint 功能，可后续接入 |
| `agent/context_engine.py` + `agent/context_compressor.py` | 上下文管理核心，当前设计足够 |
| `hermes_cli/banner.py` + `hermes_cli/skin_engine.py` | 终端皮肤系统，Desktop 不需要 |

---

## 8. 关键架构决策点（供 Phase 1 PRD 参考）

1. **Desktop 的 IPC 路径**：可以借鉴 `tui_gateway` 的 stdio JSON-RPC 模式（子进程），也可以用 ACP 协议（stdio），还可以用 WebSocket。当前三种模式都已实现，选择取决于性能要求和协议能力需求。

2. **Session 存储统一**：当前 5 种存储方式需要合并。`hermes_state.py` 的 SQLite Schema v11 是最成熟的候选基础，需要：
   - 增加 `workspace_id` 外键
   - 统一 ACP session 和 Gateway session 的存储路径
   - 提供 Repository 接口层

3. **Agent 生命周期管理**：当前所有入口直接 `AIAgent(...)` 创建。Desktop 需要一个 `AgentPool` / `AgentHandle`，管理 Agent 的创建、复用、销毁、配置注入。

4. **UI-Agent 解耦**：`HermesCLI` 类承担了 UI 渲染 + Agent 管理双重职责。Desktop 改造第一步应提取 `AgentSession` / `AgentRuntime` 层，让 UI 只做渲染。

5. **状态事件流**：当前工具执行、模型响应、错误通过 `print()` + `logger` 输出。Desktop 需要一个统一的事件总线，让 UI 层订阅 Agent 状态变更。

---

## 附录：文件规模总览

| 规模 | 文件数 | 代表文件 |
|------|--------|----------|
| 10,000+ 行 | 3 | `gateway/run.py` (17,207), `cli.py` (14,246), `hermes_cli/main.py` (12,355) |
| 5,000-10,000 行 | 1 | `tui_gateway/server.py` (6,622) |
| 3,000-5,000 行 | 3 | `agent/conversation_loop.py` (4,374), `run_agent.py` (4,157), `hermes_state.py` (2,966) |
| 1,000-3,000 行 | 6 | `acp_adapter/server.py`, `agent/agent_init.py`, `web/src/lib/api.ts`, `hermes_cli/commands.py`, `gateway/session.py` |
| 500-1,000 行 | ~15 | 各种 adapter、tool、handler |
| <500 行 | 大量 | tools、platforms、UI 组件 |

总计核心 Python 代码约 **80,000+ 行**，TypeScript 代码约 **20,000+ 行**。
