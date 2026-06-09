# hermes-desktop 改造成 Agent Control Plane 的适配审计

审计对象：`https://github.com/fathah/hermes-desktop`

审计时间：2026-06-03

本次目标不是改代码，而是判断该项目是否适合作为 Claude Code / Codex / DeepSeek TUI 等多 Agent 的桌面 Control Plane 基底。

## 结论

`hermes-desktop` 适合作为 Agent Control Plane 的 UI 和本地编排基底，但不适合直接把现有 `Hermes Agent API` 当成唯一核心继续扩展。

原因：

- Electron 主进程已经承担了本地进程管理、远程连接、配置读写、日志读取、会话缓存、任务板操作等 Control Plane 需要的职责。
- 渲染层通过 `window.hermesAPI` 访问能力，前端没有直接耦合 Python/SQLite/HTTP 细节，适合在主进程内加 Adapter Layer。
- 但当前实现强绑定 Hermes Agent 的安装目录、CLI 参数、Gateway API、`state.db` 表结构、profile/config/env 文件布局。要支持 Claude Code / Codex / DeepSeek TUI，最小路径应是新增 Agent Adapter 抽象，而不是在现有 Hermes 分支里继续堆条件判断。

推荐改造方向：

1. 保留 Electron + React UI、preload IPC、主进程能力管理。
2. 在主进程新增 `AgentAdapter` 层，把 Hermes 作为第一个 adapter。
3. Chat / Session / Task / Settings / Logs 逐步从 `HermesAPI` 语义改成通用 `AgentControlAPI`，先兼容旧接口，再迁移 UI。

## 1. 项目启动方式、构建方式、主要技术栈

### 启动和构建

来自 `package.json`：

| 用途 | 命令 |
| --- | --- |
| 安装依赖 | `npm install` |
| 开发启动 | `npm run dev` |
| 干净 Hermes Home 开发启动 | `npm run dev:fresh` |
| 预览构建产物 | `npm run start` |
| 类型检查 | `npm run typecheck` |
| 测试 | `npm run test` |
| 构建 | `npm run build` |
| 打包目录 | `npm run build:unpack` |
| macOS 打包 | `npm run build:mac` |
| Windows 打包 | `npm run build:win` |
| Linux 打包 | `npm run build:linux` / `npm run build:rpm` |

### 技术栈

| 层 | 技术 |
| --- | --- |
| 桌面壳 | Electron 39 |
| 构建 | electron-vite 5、Vite 7 |
| 前端 | React 19、TypeScript 5.9 |
| 样式 | Tailwind CSS 4 + 自定义 CSS |
| IPC 暴露 | Electron `contextBridge` + `ipcRenderer.invoke` |
| 本地 DB 读取 | `better-sqlite3` |
| 测试 | Vitest、Testing Library、jsdom、Playwright |
| 打包 | electron-builder |
| 自动更新 | electron-updater |
| 图标 | lucide-react 等 |

### 构建结构

`electron.vite.config.ts` 定义三段构建：

- `main`：`src/main`，外置 `better-sqlite3`。
- `preload`：`src/preload/index.ts` 和 `src/preload/askpass.ts`。
- `renderer`：`src/renderer/src`，React + Tailwind，别名 `@renderer`。

`electron-builder.yml` 定义应用 ID `com.nousresearch.hermes`，产品名 `Hermes Agent`，支持 NSIS、portable、DMG、AppImage、snap、deb、rpm。

## 2. 主进程 / 渲染进程 / preload / IPC 结构

### 主进程

主入口：`src/main/index.ts`

职责集中在一个大文件里：

- 创建 Electron 窗口、菜单、上下文菜单和安全策略。
- 注册大量 `ipcMain.handle(...)`。
- 调用各主进程模块完成真实操作。
- 管理 Chat streaming 回调，把主进程事件转发给 renderer。

主要模块：

| 文件 | 职责 |
| --- | --- |
| `src/main/hermes.ts` | Chat 发送、Gateway 管理、远程/SSH/API/CLI 路由 |
| `src/main/installer.ts` | Hermes 安装检测、升级、doctor、dump、日志读取、路径常量 |
| `src/main/config.ts` | `.env`、`config.yaml`、`desktop.json`、模型和连接配置 |
| `src/main/sessions.ts` | 读取 Hermes `state.db` 的 sessions/messages |
| `src/main/session-cache.ts` | `desktop/sessions.json` 快速缓存 |
| `src/main/kanban.ts` | 通过 `hermes kanban` CLI 操作任务板 |
| `src/main/ssh-remote.ts` | SSH 模式下远程执行 Hermes CLI / 远程 DB 查询 |
| `src/main/profiles.ts` | Hermes profiles 管理 |
| `src/main/memory.ts` / `soul.ts` / `skills.ts` / `tools.ts` | Hermes 生态功能 |

### preload

入口：`src/preload/index.ts`

它把两个对象暴露到 renderer：

- `window.electron`
- `window.hermesAPI`

`window.hermesAPI` 是当前最重要的边界层。它把方法映射到 IPC channel，例如：

- `sendMessage` -> `ipcRenderer.invoke("send-message", ...)`
- `listCachedSessions` -> `ipcRenderer.invoke("list-cached-sessions", ...)`
- `getSessionMessages` -> `ipcRenderer.invoke("get-session-messages", ...)`
- `kanbanListTasks` -> `ipcRenderer.invoke("kanban-list-tasks", ...)`
- `readLogs` -> `ipcRenderer.invoke("read-logs", ...)`

事件型 API 使用 `ipcRenderer.on(...)`：

- `chat-chunk`
- `chat-reasoning-chunk`
- `chat-done`
- `chat-tool-progress`
- `chat-usage`
- `chat-error`
- `install-progress`
- `oauth-login-progress`
- `update-*`

类型定义在 `src/preload/index.d.ts`，基本完整覆盖 preload 暴露面。

### 渲染进程

入口：

- `src/renderer/index.html`
- `src/renderer/src/main.tsx`
- `src/renderer/src/App.tsx`

屏幕结构：

| 屏幕 | 路径 | 主要 API |
| --- | --- | --- |
| Chat | `screens/Chat` | `sendMessage`、chat event listeners、`getSessionMessages` |
| Sessions | `screens/Sessions` | `listCachedSessions`、`searchSessions`、`deleteSession` |
| Agents | `screens/Agents` | `listProfiles`、`createProfile`、`deleteProfile`、`setActiveProfile` |
| Kanban | `screens/Kanban` | `kanbanListTasks`、`kanbanCreateTask`、`kanbanDispatchOnce` |
| Settings | `screens/Settings` | `getConfig`、`setConfig`、`readLogs`、backup/import/dump |
| Gateway | `screens/Gateway` | `startGateway`、`stopGateway`、`gatewayStatus`、platform toggles |
| Models / Providers | `screens/Models`、`screens/Providers` | model config、env key、model discovery |
| Memory / Soul / Skills / Tools | 各 screen | Hermes memory、SOUL、skills、toolsets |

整体是典型 Electron 架构：renderer 只调用 preload API，不直接访问 Node 能力。

### IPC 结构评价

优点：

- IPC 边界已经集中在 preload + `src/main/index.ts`。
- renderer 大部分地方只认 `window.hermesAPI`，适合替换为更通用的 `window.agentControlAPI`。
- 类型定义较完整，有 `preload-api-surface` 测试。

问题：

- `src/main/index.ts` 的 IPC 注册过大，接近一个总线文件。
- channel 命名全部带 Hermes 语义或 Hermes 数据模型。
- 很多 IPC handler 内部按 `isRemoteMode()` / `ssh` / local Hermes 分支写死，不是 adapter 分派。

## 3. 当前 Hermes Agent API 的调用位置

当前 Hermes Agent 调用有四类。

### 3.1 HTTP Gateway Chat API

位置：`src/main/hermes.ts`

核心函数：

- `getApiUrl(profile?)`
- `sendMessageViaApi(...)`
- `sendMessage(...)`

调用路径：

```text
renderer Chat
  -> window.hermesAPI.sendMessage(...)
  -> ipcMain.handle("send-message")
  -> src/main/hermes.ts sendMessage(...)
  -> sendMessageViaApi(...)
  -> POST {getApiUrl(profile)}/v1/chat/completions
```

请求特征：

- OpenAI-compatible `/v1/chat/completions`
- `stream: true`
- 支持 `session_id`
- 本地模式下使用 profile 的 `API_SERVER_KEY`
- remote / ssh 模式下使用远端 Authorization
- 通过 `X-Hermes-Session-Id` 强制指定桌面端 session ID
- 解析 SSE，包括 `hermes.tool.progress` 自定义事件、usage、reasoning delta

这是最适合抽象成 `ChatAdapter.send()` 的位置。

### 3.2 CLI fallback

位置：`src/main/hermes.ts`

核心函数：`sendMessageViaCli(...)`

调用 Hermes CLI：

```text
HERMES_PYTHON + hermesCliArgs(["chat", "-q", message, "-Q", "--source", "desktop", ...])
```

职责：

- 当本地 Gateway 不可用时走 CLI。
- 注入 profile `.env` 中的 provider key。
- 支持 `--resume <sessionId>`。
- 从 stdout/stderr 捕获 `session_id:`。

这是引入 Claude Code / Codex / DeepSeek TUI 的最直接参考实现，但不能直接复用参数模型。应抽成 `ProcessAgentAdapter`。

### 3.3 Gateway 生命周期

位置：`src/main/hermes.ts`

核心函数：

- `startGateway(profile?)`
- `stopGateway(profile?)`
- `isGatewayRunning(profile?)`
- `restartGateway(profile?)`
- `testRemoteConnection(url, apiKey?)`

绑定点：

- `HERMES_PYTHON`
- `HERMES_REPO`
- `hermesCliArgs(["gateway"])`
- `HERMES_HOME`
- `gateway.pid`
- `gateway-stderr.log`
- profile 端口分配

这部分适合拆成 `RuntimeAdapter.start/stop/status/logs`，Hermes Gateway 是其中一种 runtime。

### 3.4 Hermes CLI 工具面

分散位置：

- `src/main/installer.ts`：`doctor`、`update`、`dump`、backup/import、version。
- `src/main/kanban.ts`：`hermes kanban ...`
- `src/main/profiles.ts`：profile CLI。
- `src/main/skills.ts`、`tools.ts`、`cronjobs.ts` 等：读取/写入 Hermes 目录或调用 Hermes CLI。
- `src/main/ssh-remote.ts`：通过 SSH 在远端执行 Hermes CLI 或读取远端 DB。

这说明项目当前不是“纯 API 客户端”，而是“本地 Hermes 发行版管理器 + GUI”。改造成多 Agent Control Plane 时，要明确哪些能力是通用的，哪些能力是 Hermes 专属插件。

## 4. Session、Task、Settings、Logs 的数据模型

### 4.1 Session

真实来源：Hermes Agent SQLite `state.db`

读取位置：

- `src/main/sessions.ts`
- `src/main/session-cache.ts`
- SSH mirror 在 `src/main/ssh-remote.ts`

核心表：

- `sessions`
- `messages`
- 可选 `messages_fts`

`SessionSummary`：

```ts
interface SessionSummary {
  id: string;
  source: string;
  startedAt: number;
  endedAt: number | null;
  messageCount: number;
  model: string;
  title: string | null;
  preview: string;
}
```

`HistoryItem` 是 renderer 看到的统一 timeline：

- `user`
- `assistant`
- `reasoning`
- `tool_call`
- `tool_result`

重要细节：

- `messages.content` 可能有 Hermes sentinel 前缀 `\x00json:`，用于 JSON-encoded multimodal content。
- `tool_calls` 是 Hermes/OpenAI 风格 JSON。
- reasoning 可能来自 `reasoning`、`reasoning_content`、`reasoning_details`。
- session cache 保存在 profile 下的 `desktop/sessions.json`。

适配评价：

- UI 的 `HistoryItem` 抽象可复用。
- 底层 `state.db` 强绑定 Hermes。Claude Code / Codex / DeepSeek TUI 需要各自的 session store adapter，把原始 transcript 映射成同一 `HistoryItem`。

### 4.2 Task

当前 Task 实际是 Hermes Kanban。

位置：`src/main/kanban.ts`

`KanbanTask`：

```ts
interface KanbanTask {
  id: string;
  title: string;
  body: string | null;
  assignee: string | null;
  status: string;
  priority: number;
  tenant: string | null;
  workspace_kind: string;
  workspace_path: string | null;
  created_by: string | null;
  created_at: number | null;
  started_at: number | null;
  completed_at: number | null;
  result: string | null;
  skills: string[];
  max_retries: number | null;
}
```

补充模型：

- `KanbanBoard`
- `KanbanTaskDetail`
- `KanbanComment`
- `KanbanEvent`
- `KanbanRun`

调用方式：

```text
hermes kanban boards list --json
hermes kanban list --json
hermes kanban create ...
hermes kanban assign ...
hermes kanban dispatch --json
```

适配评价：

- Task UI 可作为通用任务控制台原型。
- 当前 task lifecycle 是 Hermes Kanban 语义，不等同 Claude Code / Codex 的任务、会话或 run。
- 最小改造不应直接把 Claude/Codex/DeepSeek 都塞进 `KanbanTask`，而应增加 `ControlTask` 通用层，再由 Hermes Kanban adapter 映射。

### 4.3 Settings

配置来源分三层：

| 配置 | 文件 | 说明 |
| --- | --- | --- |
| 桌面连接配置 | `${HERMES_HOME}/desktop.json` | local/remote/ssh、remote URL、API key、SSH config |
| Hermes env | profile `.env` | provider API keys、工具 API keys |
| Hermes YAML | profile `config.yaml` | model、memory、network、agent service tier、platform settings |

核心位置：`src/main/config.ts`

主要模型：

```ts
interface ConnectionConfig {
  mode: "local" | "remote" | "ssh";
  remoteUrl: string;
  apiKey: string;
  ssh: SshConnectionConfig;
}
```

```ts
interface SshConnectionConfig {
  host: string;
  port: number;
  username: string;
  keyPath: string;
  remotePort: number;
  localPort: number;
}
```

```ts
getModelConfig(profile?) => {
  provider: string;
  model: string;
  baseUrl: string;
}
```

适配评价：

- `desktop.json` 的连接配置可以扩展为 agent registry。
- `.env` / `config.yaml` 强绑定 Hermes profile，不应作为通用 agent 设置模型。
- 最小改造应新增类似 `agents.json` 或 `control-plane.json`，描述 agent kind、command、cwd、env ref、session store、capabilities。

### 4.4 Logs

位置：`src/main/installer.ts`

`readLogs(logFile = "agent.log", lines = 200)` 只允许：

- `agent.log`
- `errors.log`
- `gateway.log`

路径固定为：

```text
${HERMES_HOME}/logs/<logFile>
```

另外：

- Gateway stderr 写到 profile home 下 `gateway-stderr.log`。
- `runHermesDump()` 调 `hermes dump`。
- `Settings` screen 通过 `window.hermesAPI.readLogs(...)` 展示日志。

适配评价：

- Log viewer UI 可复用。
- 日志路径和文件名强绑定 Hermes。
- 适配层应提供 `listLogs(agentId)`、`tailLog(agentId, logId, lines)`，由各 adapter 返回自己的日志源。

## 5. 适合插入 Agent Adapter Layer 的位置

### 首选插入点：主进程 `src/main/hermes.ts`

现在的 `sendMessage(...)` 已经是 chat 统一入口，且已经根据 local/remote/ssh/API/CLI 分派。

建议替换为：

```ts
interface AgentAdapter {
  kind: "hermes" | "claude-code" | "codex" | "deepseek-tui";
  send(input: SendMessageInput, callbacks: ChatCallbacks): Promise<ChatHandle>;
  abort?(sessionId?: string): Promise<void> | void;
  listSessions?(query: SessionQuery): Promise<SessionSummary[]>;
  getSessionMessages?(sessionId: string): Promise<HistoryItem[]>;
  start?(): Promise<RuntimeStatus>;
  stop?(): Promise<RuntimeStatus>;
  status?(): Promise<RuntimeStatus>;
  listTasks?(): Promise<ControlTask[]>;
  getSettings?(): Promise<AgentSettings>;
  updateSettings?(patch: AgentSettingsPatch): Promise<void>;
  listLogs?(): Promise<LogDescriptor[]>;
  readLog?(logId: string, lines: number): Promise<LogReadResult>;
}
```

Hermes adapter 先包住现有函数，做到行为不变。

### 第二插入点：preload API

短期不要大改 renderer，可新增并兼容：

- 保留 `window.hermesAPI`。
- 新增 `window.agentControlAPI`。
- `window.hermesAPI.sendMessage` 内部先转发到默认 agent adapter。

这样能渐进迁移 UI，不需要一次性改全部屏幕。

### 第三插入点：Session Store

当前 `sessions.ts` 直接读取 Hermes `state.db`。建议新增：

```text
src/main/agents/session-store.ts
src/main/agents/adapters/hermes/session-store.ts
src/main/agents/adapters/claude-code/session-store.ts
src/main/agents/adapters/codex/session-store.ts
src/main/agents/adapters/deepseek-tui/session-store.ts
```

通用 UI 只认 `HistoryItem`。

### 第四插入点：Settings / Runtime Registry

新增 registry，不要继续把所有 agent 都写入 Hermes `desktop.json`。

建议：

```json
{
  "activeAgentId": "hermes-default",
  "agents": [
    {
      "id": "hermes-default",
      "kind": "hermes",
      "label": "Hermes Default",
      "profile": "default"
    },
    {
      "id": "codex-local",
      "kind": "codex",
      "label": "Codex",
      "command": "codex",
      "cwd": "/Users/gu/.hermes"
    }
  ]
}
```

### 第五插入点：Task 控制台

先不要把 Kanban 改成通用 task。建议：

- 保留 `Kanban` 作为 Hermes 专属 task view。
- 新增通用 `Runs` 或 `Agent Tasks` 模型。
- Claude Code / Codex / DeepSeek TUI 的非交互 run 先映射为 `ControlTask`，不强行支持 Hermes Kanban 全功能。

## 6. 支持 Claude Code / Codex / DeepSeek TUI 的最小改造路径

### Phase 0：只加抽象，不改 UI 行为

目标：Hermes 行为完全不变。

动作：

1. 新建 `src/main/agents/`。
2. 定义 `AgentAdapter`、`AgentRegistry`、`ChatEvent`、`ControlSession`、`ControlTask`。
3. 实现 `HermesAgentAdapter`，内部直接调用当前 `sendMessageViaApi` / `sendMessageViaCli` / `listSessions` 等现有函数。
4. `ipcMain.handle("send-message")` 先通过 registry 找 active adapter，再调用 adapter。

验证：

- 原 Hermes chat、session、settings、logs 流程不变。
- 现有测试应继续通过，尤其是 IPC、SSE parser、session history、preload API surface。

### Phase 1：新增 agent registry

目标：让 UI 能选择不同 agent，但默认仍是 Hermes。

动作：

1. 新建独立配置文件，例如 `${appData}/control-plane.json` 或 `${HERMES_HOME}/desktop/agents.json`。
2. 支持 agent kind、label、command、cwd、env、session store path、capabilities。
3. Settings/Agents 页先只展示 registry，不做复杂编辑。

最小字段：

```ts
interface AgentRuntimeConfig {
  id: string;
  kind: "hermes" | "claude-code" | "codex" | "deepseek-tui";
  label: string;
  command?: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  profile?: string;
  capabilities: string[];
}
```

### Phase 2：接入 Codex

优先接 Codex，因为它适合作为非交互命令行 run。

建议 adapter：

- `kind: "codex"`
- 通过 CLI 启动。
- 输入：用户 prompt、cwd、可选 session/resume。
- 输出：stdout/stderr 流映射到 `chat-chunk` / `chat-error`。
- 会话：先保存桌面端 transcript 到 control-plane 自己的 SQLite/JSON，不要求复用 Codex 内部历史。

最小可用能力：

- send prompt
- stream output
- abort process
- record local transcript
- read per-run log

暂不做：

- Codex 内部 session 完整恢复。
- Codex MCP/工具配置 UI。

### Phase 3：接入 Claude Code

Claude Code 可能有交互式 session 和本地项目上下文，建议作为 `ProcessAgentAdapter` 的一个实现。

最小路径：

- command/cwd/env 配置化。
- 每次任务以非交互方式发起。
- stdout/stderr 映射到 chat stream。
- 进程 PID、exit code、duration 写入 control-plane run store。

风险：

- Claude Code 的真实 session/resume 机制、鉴权、profile 状态可能不适合被强行抽象成 Hermes session。
- 不建议第一阶段就做深度 session import。

### Phase 4：接入 DeepSeek TUI

现有 Hermes 记忆中，当前 Hermes 的 `deepseek-tui` 是 Named Agent 槽位，路由到 `opencode_go_deepseek_pro` 模型，不等同直接调用本地 `/Users/gu/.npm-global/bin/deepseek-tui`。因此需要区分两种模式：

1. Hermes 内部 Named Agent：继续由 Hermes adapter 管。
2. 真实 DeepSeek TUI CLI：新增 `deepseek-tui` adapter。

最小路径：

- 支持非交互命令，例如 `deepseek-tui exec --json --auto` 这一类模式，具体命令需按当前本机安装版本再验证。
- JSON 输出优先结构化解析；失败时退回文本流。
- session 先由 Control Plane 自己记录。

### Phase 5：通用 Session / Run Store

为非 Hermes agent 新增桌面端自己的存储：

```text
control-plane.db
  agents
  runs
  messages
  tool_events
  logs
```

这样无需等待各 CLI 暴露统一历史 API。

推荐最小表：

```sql
agents(id, kind, label, config_json, created_at, updated_at)
runs(id, agent_id, cwd, status, started_at, ended_at, exit_code, error)
messages(id, run_id, role, content, timestamp, raw_json)
events(id, run_id, kind, payload_json, timestamp)
logs(id, run_id, stream, content, timestamp)
```

Hermes `state.db` 可以继续只读接入，不必迁移。

## 7. 风险点：强绑定 Hermes Agent 的地方、难改的地方、可复用的地方

### 强绑定 Hermes Agent 的地方

| 区域 | 绑定方式 | 风险 |
| --- | --- | --- |
| 安装器 | 官方 Hermes installer、`~/.hermes/hermes-agent`、venv、`hermes` script | 不适合其他 agent |
| Chat API | `/v1/chat/completions` + `X-Hermes-Session-Id` + Hermes Gateway auth | 其他 CLI 不一定有 HTTP API |
| Session | 直接读 Hermes `state.db` 的 `sessions/messages` 表 | 其他 agent 无法复用 |
| Profiles | `~/.hermes/profiles/<name>` | 不能等同 Claude/Codex profile |
| Settings | `config.yaml`、`.env`、`auth.json`、`desktop.json` | Hermes 配置语义过重 |
| Kanban | `hermes kanban ...` CLI | Hermes 专属任务系统 |
| Gateway | `hermes gateway`、profile port、`gateway.pid` | 其他 agent 不一定有 daemon |
| Logs | `${HERMES_HOME}/logs/{agent,errors,gateway}.log` | 日志源固定 |
| Skills/Tools/Memory/Soul | Hermes Agent 插件和文件结构 | 只能作为 Hermes adapter capability |

### 难改的地方

1. `src/main/index.ts` 过大，IPC 注册和业务分派混在一起。后续加多 agent 时容易继续膨胀。
2. `src/main/hermes.ts` 同时负责 HTTP、CLI、Gateway 生命周期、profile、auth、SSE 解析，抽象边界需要先切清楚。
3. renderer 的命名和类型全部叫 `hermesAPI`，迁移到 `agentControlAPI` 会涉及大量文件，但可以兼容迁移。
4. Session UI 依赖 Hermes history shape 的细节较多，包括 reasoning、tool call、attachment 还原。
5. Kanban UI 看似通用任务板，但实际操作是 Hermes CLI，因此不能直接当多 agent task abstraction。
6. SSH remote 模式里复制了一套远程 Hermes 操作逻辑；如果多 agent 都支持 remote，应该重新设计 remote execution 层。

### 可复用的地方

| 区域 | 可复用性 | 说明 |
| --- | --- | --- |
| Electron 壳 | 高 | 主/渲染/preload 架构完整 |
| Chat UI | 高 | streaming、reasoning、tool progress、usage 展示可复用 |
| IPC preload 边界 | 高 | 可以包一层 adapter 分派 |
| Process spawn 经验 | 高 | CLI fallback、gateway spawn、stderr log、abort 都可参考 |
| Session UI | 中高 | UI 可复用，数据源需 adapter |
| Log viewer | 中高 | UI 可复用，日志源需 adapter |
| Settings UI | 中 | 基础控件可复用，数据模型要重做 |
| Agents/Profile UI | 中 | 视觉和交互可复用，语义要从 Hermes profile 改成 Agent registry |
| Kanban UI | 中 | 任务板 UI 可复用，但业务模型需抽象 |
| Installer | 低 | Hermes 专属 |
| Memory/Soul/Skills/Tools | 低到中 | 作为 Hermes capability 保留，不宜通用化 |

## 建议的最小技术方案

### 目录结构

建议新增：

```text
src/main/agents/
  types.ts
  registry.ts
  control-store.ts
  adapters/
    hermes.ts
    process-base.ts
    codex.ts
    claude-code.ts
    deepseek-tui.ts
```

### 通用模型

```ts
type AgentKind = "hermes" | "claude-code" | "codex" | "deepseek-tui";

interface ControlAgent {
  id: string;
  kind: AgentKind;
  label: string;
  cwd?: string;
  command?: string;
  args?: string[];
  profile?: string;
  capabilities: Array<
    | "chat"
    | "sessions"
    | "tasks"
    | "settings"
    | "logs"
    | "runtime"
    | "tools"
  >;
}
```

### 改造顺序

1. 先把 Hermes 包成 adapter，保证行为不变。
2. 新增 control-plane 自有 run/session store。
3. 接 Codex 非交互 run。
4. 接 Claude Code 非交互 run。
5. 接 DeepSeek TUI 非交互 run。
6. 再考虑通用 task board、remote execution、agent health dashboard。

## 适配判断

最终判断：适合改造，但应定位为“Electron Control Plane 壳 + Hermes adapter”，而不是“在 Hermes Desktop 里硬塞多个 CLI”。

最小可行版本应该做到：

- 一个统一 Agent 列表。
- 一个统一 Chat/Run 入口。
- Hermes 继续使用原 gateway/session/kanban。
- Codex / Claude Code / DeepSeek TUI 先以 process adapter 运行，输出进入统一 transcript。
- 非 Hermes 的 session/log/task 数据由 Control Plane 自己记录。

这条路径改动小、风险可控，也不会破坏 Hermes Desktop 已经实现得比较完整的 Hermes 专属能力。

