# 官方 Hermes Desktop 产品审计

审计对象：`NousResearch/hermes-agent/apps/desktop`

临时路径：`/tmp/nous-hermes-agent-audit/apps/desktop`

审计目标：判断它作为 Codex.app-like Agent Coding Workbench 的产品参考价值。

## 观察到的产品结构

官方 desktop 是三栏 workbench，而不是普通聊天客户端。

```text
AppShell
├── 左栏 ChatSidebar
│   ├── New session
│   ├── Skills & Tools / Messaging / Artifacts
│   ├── pinned sessions
│   ├── workspace grouped sessions
│   └── working session state
├── 中栏 ChatView / Thread
│   ├── user messages
│   ├── assistant messages
│   ├── reasoning
│   ├── tool calls
│   ├── subagent events
│   └── branch/reload/edit actions
├── 右栏 Preview Rail
├── 右栏 Files / Terminal
├── 底部 Status Bar
└── overlays: Command Center / Agents / Settings / Skills / Artifacts / Cron
```

从文件结构看，关键模块包括：

- `app/desktop-controller.tsx`：组织 shell、sidebar、main pane、preview、right sidebar。
- `app/chat/sidebar/index.tsx`：session 列表、workspace group、pin/search/new session。
- `app/chat/index.tsx`：thread 主体。
- `app/chat/right-rail/*`：preview、console、file preview。
- `app/right-sidebar/files/*`：文件树。
- `app/right-sidebar/terminal/*`：内置终端。
- `app/shell/hooks/use-statusbar-items.tsx`：gateway、agents、cron、running timer、context、model、version 状态栏。
- `app/agents/index.tsx`：当前 turn 的 subagent/spawn tree。
- `components/assistant-ui/tool-fallback.tsx`：工具调用产品化展示。
- `store/session.ts`：active session、stored session、cwd、branch、working sessions。
- `store/subagents.ts`：subagent 状态、stream、文件、成本、工具统计。
- `store/tool-diffs.ts` 与 `components/chat/diff-lines.tsx`：按 tool call 组织 diff。

## 可借鉴点

### 1. 第一屏就是任务现场

它没有把配置、模型、技能做成第一屏，而是让用户直接进入当前 session/thread。周边能力都围绕当前任务服务。这是 Codex.app-like 的核心。

### 2. Project 用 cwd/workspace 表达

官方 desktop 没有复杂 Project 模型，而是用 cwd 承担 workspace 语义：

- session 带 cwd。
- sidebar 按 cwd 分组。
-右侧 files/terminal 跟随 cwd。
- status bar 显示 branch/context/model。

Hermes v0.1 可以采用同样策略：先绑定 workspace path，不急着设计大型项目管理系统。

### 3. stored session 与 runtime session 分离

`store/session.ts` 同时维护：

- `selectedStoredSessionId`：历史、URL、搜索、恢复。
- `activeSessionId`：当前 runtime session。

这使得历史恢复、URL 跳转、后台 runtime 重建互不混淆。Hermes 已有 session/run 概念，应明确区分“任务历史对象”和“正在运行的 agent run”。

### 4. Tool call 是产品组件，不是 raw JSON

`ToolFallback` 把工具调用做成 compact row：

- 状态图标、运行时间、错误态。
- 可折叠参数和结果。
- stdout/stderr、ANSI 输出、搜索结果、图片、preview attachment。
- inline diff。
- grouped tool actions。

这是 Hermes 必须借鉴的地方。Codex-like 体验的差异不在模型回答，而在用户能不能看懂 agent 正在做什么。

### 5. Diff 绑定 tool call

`store/tool-diffs.ts` 按 `toolCallId` 存 diff，`DiffLines` 做 unified diff 渲染。这个设计比“单独 diff 页面”更贴近 agent trace：用户看到某个工具调用造成了哪些修改。

### 6. Subagent 状态可视化

`store/subagents.ts` 记录 queued、running、completed、failed、interrupted，以及 stream kind、filesRead、filesWritten、tokens、cost、tool count。`AgentsView` 把当前 turn 的 agent spawn tree 展示出来。

Hermes 本身有多 agent 管理，这一点应重点吸收并扩展。

### 7. Preview console 可回流到任务

preview rail 的 console logs 可以被发送回 chat。对 coding workbench 来说，这意味着“运行失败 -> 把错误交给 agent 修”是现场动作，不是复制粘贴。

## 不适合照搬点

### 1. Runtime bootstrap 不适合照搬

官方 desktop 要服务独立发行，包含安装/更新 Hermes backend、Python 环境、gateway boot、版本更新等逻辑。当前 Hermes 是本地项目，不应把这套发行复杂度引入 v0.1。

### 2. Gateway contract 不应硬拷贝

官方 UI 深度依赖自己的 JSON-RPC 事件，如 `session.create`、`session.resume`、`prompt.submit`、`tool.*`、`subagent.*`。Hermes 应借鉴事件语义，但以当前 `/v1/runs`、event log、review gate 为主。

### 3. 不要一口气复制全部功能面

Skills、Messaging、Artifacts、Cron、Profiles、Settings 都有价值，但 v0.1 如果全部铺开，会稀释主线。Hermes v0.1 应优先让 Project -> Task -> Run -> Logs/Tool/Diff -> Review 成立。

### 4. 不要把 task 简化成 todo

官方 `todo` 工具适合当前 turn 内展示计划，但 Hermes 已经有 Kanban/task/run，更适合做长期任务组织。不要用 todo 覆盖现有任务模型。

## 对 Hermes Codex-like 改造的影响

官方 desktop 给 Hermes 的最大启发是：主界面应围绕“当前任务运行状态”设计。

建议映射：

| 官方 desktop | Hermes 目标 |
| --- | --- |
| workspace cwd | Project/workspace |
| stored session | TaskThread/history |
| active session | AgentRun runtime |
| message/tool stream | RunEvent timeline |
| tool diff | RunEvent.diff / file change |
| Agents overlay | Agent fleet / spawn tree |
| preview console | logs/artifact repair loop |
| status bar | gateway/model/context/review/run state |

## v0.1 最小闭环建议

官方参考下的 Hermes v0.1：

- 左侧 workspace/task thread 列表。
- 中间 run timeline，包含 user prompt、assistant output、reasoning、tool call、tool result。
- 工具调用默认 compact，展开看 raw/detail。
- diff 以内联 panel 展示。
- 右侧展示 files/diff/log/artifact 其中至少一种。
- 底部显示 gateway、run status、agent status、model。
- Review bar 提供 Continue、Accept、Done。

v0.1 的重点是一个任务从发起到 review 的手感，而不是功能数量。

## v1.0 扩展方向

- 真实 multi-project/workspace 管理。
- 完整 thread branch/fork/retry。
- Agent spawn tree 与跨 run agent fleet。
- Preview server、console logs、artifact repair loop。
- Diff accept/reject、partial accept、文件级 review。
- Command Center 搜索 task、session、run、log、artifact。
- Feishu/API/Desktop 多入口统一 thread。
- 成本、token、耗时、失败原因、重试统计。

## 结论

官方 Hermes Desktop 是本次三者中最适合作为产品设计参考的对象。它最接近 Codex.app 的不是 UI 皮肤，而是信息架构：左侧组织 project/session，中间呈现 agent run trace，右侧承载工作区与产物，底部暴露 runtime 状态。
