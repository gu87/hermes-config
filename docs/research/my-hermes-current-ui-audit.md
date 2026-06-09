# 当前 Hermes 客户端审计

审计对象：当前仓库 `/Users/gu/.hermes`

审计目标：判断现有 Hermes 客户端/后端资产如何支撑 Codex-like Agent Coding Workbench。

## 观察到的产品结构

当前 Hermes 的可见客户端主要是 dashboard 与若干 TUI/web/API 入口，而不是一个统一 desktop workbench。

### 1. Dashboard

`dashboard/static/index.html` 是简单运维面板：

```text
Dashboard
├── Gateway Status
├── Gateway Controls
│   ├── default model
│   ├── API keys
│   └── restart gateway
├── Live Log Stream
└── Config Editor
```

`dashboard/main.py` 提供：

- `/api/status`：探测 `http://localhost:8642/health`。
- `/api/logs/stream`：SSE tail `~/.hermes/logs/gateway.log`。
- `/api/config/{name}`：读写 config/models，带备份。
- `/api/keys`：读写 `.env` key。
- `/api/gateway/restart`：重启 gateway。
- `/api/model/default`：设置默认模型。

这套 UI 是 Gateway ops console，不是 coding workbench。它适合保留为 System/Gateway overlay，不适合作为 Hermes Desktop 主界面。

### 2. API Server

`hermes-agent/gateway/platforms/api_server.py` 已经暴露关键 agent run 能力：

- `POST /v1/runs`：启动 run。
- `GET /v1/runs/{run_id}`：读取 run 状态。
- `GET /v1/runs/{run_id}/events`：SSE 结构化生命周期事件。
- `POST /v1/runs/{run_id}/approval`：处理审批。
- `POST /v1/runs/{run_id}/stop`：停止 run。
- `GET /health` 与 `/health/detailed`。

这正是 Codex-like workbench 最需要的后端底座。

### 3. Managed Agents

当前 Hermes 已有一组更接近 Agent Control Plane 的模块：

- workspace/session/session binding：把入口、channel、thread 绑定到 workspace/session。
- event log：记录 agent 运行事件。
- review gate：把需要用户决策的节点停下来。
- kanban bridge：把 task/board/run 与 agent 执行连接。
- router/policy：多 agent 选择与执行策略。
- codex runtime transport：`codex_app_server*.py`、`codex_event_projector.py`。

这些比 dashboard UI 更重要，是 Hermes 不应丢掉的核心资产。

## 可借鉴点

### 1. API run/event/approval 已符合 workbench 主线

目标流程 `Project -> Task Thread -> Agent Run -> Logs/Tool Calls/Diff -> Review -> Continue/Accept/Done` 中，当前 Hermes 已经有 Agent Run、events、approval、stop 的基础。

v0.1 不必先造完整 runtime，可以先把现有 run/event API 变成可见 timeline。

### 2. Dashboard 的日志流可迁移

`/api/logs/stream` 可转化为 workbench 的 Logs panel 或 System overlay。它不应占主屏，但可作为 run 出错时的诊断来源。

### 3. Config/Gateway 控制可保留

default model、API keys、gateway restart、health check 都应保留，但位置应从主界面挪到：

- 底部 status bar。
- Gateway menu。
- Command Center/System 页面。
- Settings。

### 4. Session binding 适合多入口连续性

Hermes 的 Feishu/API/Desktop/cron 多入口是优势。当前 session binding 能把外部 thread 与 workspace/session 关联，未来可让 Feishu 发起的任务在 desktop 中继续 review。

### 5. Kanban 可升级为 Task Thread Index

当前 Kanban 不应只是任务板，可以成为左侧 TaskThread 列表的数据来源：

- triage/todo/ready/running/blocked/done 映射 task 状态。
- run/events 映射 thread timeline。
- comments 映射用户/agent 交互记录。
- latest_summary 映射 thread preview。

## 不适合照搬点

### 1. 不保留 dashboard 作为主 IA

Gateway Status、Config Editor、API Keys 不应该是 Codex-like desktop 的第一屏。用户的第一任务是完成代码任务，不是管理配置。

### 2. 不把 logs 当作独立滚动文本

Codex-like 需要日志与 run/tool/diff 关联。单纯 tail gateway log 只能做诊断，不能解释“这个任务为什么失败/改了什么”。

### 3. 不把 `/v1/chat/completions` 当主 UX

OpenAI-compatible chat endpoint适合外部客户端，但 desktop workbench 应优先使用 run/event API，否则会退化成聊天应用。

### 4. 不要重做当前后端模型

当前 Hermes 已有 session/task/run/review/agent 的基础，不应为了模仿官方 desktop 而压成“session + message”的单薄模型。

## 对 Hermes Codex-like 改造的影响

当前 Hermes 的正确改造方向是“前端重组，后端保留”。

建议对象映射：

| 当前 Hermes | Codex-like UI |
| --- | --- |
| workspace/session_binding | Project / TaskThread identity |
| kanban task | TaskThread |
| run | AgentRun |
| event_log / run events | Timeline |
| review_gate / approval endpoint | ReviewBar |
| gateway logs | LogsPanel / System overlay |
| config/model/api keys | Settings / StatusBar |
| codex runtime transport | optional high-capability runner |
| Feishu channel/thread | external task entrypoint |

## v0.1 最小闭环建议

当前 Hermes v0.1 最小闭环可以这样落：

1. 读取一个 workspace/task 列表，若真实 task index 尚不稳定，先用当前 workspace + 最近 run 作为列表。
2. 启动或读取一个 `/v1/runs` run。
3. 消费 `/v1/runs/{run_id}/events`，渲染 timeline。
4. timeline 至少支持：message、reasoning/log、tool call、tool result、error、approval needed、completed。
5. ReviewBar 接 `/v1/runs/{run_id}/approval` 与 `/stop`。
6. LogsPanel 复用 dashboard log stream，但标明是 gateway/system log。
7. Gateway status 放到底部状态栏。

v0.1 的 UI 不应先追求漂亮页面，而应让用户能看见“agent 在为这个任务做什么、卡在哪里、改了什么、下一步我能按什么”。

## v1.0 扩展方向

- Feishu/API/Desktop/cron 任务统一进入 TaskThread。
- Kanban board 与 desktop task rail 双向同步。
- Run event schema 标准化：tool_call、diff、artifact、approval、agent_spawn、log。
- Diff accept/reject/partial accept。
- Agent fleet overlay：跨 task 显示排队、运行、失败、重试。
- Workspace file tree、terminal、artifact preview。
- Command Center 搜索 task、session、run、logs、配置。
- 完整 review gate 状态机：continue、accept、done、needs_changes。

## 结论

当前 Hermes 的 UI 不是 Codex-like，但后端资产很接近 Agent Coding Workbench 的控制面。改造重点不是复制外部桌面端，而是把已有 run/event/review/task/session/agent 能力组织成一个面向任务的桌面工作台。
