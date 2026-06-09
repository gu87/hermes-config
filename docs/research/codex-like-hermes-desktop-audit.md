# Hermes Desktop Codex-like Phase 0 总审计

审计日期：2026-06-03

审计对象：

- `NousResearch/hermes-agent/apps/desktop`，临时 clone 于 `/tmp/nous-hermes-agent-audit`
- `fathah/hermes-desktop`，临时 clone 于 `/tmp/hermes-desktop-audit/fathah-hermes-desktop`
- 当前 Hermes 客户端，工作区 `/Users/gu/.hermes`

本轮结论很清楚：产品设计参考 `NousResearch/hermes-agent/apps/desktop`；工程落地参考 `fathah/hermes-desktop`；当前 Hermes 保留自己的 Gateway、session/task/run、managed agents、Feishu 入口、Codex runtime transport 与 Kanban/review 后端能力。目标不是把 Hermes 变成另一个聊天壳，而是把它改造成：

```text
Project -> Task Thread -> Agent Run -> Logs / Tool Calls / Diff -> Review -> Continue / Accept / Done
```

## 观察到的产品结构

### 1. 官方 Hermes Desktop

官方 desktop 已经是最接近 Codex.app 的产品骨架。

- 左侧：按 workspace/session 组织历史，支持新建 session、pin、搜索、工作中 session 状态。
- 中间：chat/thread 是主工作区，不是普通消息页；消息、reasoning、tool call、subagent 事件都进入同一条任务轨迹。
- 右侧：preview、文件树、终端跟随当前 cwd/branch。
- 底部：status bar 展示 gateway、agents、running timer、context、model、版本。
- overlay：Command Center、Agents、Settings、Skills、Artifacts、Cron 等作为全局管理层。

它的核心设计不是“聊天 + 功能页”，而是“agent runtime 控制台 + 任务现场”。

### 2. 社区 Hermes Desktop

社区 desktop 更像工程完成度较高的 Electron 管理客户端。

- 左侧导航把 Chat、Sessions、Kanban、Gateway、Agents、Tools、Skills、Models、Providers、Settings 等做成独立页面。
- Electron main/preload/renderer 分层清晰，`window.hermesAPI` 封装了 chat stream、session cache、kanban、gateway、tools、config、logs 等能力。
- Chat、Sessions、Kanban 页面有不少可直接借鉴的组件和 IPC 设计。
- 但它不是 Codex.app-like 工作台：session、kanban、logs、tools 被拆成功能页，任务运行现场没有聚合成一个持续的 workbench。

### 3. 当前 Hermes 客户端

当前本地 UI 主要是 ops dashboard。

- `dashboard/static/index.html` 是 Gateway Status、Gateway Controls、Live Log Stream、Config Editor 的 2x2 管理界面。
- `dashboard/main.py` 提供 status、logs SSE、config、keys、gateway restart、default model 等运维接口。
- `hermes-agent/gateway/platforms/api_server.py` 已经有 `/v1/runs`、`/v1/runs/{run_id}`、`/v1/runs/{run_id}/events`、approval、stop 等 agent run API。
- managed agents 目录下已有 workspace、session、session binding、event log、review gate、kanban bridge、router、policy 等后台资产。
- Codex app runtime transport 也已存在，说明 Hermes 当前最大价值在后端控制面，不在现有 dashboard UI。

## 可借鉴点

### 产品设计参考：官方 Hermes Desktop

Hermes Codex-like 改造应该借鉴官方 desktop 的一级信息架构：

- 第一屏就是当前任务 thread，而不是欢迎页、设置页或功能宫格。
- Project 用 cwd/workspace 表达，先不做复杂项目数据库。
- Session/thread 是 URL 级对象，可搜索、恢复、pin、branch。
- Tool call 默认产品化展示：标题、状态、耗时、摘要、stdout/stderr、diff、raw payload 分层。
- Reasoning/thinking 默认折叠，运行中可见。
- 右侧固定承担 preview/files/terminal/artifacts。
- 底部 status bar 承担 gateway、agent、run timer、model、context。
- Agents overlay 展示当前 turn 的 spawn tree、状态、成本、工具数、读写文件。

### 工程实现参考：社区 Hermes Desktop

社区 desktop 值得借鉴的是工程边界，而不是产品 IA。

- Electron main/preload/renderer 的能力隔离。
- `window.hermesAPI` 作为稳定前端 API 面。
- session cache/search 从 SQLite 或本地状态中重建历史。
- chat SSE parser 与 streaming callback 的封装。
- Kanban task/detail/run/event 的 UI 读取路径。
- Gateway、settings、provider/model 管理作为 secondary surfaces。

### 当前 Hermes 应保留的部分

当前 Hermes 不应该推倒重来。应保留并围绕以下资产重新组织 UI：

- Gateway API server：尤其是 run/event/approval/stop。
- managed agents：workspace、session、session_binding、router、review_gate、event_log。
- Kanban/task/run 后端：可成为 Task Thread 的数据来源。
- Feishu/外部入口：未来做跨入口连续任务。
- Codex runtime transport：作为一个可选高能力 agent runtime。
- dashboard 的 ops 功能：保留为 Settings/System/Gateway 页面，不再作为主界面。

## 不适合照搬点

### 不照搬官方 desktop 的部分

- 不照搬官方的安装、更新、venv bootstrap 和 portable runtime 逻辑；当前 Hermes 已经是本地系统。
- 不照搬它的全部 gateway JSON-RPC contract；Hermes 已有 `/v1/runs` 与 managed-agent 模型。
- 不在 v0.1 搬完整 Skills、Messaging、Artifacts、Cron、Profiles。
- 不把 todo 工具当作 Hermes 的任务模型；Hermes 应保留更强的 Kanban/task/run 数据结构。
- 不把 subagent 只做成当前 turn overlay；Hermes 的多 agent 控制面需要跨 task/run 的历史视图。

### 不照搬社区 desktop 的部分

- 不把 Chat、Sessions、Kanban、Logs、Tools 分散成彼此独立的一级页面。
- 不把 tool progress 停留在字符串级别。
- 不把 Gateway/Provider/Settings 放到主流程前面。
- 不把远程/SSH/安装器复杂度放进 v0.1 主线。

## 对 Hermes Codex-like 改造的影响

Hermes Desktop 的产品轴线应从“配置和聊天”改成“任务运行控制面”：

```text
左侧：Project / Task Thread Index
中间：当前 Task Thread / Agent Run Timeline
右侧：Files / Diff / Artifacts / Terminal / Logs
底部：Gateway / Agent Fleet / Run Timer / Model / Review State
```

核心对象建议：

- `Project`：最小就是 workspace path/cwd，加上 name、last active、git branch。
- `TaskThread`：用户想完成的一件事，来自 Desktop、Feishu、Kanban 或 API。
- `AgentRun`：一次实际执行，可 running/completed/failed/interrupted/waiting_review。
- `RunEvent`：message、reasoning、tool_call、tool_result、diff、approval、log、artifact。
- `ReviewDecision`：continue、accept、done、reject/needs_changes。

这样 Hermes 既能吸收 Codex.app 的交互手感，又不会丢掉自己已有的多入口、多 agent、review gate 优势。

## v0.1 最小闭环建议

v0.1 只做一个能跑通的 workbench，不做完整桌面生态。

最小闭环：

1. Project/workspace rail：显示本地 workspace 和 task thread 列表，至少支持当前 Hermes workspace。
2. Task thread timeline：把一次任务组织为 user prompt、assistant output、reasoning、tool call、tool result、log、diff。
3. Run status：running、waiting_review、failed、completed、stopped。
4. Logs/tool calls：消费现有 `/v1/runs/{run_id}/events` 或 fixture，先完成结构化展示。
5. Diff panel：先支持 unified diff 文本展示，不急于接真实 apply。
6. Review bar：Continue、Accept、Done 三个动作先接现有 approval/stop 或 mock，再逐步接 review_gate。
7. Gateway/system 状态：放到底部 status bar 或 System overlay。

验收标准：

- 用户打开 desktop 后第一眼看到的是当前 project/task/run，而不是配置面板。
- 一次 agent run 的日志、工具、diff、结果在同一个 thread 里可追踪。
- run 结束后用户能做 Continue/Accept/Done 的下一步决策。

## v1.0 扩展方向

v1.0 应补齐真正 Agent Coding Workbench 能力：

- 多 project：workspace 分组、git branch、dirty state、最近任务。
- 多入口连续性：Feishu、API、desktop、cron 进入同一个 task thread 模型。
- Agent fleet：显示 queued/running/failed/completed agents，支持 spawn tree 和跨 run 历史。
- Review gate：审批、拒绝、继续、接受 diff、标记 done 的完整状态机。
- Diff/artifact preview：文件 diff、生成物、网页 preview、console logs、截图。
- Branch/continue：从任意历史节点继续、fork thread、比较 run。
- Command Center：跨 project 搜索 task/session/run/log/artifact。
- 可观测性：tokens/cost、耗时、失败原因、重试、工具统计。

## 结论

Phase 0 的判断是：

- 产品设计参考官方 `NousResearch/hermes-agent/apps/desktop`。
- 工程实现参考社区 `fathah/hermes-desktop`。
- 当前 Hermes 保留后端控制面、run/event/review/session/task/Feishu/managed-agent 能力。
- v0.1 不做“大而全桌面端”，只做一条真实可感知的 Codex-like agent run 闭环。
