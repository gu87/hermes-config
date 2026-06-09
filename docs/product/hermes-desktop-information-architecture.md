# Hermes Desktop — 信息架构

版本：0.1-draft
日期：2026-06-03

---

## 一、整体布局

```
┌─────────────────────────────────────────────────────────────────┐
│  Left Rail          │  Center: Run Timeline  │  Right Rail       │
│  (240px, fixed)     │  (flex, main)          │  (320px, toggle)  │
│                     │                        │                   │
│  Project Header     │  Thread Header         │  Diff / Logs /    │
│  ─────────────      │  ─────────────────     │  Changed Files /  │
│                     │                        │  Logs             │
│  Task Thread List   │  Event Stream          │                   │
│  ─────────────      │                        │                   │
│  [+ New Task]       │  [Input Bar]           │                   │
├─────────────────────┴────────────────────────┴───────────────────┤
│  Status Bar                                                       │
│  Gateway │ Active Run │ Timer │ Model │ Review State             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、Left Rail — Project / Task Thread

### Project Header（顶部固定）
- workspace name（来自 cwd 最后一段或 .hermes/config）
- git branch + dirty indicator
- gateway 连接状态点（green / yellow / red）

### Task Thread List
每条 Task Thread 显示：
- title（task title 或 prompt 前 60 字符）
- status badge：`running` / `waiting_review` / `completed` / `failed` / `draft`
- source icon：desktop / feishu / api / cron（v0.5 起显示）
- last activity 时间（相对时间）
- 当前 run 进度（running 时显示 spinner）

排序：running 和 waiting_review 置顶，其余按 updated_at 倒序。

交互：
- 点击切换到该 Thread
- 右键 / 长按：Stop Run / Archive / Copy ID
- `+` 按钮：新建 Task Thread（输入框弹出或展开）

### v0.1 数据来源
- `GET /kanban/tasks`（已有）
- 每条 task 关联 `last_run_id`，通过 `GET /v1/runs/{run_id}` 读取状态

---

## 三、Center — Run Timeline

### Thread Header（固定）
- task title（可编辑）
- run status chip：running / waiting_review / completed / failed
- Stop 按钮（run 进行中时可见）
- 历史 run 切换器（v0.1：最近 runs 摘要；v0.5：完整 run timeline 切换）
- Retry 按钮（failed / interrupted run 可见）
- Continue 按钮（completed 或 waiting_review 后可见）

### Event Stream（滚动，新事件追加到底部）

每种 event 的展示形态：

#### message（用户 prompt）
```
┌ 👤 You ──────────────────────────────────┐
│ 帮我重构 services/auth.py 的错误处理逻辑   │
└───────────────────────────────────────────┘
```

#### message（assistant 输出）
```
┌ ◆ Hermes ─────────────────────────────────┐
│ 我将分析当前错误处理模式，然后进行重构。    │
└────────────────────────────────────────────┘
```

#### reasoning（默认折叠）
```
▶ Thinking  [展开]
```
展开后显示 thinking block 文本，带灰色背景。

#### tool_call（compact 默认）
```
┌ ⚙ read_file  ✓ 230ms ────────────────────┐
│ services/auth.py                  [展开 ▾] │
└────────────────────────────────────────────┘
```
展开后显示 args（JSON）+ result 摘要 + stdout/stderr（如有）。
v0.5 增加 raw tab。

#### tool_result with diff
```
┌ ⚙ write_file  ✓ 180ms ───────────────────┐
│ services/auth.py  [3 additions, 7 deletions] │
│ [查看 Diff →]                              │
└────────────────────────────────────────────┘
```
点击"查看 Diff"打开右侧 Diff Rail。

#### log
```
  · [13:24:01] Running test suite...
  · [13:24:03] 12 passed, 0 failed
```
小号字体，灰色，不占主要视觉权重。

#### approval_needed（Review Checkpoint）
```
┌─────────────────────────────────────────────┐
│  ◉ Review Checkpoint                         │
│  agent 已完成文件修改，等待确认后继续。        │
│                                              │
│  [Continue]  [Accept]  [Done]                │
└─────────────────────────────────────────────┘
```
此卡片出现时 timeline 滚动暂停，ReviewBar 同时激活。

#### completed / failed
```
  ✓ Run completed  · 2m 34s  · 4 tools  · 3 files changed
  ✗ Run failed: timeout after 120s
```
完成态显示 `Continue`；失败态显示 `Retry` 和失败原因摘要。

### Input Bar（底部固定）
- 多行文本输入
- 附件 / context 文件夹（v0.5）
- 发送按钮，快捷键 Cmd+Enter
- run 进行中时禁用主发送，保留 Stop
- run 结束后输入框文案变为"继续这个任务"，提交后创建新的 Agent Run

---

## 四、Right Rail — Diff / Changed Files / Logs

v0.1 允许右栏收起，但一旦打开必须默认进入 Changed Files，而不是设置、模型或系统日志。右 rail toggle 按钮在 Thread Header 右侧。

打开时显示 tab 栏：

### Changed Files Tab（v0.1 默认）
- 本次 run 修改过的文件列表
- 每个文件显示 additions / deletions / status
- 点击文件打开 Diff Tab 并定位该文件
- `Open in Editor` 按钮打开本地编辑器中的真实文件
- 无文件变更时显示空状态：`本次 run 未修改文件`

### Diff Tab
- 按 tool call 分组的文件 diff
- unified diff，语法高亮
- v0.5：accept / reject / partial accept

### Logs Tab
- 当前 run 的结构化日志
- 按 tool call 分组
- 来源：`/v1/runs/{run_id}/events` 中 log 类型 events
- v0.5：全文搜索

### Files Tab（v0.5）
- workspace 文件树
- 标记本次 run 修改过的文件

### Artifacts Tab（v1.0）
- run 生成的文件、截图、预览

---

## 五、Status Bar（底部固定）

```
● Gateway: Connected  │  ◆ Run: waiting_review  │  ⏱ 2m 34s  │  claude-opus-4-7  │  ⚠ Review needed
```

各区段：

| 区段 | 内容 | 来源 |
|---|---|---|
| Gateway | Connected / Disconnected / Error | `/api/status` |
| Active Run | run status + run_id 后 4 位 | SSE or poll |
| Timer | run 开始至今elapsed time | 前端计时 |
| Model | 当前默认模型 | `/api/model/default` 或 config |
| Review State | 有 waiting_review 时高亮提示 | SSE event |

点击任意区段可打开对应 overlay（Gateway → System overlay，Model → Settings）。

---

## 六、Overlays（全局层）

覆盖在主界面上，按需打开，不打断 timeline 状态。

| Overlay | 触发 | 内容 |
|---|---|---|
| System / Gateway | Status Bar 点击 | gateway 健康、日志流、重启 |
| Settings | Cmd+, | model、API keys、config |
| Agents（v1.0） | Status Bar 点击 | agent fleet，spawn tree |
| Command Center（v1.0） | Cmd+K | 跨 task/run 搜索 |

---

## 七、参考来源决策表

| 决策类型 | 参考来源 | 不参考 |
|---|---|---|
| 整体信息架构（三栏 + status bar + timeline 聚合） | NousResearch desktop | fathah desktop |
| 工程分层（Electron bridge、typed preload API） | fathah desktop | NousResearch desktop |
| 数据模型（Task/Run/Event/Review） | 当前 Hermes 后端 | 两个外部仓库 |
| Event contract | 当前 `/v1/runs/events` SSE | 官方 gateway JSON-RPC |
| 历史 timeline 重建 | fathah `sessions.ts` 模式 | — |

---

## 八、主链路后端 API 映射

每个 UI 节点对应的已有后端 API，v0.1 不需要新建 API：

| UI 节点 | 后端 API | 状态 |
|---|---|---|
| Project | session cwd / workspace config | 已有 |
| Task Thread 列表 | `GET /kanban/tasks` | 已有 |
| 发起 Run | `POST /v1/runs` | 已有 |
| Run 状态 | `GET /v1/runs/{run_id}` | 已有 |
| Run History | kanban task runs / local DB adapter | 需确认字段 |
| Timeline events | `GET /v1/runs/{run_id}/events` SSE | 已有 |
| Changed Files | run events 中 diff/tool_result 聚合 | 需前端适配 |
| Open in Editor | desktop shell open file command | 需技术栈决策 |
| Stop | `POST /v1/runs/{run_id}/stop` | 已有 |
| Review 决策 | `POST /v1/runs/{run_id}/approval` | 已有 |
| Gateway 状态 | `GET /api/status` | 已有 |
| 默认模型 | `GET /api/model/default` | 已有 |

---

## 九、Codex-like 体验检查清单

v0.1 设计完成时必须逐项满足：

- 主链路不超过：选择任务 -> 发起/继续 run -> review diff -> done。
- 中心区域不是聊天泡泡列表，而是 run timeline。
- 右侧默认优先显示 Changed Files，而不是设置、模型或系统日志。
- 任一 failed/interrupted run 都有 Retry。
- 任一 completed run 都能 Continue 成新的 run。
- 任一 changed file 都能打开 diff，并能 Open in Editor。
- Gateway/settings 只作为 status bar 或 overlay，不抢占主流程。
