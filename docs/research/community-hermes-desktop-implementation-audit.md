# 社区 Hermes Desktop 工程实现审计

审计对象：`fathah/hermes-desktop`

临时路径：`/tmp/hermes-desktop-audit/fathah-hermes-desktop`

审计目标：判断它作为 Hermes Codex-like Desktop 的工程参考价值。

## 观察到的产品结构

社区 desktop 是一个 Electron + React + TypeScript 的多页面管理客户端。

```text
Electron Main
├── hermes process / CLI bridge
├── sessions / session cache
├── kanban bridge
├── gateway controls
├── SSE parser
└── config / tools / skills / providers

Preload
└── window.hermesAPI
    ├── chat streaming callbacks
    ├── sessions and cached sessions
    ├── kanban boards/tasks/runs/events
    ├── gateway start/stop/status
    ├── config/model/provider/profile
    ├── tools/skills/memory
    └── logs/update/install helpers

Renderer
└── Layout
    ├── Chat
    ├── Sessions
    ├── Kanban
    ├── Gateway
    ├── Agents
    ├── Tools / Skills / Memory
    ├── Models / Providers
    ├── Schedules / Office
    └── Settings
```

关键文件：

- `src/main/index.ts`、`src/main/hermes.ts`：Electron 主进程与 Hermes 后端调用。
- `src/preload/index.ts`、`src/preload/index.d.ts`：renderer 能力面。
- `src/main/sessions.ts`：从 Hermes state DB 读取 session、messages、reasoning、tool_call、tool_result。
- `src/main/session-cache.ts`：session cache/search。
- `src/main/sse-parser.ts`：SSE 解析与 tool progress。
- `src/renderer/src/screens/Layout/Layout.tsx`：一级导航。
- `src/renderer/src/screens/Chat/*`：聊天、附件、context、history row。
- `src/renderer/src/screens/Sessions/Sessions.tsx`：历史 session 管理。
- `src/renderer/src/screens/Kanban/Kanban.tsx`：boards、tasks、runs、events、task detail。
- `src/renderer/src/screens/Gateway/Gateway.tsx`：gateway 运维界面。

## 可借鉴点

### 1. Electron 分层清晰

main/preload/renderer 边界清楚，renderer 不直接碰 Node 文件系统和进程能力，而通过 `window.hermesAPI` 调用。这是当前 Hermes 如果要做 desktop 客户端时最值得借鉴的工程边界。

### 2. `window.hermesAPI` 能力面完整

preload 类型定义覆盖：

- install/update/doctor。
- local/remote/SSH connection。
- chat send/abort/chunk/reasoning/tool progress/usage/error。
- gateway start/stop/status。
- session list/messages/cache/search。
- kanban boards/tasks/task detail/runs/events。
- config/model/provider/profile。
- tools/skills/memory/schedules。

Hermes v0.1 可以把这个模式收窄为 `project/task/run/events/review/gateway`，但保留同样的 typed bridge 思路。

### 3. Session 历史重建做得实用

`src/main/sessions.ts` 从本地 DB 重建历史消息，并把 `reasoning`、`tool_call`、`tool_result` 作为 timeline item 暴露给 renderer。它还处理 multimodal content 的 JSON sentinel，能恢复图片 attachment。

这对 Hermes 很有价值：即使 live run stream 不在，历史 task thread 也可以从状态库重建。

### 4. Kanban task/run/event 已有 UI 形态

Kanban 页面已经有：

- board/task 列表。
- task detail。
- comments/events。
- runs。
- 手动 dispatch。
- status columns：triage、todo、ready、running、blocked、done。

虽然产品形态不是 Codex.app-like，但工程上证明了 task/run/event 可以通过 desktop UI 读取与操作。

### 5. Chat 组件具备可复用基础

ChatInput、AttachmentChip、ContextFolderChip、ContextGauge、MessageList、HistoryRow 等组件说明它已经处理了常见桌面聊天输入问题：附件、上下文文件夹、历史恢复、流式输出、token usage。

Hermes v0.1 可以借鉴这些边界，不需要重新发明桌面输入体验。

## 不适合照搬点

### 1. 一级导航不适合作为 Codex-like IA

社区 desktop 把 Chat、Sessions、Kanban、Gateway、Tools、Settings 等拆成平级页面。这样更像管理后台，不像 Codex.app 的持续任务现场。

Hermes 改造应把这些能力聚合到一个 task thread workbench 里，而不是让用户在多个页面之间跳转理解一个 run。

### 2. Tool progress 粒度偏粗

preload 中有 `onChatToolProgress(callback: (tool: string) => void)`，SSE parser 能识别 `hermes.tool.progress`，但产品上仍偏字符串通知。Codex-like 需要结构化 tool call：id、name、args、status、duration、stdout/stderr、diff、artifacts、error。

### 3. Kanban 是独立任务板，不是 task thread 中枢

Kanban 目前像任务管理页面。Hermes 目标里，Kanban/task 应该进入左侧 task index 和中间 thread，而不是独立页面之外的“另一个系统”。

### 4. 安装/远程/SSH 复杂度不适合 v0.1

社区 desktop 处理安装、远程模式、SSH tunnel、更新等问题。这些对通用发行有意义，但当前 Hermes v0.1 应先做本地 workbench，避免把复杂连接模式带进主路径。

### 5. Gateway/Provider/Model 不应占据主流程

这些是必要系统能力，但 Codex-like 工作台里应下沉到 status bar、settings 或 command center，而不是主导航焦点。

## 对 Hermes Codex-like 改造的影响

社区 desktop 对 Hermes 的影响主要是工程实现：

- 用 typed preload API 隔离 UI 与本地系统能力。
- 以主进程承接状态库读取、进程控制、日志读取。
- renderer 只消费 task/run/event 的结构化数据。
- session cache/search 可以复用“本地 DB -> renderer timeline”的模式。
- Kanban task/run/event 页面可以被拆解为左侧 task index 与 run detail panel。

建议不要复制它的页面组织，而是重构成：

```text
Workbench
├── left: Project / TaskThread
├── center: RunTimeline
├── right: Diff / Logs / Artifacts / Files
└── bottom: Gateway / Agent / Review / Model status
```

## v0.1 最小闭环建议

以社区 desktop 为工程参考，v0.1 可以定义最小 preload API：

```text
listProjects()
listTaskThreads(projectId)
getTaskThread(threadId)
startRun(threadId, prompt)
streamRunEvents(runId)
stopRun(runId)
resolveReview(runId, decision)
getGatewayStatus()
getRunLogs(runId)
```

renderer 最小组件：

- `WorkbenchLayout`
- `ProjectTaskRail`
- `RunTimeline`
- `ToolCallCard`
- `DiffPanel`
- `LogsPanel`
- `ReviewBar`
- `StatusBar`

这样能保留社区项目的工程优点，同时避免被它的多页面管理 IA 带偏。

## v1.0 扩展方向

- 完整 Electron installer/update/remote/SSH 可放到 v1.0 后段。
- Session cache 做全文搜索、pin、recent、workspace grouping。
- Kanban 与 TaskThread 双向同步。
- Tool call schema 升级到结构化 trace。
- run event 持久化与历史重放。
- Gateway/diagnostics/logs 进入 Command Center。
- 多 profile/model/provider 进入 secondary settings。

## 结论

社区 Hermes Desktop 不适合作为 Codex.app-like 产品设计蓝本，但非常适合作为工程实现参考。它证明了 Electron typed bridge、本地 session DB 重建、Kanban task/run/event 读取、Gateway 控制这些能力都可以落地。Hermes 应借鉴它的工程边界，重做它的信息架构。
