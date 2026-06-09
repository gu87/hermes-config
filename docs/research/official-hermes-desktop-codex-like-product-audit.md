# Official Hermes Desktop: Codex.app-like Product Audit

审计对象：`NousResearch/hermes-agent/apps/desktop`

审计点：`origin/main` commit `5fca754ee335f6b99ee59481a242e89f5abe8791`

结论：官方 Hermes Desktop 更接近 Codex.app，不是因为它多了一个 Electron 壳，而是因为它把“对话”设计成 agent runtime 的控制台：左侧是项目化 session 历史，中间是可分支的 thread trace，右侧是文件/终端/preview，底部是 runtime/gateway/agent 状态栏。它的产品骨架是开发者工作台，不是普通聊天客户端。

## 1. 主界面信息架构

官方 desktop 的 IA 可以概括成：

```text
AppShell
├── 左侧 Pane: ChatSidebar
│   ├── New session
│   ├── Skills & Tools / Messaging / Artifacts
│   ├── pinned sessions
│   └── recent sessions, optionally grouped by workspace cwd
├── 中间 PaneMain
│   ├── / 和 /:sessionId -> ChatView
│   ├── /skills -> SkillsView
│   ├── /messaging -> MessagingView
│   ├── /artifacts -> ArtifactsView
│   ├── /cron -> CronView
│   └── /profiles -> ProfilesView
├── 右侧 Pane: preview rail
├── 右侧 Pane: file browser / terminal
├── 顶部 titlebar tools
├── 底部 status bar
└── overlays: settings, command center, agents, onboarding, updates, boot failures
```

关键证据：

- `apps/desktop/src/app/routes.ts`：`/` 和 `/:sessionId` 都归为 `chat`，其他页是 `settings`、`command-center`、`skills`、`messaging`、`artifacts`、`cron`、`profiles`、`agents`。
- `apps/desktop/src/app/desktop-controller.tsx`：实际布局由 `AppShell + Pane(chat-sidebar) + PaneMain + Pane(preview) + Pane(file-browser)` 组成。
- `apps/desktop/src/app/chat/sidebar/index.tsx`：左侧有 `New session`、`Skills & Tools`、`Messaging`、`Artifacts`、session 搜索、pin、workspace 分组。
- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`：底部状态栏显示 Command Center、Gateway、Agents、Cron、Running timer、context usage、session timer、model、version。

这套 IA 和 Codex.app 的相似点在于：第一屏不是“欢迎页/功能页”，而是一个始终围绕当前工作目录、当前任务、当前运行状态展开的控制台。

## 2. Project / Session / Thread / Agent Runtime 的组织方式

### Project

官方 desktop 没有单独的 `Project` 实体表，但用 `cwd` 承担 project/workspace 语义。

- `store/session.ts` 用 `hermes.desktop.workspace-cwd` 记住当前 workspace cwd。
- `ChatSidebar` 会按 `session.cwd` 生成 workspace groups，未设置 cwd 的进入 `No workspace`。
- `RightSidebarPane` 以当前 `cwd` 渲染文件树，并展示当前 Git branch。
- 新建 session 时可以从某个 workspace 发起，`startSessionInWorkspace(path)` 先设置 `currentCwd`，下一条消息创建 backend session 时继承这个 cwd。

这比“项目列表页”更接近 Codex.app：project 是任务运行的上下文，不是一个独立管理对象。

### Session

它同时维护两类 session id：

- `selectedStoredSessionId`：持久化历史 session id，用于 URL、侧边栏、搜索、恢复。
- `activeSessionId`：runtime session id，用于 JSON-RPC 调用、流式事件、当前运行状态。

证据：

- `store/session.ts`：`$activeSessionId`、`$selectedStoredSessionId` 分开。
- `use-session-actions.ts`：新消息前如果没有 runtime session，会调用 `session.create`；后端返回 `session_id` 和 `stored_session_id` 后，URL 切到 `/:storedSessionId`。
- `use-session-actions.ts`：恢复历史时先 `getSessionMessages(storedSessionId)` 读取本地快照，再 `session.resume` 创建/恢复 runtime session。
- `SessionInfo` 包含 `cwd`、`model`、`preview`、`message_count`、`tool_call_count`、`input_tokens`、`output_tokens`、`_lineage_root_id` 等字段。

这个拆法非常重要：历史可检索、URL 可分享/恢复；runtime 可以随后台进程重建。

### Thread

Thread 是 UI 层对 message tree/branch 的呈现。

- `ChatView` 把 `$messages` 转成 `ExportedMessageRepository.fromBranchableArray`。
- assistant message 支持 `branchGroupId`，并提供 `Branch in new chat`。
- `onEdit`、`onReload`、`onBranchInNewChat` 都挂在 assistant-ui runtime 上。

这接近 Codex.app 的 thread 体验：一次任务不是纯线性聊天，而是可以从某条消息分支、重跑、恢复。

### Agent Runtime

Agent Runtime 是由 Electron 主进程启动的 Python Hermes backend。

- `electron/main.cjs` 解析/安装 `ACTIVE_HERMES_ROOT = HERMES_HOME/hermes-agent`。
- backend 启动命令是 `python -m hermes_cli.main dashboard --no-open --tui --host 127.0.0.1 --port <port>`。
- renderer 通过 REST 获取历史/配置/日志，通过 WebSocket JSON-RPC 驱动 live session。
- `@hermes/shared` 的 `JsonRpcGatewayClient` 处理 `request(method, params)` 和 gateway event。

这也是它像 Codex.app 的根本原因：桌面端不是模拟 agent，而是接入一个真实可运行的 agent runtime。

## 3. 用户从发起任务到看到结果的完整路径

### 新任务路径

1. 用户点击 `New session` 或进入 `/`。
2. `startFreshSessionDraft()` 清空消息、重置 busy/usage、保留当前 workspace cwd。
3. 用户在 ChatBar 输入文本、拖入文件、添加 `@file` / `@folder` / `@url` 上下文，或用语音转写。
4. `submitText()` 判断是否是 slash command；普通 prompt 进入 `submitPromptText()`。
5. 前端先乐观插入 user message，设置 `busy=true`、`awaitingResponse=true`。
6. 如果还没有 active runtime session，调用 `session.create`，并带上当前 `cwd`。
7. 后端返回 `session_id` 和 `stored_session_id` 后，前端把 URL 替换成 `/:storedSessionId`，侧边栏插入 optimistic session preview。
8. 前端调用 `prompt.submit`，参数是 `{ session_id, text }`。
9. gateway 事件开始流入：`message.start`、`reasoning.delta`、`message.delta`、`tool.start/progress/complete`、`subagent.*`、`message.complete`。
10. UI 把 reasoning、工具块、子 agent 进度、assistant 文本逐步合并到同一个 thread。
11. `message.complete` 后刷新 session 列表、更新 usage、必要时通知用户。

### 历史 session 路径

1. 用户点击侧边栏 session 或访问 `/:sessionId`。
2. `useRouteResume()` 触发 `resumeSession(storedSessionId)`。
3. 前端先调用 REST `GET /api/sessions/:id/messages` 展示本地快照，避免空白闪烁。
4. 再通过 JSON-RPC 调 `session.resume`，得到 runtime session id 和 runtime-shaped messages。
5. 后续 prompt 都走 runtime session id。

这个路径值得借鉴：历史恢复先快照、再 runtime；用户看到的是连续 thread，而不是“正在重建环境”的技术细节。

## 4. Agent 状态、日志、工具调用、历史记录的展示方式

### Agent 状态

状态展示是多层级的：

- 侧边栏 session row：working session 有发光小点和 animated arc。
- Chat thread：底部 response loading indicator 显示运行计时。
- Status bar：`Running` 显示当前 turn elapsed；`Session` 显示 runtime session elapsed。
- Status bar 的 `Agents` 项汇总 running/failed background actions 和 subagents 数量。
- `AgentsView` overlay 展示当前 turn 的 spawn tree。

### 日志

日志不是只藏在文件里：

- Status bar 的 `Gateway` 菜单显示 gateway readiness 和最近 GUI logs。
- Command Center 的 `System` panel 拉取 `getStatus()` 和 `getLogs({ file: 'agent', lines: 120 })`。
- boot failure overlay 可展示/reveal 最近 logs。
- preview console 会记录 preview webview console 和 Hermes 重启 preview server 的进度。

这比传统“设置页里有日志按钮”更像 Codex.app：日志在任务现场可见，尤其是 preview 失败时可以直接把 console logs 发回 composer。

### 工具调用

工具调用不是裸 JSON：

- `ToolFallback` 把 tool part 映射成 compact row：图标、运行状态、计时、错误、复制、可展开详情。
- 支持 grouped tool actions，把多步工具合并展示。
- 支持 stdout/stderr、ANSI、diff、preview attachment、image output、web search results。
- `todo` 工具被 hoist 成上方任务面板。
- `clarify` 工具变成可交互问答卡，前端通过 `clarify.respond` 解除后端阻塞。
- `reasoning` 被放进 `Thinking` disclosure，流式时自动展开，完成后折叠。

这套“把 agent trace 产品化”的成熟度，是它接近 Codex.app 的最大价值。

### 历史记录

历史记录不只是左侧列表：

- 侧边栏支持 pinned sessions、workspace groups、server-side full-text search、load more。
- session row 显示 title/preview、working 状态、最近活跃时间。
- Command Center 的 Sessions panel 可以搜索、pin、删除、导出。
- URL 直接是 `/:sessionId`，历史 session 是一级路由，不是 modal 状态。
- branch/fork 机制让历史 message 可以成为新 thread 的入口。

## 5. 哪些交互值得 Hermes 借鉴

1. **把 chat 作为运行中枢，而不是功能之一。**
   Hermes 桌面工作台第一屏应该是当前任务 thread，侧边能力围绕它服务。

2. **Project 用 cwd/workspace 轻量表达。**
   不必一开始做复杂 Project 管理系统。先让每个 session 绑定 cwd，侧边栏按 cwd 分组，右侧文件树跟随 cwd。

3. **区分 stored session 和 runtime session。**
   你的 Hermes 已有 session/task/run 概念，更应该把“历史 id”和“运行实例 id”分开。这样断线、重启、恢复、分支都更稳。

4. **任务发起后立即乐观插入。**
   用户输入后先看到自己的消息和运行态，再等待 runtime 创建完成。这个手感很关键。

5. **工具调用要压缩成可读 trace。**
   不要默认展示 JSON。默认给标题、状态、摘要、计时、结果预览；需要时再展开 stdout、stderr、diff、raw payload。

6. **reasoning / thinking 独立折叠。**
   流式时自动展开，结束后收起，既有透明度又不污染最终答案。

7. **右侧 preview + 文件树 + 终端。**
   对 Agent Control Plane 来说，右侧应该是“任务产物和工作区”的现场，而不是普通详情抽屉。

8. **底部状态栏承载系统状态。**
   Gateway、agents、model、context、running timer、version/update 都适合放在 status bar，减少主界面噪音。

9. **Command Center 做全局搜索/管理。**
   Sessions、system logs、usage、导航可以集中在命令中心，而不是拆成多个一级页面。

10. **Agents overlay 展示 spawn tree。**
    对你的多 agent Hermes 尤其重要：要让用户看见谁在跑、跑多久、用了哪些工具、读写了哪些文件、是否失败。

11. **preview 失败时允许“让 agent 修”。**
    官方 desktop 的 preview rail 在 server not found / boot failed 时可触发 Hermes 重启 server，并把 console logs 作为上下文。这是 Codex.app-like 工作台的关键体验。

## 6. 哪些部分不适合照搬

1. **不要照搬官方 runtime bootstrap。**
   官方 desktop 为通用发行包服务，要安装/更新 `HERMES_HOME/hermes-agent`、处理 Python venv、portable Git、release installer。你的 Hermes 已经是本地系统，照搬会增加维护成本。

2. **不要照搬 Hermes Agent 的 gateway contract。**
   官方 UI 深度依赖 `session.create/resume`、`prompt.submit`、`tool.*`、`subagent.*`、`clarify.*` 这些事件名。你的 Hermes 可以借鉴事件语义，但不要被其 Python backend contract 绑死。

3. **不要把所有功能页都作为第一阶段目标。**
   Skills、Messaging、Artifacts、Cron、Profiles 都有价值，但如果目标是 Codex.app-like control plane，MVP 应先做 Chat/Session/Task/Run/Agent 状态和 workspace preview。

4. **不要照搬装饰性/品牌细节。**
   官方 UI 有大量皮肤、haptics、voice、theme、animated polish。这些会分散你的第一阶段改造重点。

5. **不要把 task 数据模型压成 todo。**
   官方的 `todo` 只是 message 内工具状态，不是完整任务管理模型。你的 Hermes 有 kanban/task_cards/runs，应该保留更强的数据结构。

6. **不要把 subagent 只当当前 turn overlay。**
   官方 `AgentsView` 主要展示当前 active session 的 live subagents。你的 Hermes 如果要做 Agent Control Plane，需要跨 session/task 的 agent fleet 视图、排队状态、失败重试和历史 run。

## 7. Hermes 做成 Codex.app-like 桌面工作台应复刻的核心体验

### MVP 必须复刻

1. **三栏工作台**
   左侧 session/task/project 列表；中间 thread；右侧 workspace 文件/产物/preview/terminal。

2. **session 与 task 的双层导航**
   左侧可以按 project/cwd 分组 session，也可以按 task/kanban 状态过滤。session 是对话和 trace，task 是目标和执行单元。

3. **stored id / runtime id 分离**
   `stored_session_id` 用于历史、URL、搜索；`runtime_session_id` 用于 live execution。task run 也同理：`task_id` 与 `run_id` 分开。

4. **流式 agent trace**
   标准事件至少包括：
   - `run.start`
   - `message.delta`
   - `reasoning.delta`
   - `tool.start`
   - `tool.progress`
   - `tool.complete`
   - `agent.spawn`
   - `agent.progress`
   - `agent.complete`
   - `run.complete`
   - `run.error`

5. **工具块产品化**
   每个工具调用默认显示摘要、状态、耗时、输出 preview；展开后显示 raw log/diff/stdout/stderr。

6. **Agent 状态可视化**
   Status bar 显示当前 gateway、running count、model、token/context、当前 run 时间；Agents overlay 展示 spawn tree 和 agent fleet。

7. **历史恢复路径**
   打开历史 session 时先显示本地快照，再连接/恢复 runtime。不要让用户面对空屏或“重建中”的内部状态。

8. **Command Center**
   支持搜索 session/task/artifact/log，打开系统状态、usage、失败任务、配置入口。

9. **Preview 修复闭环**
   右侧 preview 失败时，用户可以一键把错误和 console logs 作为上下文交给 agent 修复。

### 第二阶段再做

- Voice / STT / TTS。
- 皮肤和主题系统。
- in-app updater。
- provider OAuth 管理。
- messaging platform 管理。
- 更完整的 usage analytics。

## 推荐实现方向

如果你的目标是“Hermes Agent Control Plane”，建议不要 fork 官方 desktop 直接改。更好的方式是复刻它的产品骨架：

```text
官方 Hermes Desktop 可借鉴的层
├── IA: sidebar + thread + preview/files/terminal + statusbar + overlays
├── UX: optimistic send, live trace, tool blocks, thinking disclosure, spawn tree
├── 数据组织: cwd-as-project, stored/runtime session split, branchable thread
└── 运行状态: gateway health, running sessions, subagents, logs, usage

不建议直接继承的层
├── Electron bootstrap/install/update
├── Hermes Agent Python gateway contract
├── 官方 skin/voice/haptics 的复杂 polish
└── 只适配当前 turn 的 subagent overlay
```

对你的 Hermes 来说，最应该复刻的核心体验是：

> 用户进入桌面工作台后，不是在“找一个 agent 聊天”，而是在一个项目上下文里发起任务、观察 agent 执行、检查工具证据、预览产物、恢复历史、继续分支。

这正是官方 Hermes Desktop 接近 Codex.app 的地方。

