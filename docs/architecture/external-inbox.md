# External Inbox 架构

版本：v0.8-draft
日期：2026-06-04

---

## 一、设计目标

Feishu / Discord / CLI / Scheduler 等外部入口只能向 Inbox 投递消息，不能直接执行代码、不能自动创建 run、不能绕过 Permission Gate。用户在 Inbox 中审查后手动将消息转化为 Task Thread，之后走标准的 Run → Review → Done 流程。

---

## 二、InboxItem 数据模型

```typescript
interface InboxItem {
  id: string
  source: InboxSource
  raw_payload: unknown          // 原始消息体，只读，不直接注入 prompt
  normalized: TaskDraft         // 系统从 raw_payload 提取的结构化草稿
  status: InboxStatus
  created_at: string
  expires_at?: string           // Scheduler 任务有过期时间
  linked_task_id?: string       // 转化为 Task Thread 后填入
  rejected_reason?: string
}

type InboxSource = 'manual' | 'cli' | 'feishu' | 'discord' | 'scheduler'

type InboxStatus =
  | 'pending'       // 等待用户处理
  | 'confirmed'     // 用户已转化为 Task Thread
  | 'rejected'      // 用户拒绝
  | 'archived'      // 用户存档（不拒绝但暂不处理）
  | 'expired'       // 超过 expires_at 未处理

interface TaskDraft {
  title: string               // 系统提取的任务标题，用户可编辑
  suggested_prompt: string    // 系统建议的 prompt，用户可编辑后才使用
  suggested_executor?: ExecutorType
  project_hint?: string       // 推测的目标 project（用户确认）
  priority?: 'high' | 'normal' | 'low'
  tags?: string[]
}
```

`suggested_prompt` 是系统基于 `raw_payload` 提取的建议，**不直接用于 run**。用户在确认时可修改，最终使用的是用户编辑后的版本。

---

## 三、各 Source 的投递方式

| Source | 投递方式 | raw_payload 内容 |
|---|---|---|
| `manual` | Desktop UI 直接新建 | 用户输入的 title + prompt |
| `cli` | `hermes inbox add --title "..." --body "..."` | `{title, body, project?}` |
| `feishu` | Feishu bot webhook → Hermes inbox API | `{message_id, chat_id, sender, content, thread_id?}` |
| `discord` | Discord bot → Hermes inbox API | `{message_id, channel_id, author, content}` |
| `scheduler` | cron / task scheduler → inbox API | `{schedule_id, job_name, prompt, target_project, due_at}` |

所有外部 source 通过 `POST /v1/inbox` 写入，需要有效 API key，不对公网开放。

---

## 四、raw_payload 到 TaskDraft 的归一化

各 source 的归一化由 `InboxNormalizer` 处理，规则：

```
feishu:    content.text → suggested_prompt
           chat_id      → project_hint（若有绑定关系）

discord:   content      → suggested_prompt
           channel_id   → project_hint（若有绑定关系）

cli:       body         → suggested_prompt
           title        → title

scheduler: prompt       → suggested_prompt
           job_name     → title
           target_project → project_hint

manual:    直接使用用户输入，无需归一化
```

归一化只做文本提取，**不做 LLM 推理**（避免外部消息触发 token 消耗）。`suggested_prompt` 截断上限为 2000 字符，超出部分在 UI 中提示用户手动补充。

---

## 五、流程

```
外部消息（Feishu / Discord / CLI / Scheduler）
       │
       ▼
POST /v1/inbox（需 API key）
       │
       ▼
InboxNormalizer.normalize(raw_payload, source)
       │
       ▼
InboxItem 写入 DB，status = 'pending'
       │
       ▼  [桌面通知 / Inbox badge 更新]
       │
用户打开 Inbox，查看 pending 列表
       │
  ┌────┴──────────┬────────────┐
  ▼               ▼            ▼
Confirm         Reject       Archive
  │               │
  ▼               ▼
用户编辑         InboxItem
suggested_prompt  status = 'rejected'
+ 选择 Project
+ 选择 Executor
  │
  ▼
Orchestrator.createTaskThread(draft)
  │
  ▼
Task Thread（status: draft）
  │
  ▼
用户在 Task Thread 中发起 Run
（走标准 Worktree / Run / Review 流程）
  │
  ▼
InboxItem.linked_task_id = thread.id
InboxItem.status = 'confirmed'
```

用户"确认"只是将 InboxItem 转化为 Task Thread（draft 状态），**不自动发起 run**。

---

## 六、Result 回写

run 完成（done 状态）后，若 Task Thread 来自 Inbox，系统可向来源回写结果摘要：

```typescript
interface InboxResultCallback {
  inbox_item_id: string
  run_id: string
  status: 'done' | 'failed'
  summary: string         // run 完成摘要，< 500 字符
  changed_files_count: number
  review_decision: ReviewDecisionType
}
```

回写规则：
- feishu：向原始消息所在 thread 回复摘要（通过 Feishu bot API）
- discord：向原始消息所在 channel 回复（通过 Discord bot API）
- cli：写入 `~/.hermes/inbox-results/<item_id>.json`
- scheduler：更新 scheduler job 状态
- **回写内容只包含摘要，不包含 diff、代码或 prompt snapshot**
- 回写失败不阻塞 run 完成流程，记录为警告

---

## 七、UI 设计

### 7.1 Inbox 页面

路径：Left Rail 底部 Inbox badge（未读数），或 Cmd+I

```
┌─ Inbox ────────────────────────────────────────────────┐
│  [全部]  [Feishu]  [Discord]  [CLI]  [Scheduler]       │  ← source filter
│  ──────────────────────────────────────────────────    │
│  ● 重构 auth 错误处理          Feishu · 5 分钟前        │
│    "帮我重构 services/auth.py..."  [Convert] [Reject]  │
│                                                        │
│  ● 每日代码 review              Scheduler · 今天 09:00 │
│    "review 昨日新增 PR..."     [Convert] [Reject]      │
│                                                        │
│  ○ Fix login bug               CLI · 昨天              │  ← archived
│    "登录 500 错误..."          [Restore] [Delete]      │
│  ──────────────────────────────────────────────────    │
│  已处理: 12 confirmed  3 rejected  2 archived          │
└────────────────────────────────────────────────────────┘
```

- 未读 pending 条目在 Left Rail badge 上显示数量
- `●` = pending，`○` = archived，灰色 = confirmed/rejected

### 7.2 Convert to Task 对话框

点击 `[Convert]` 后弹出：

```
┌─ Convert to Task ──────────────────────────────────────┐
│  Source: Feishu  ·  5 分钟前                           │
│                                                        │
│  Title:  [重构 auth 错误处理            ]  ← 可编辑    │
│                                                        │
│  Prompt: [帮我重构 services/auth.py     ]  ← 可编辑    │
│          [的错误处理逻辑，统一 exception ]              │
│          [格式，增加日志                ]              │
│  ⚠ Raw payload 已截断，原始内容 2340 字，显示 2000 字   │
│                                                        │
│  Project:   [hermes  ▾]                                │
│  Executor:  [Codex CLI (推荐) ▾]                       │
│                                                        │
│  [查看原始消息]  [Create Task]  [Reject]               │
└────────────────────────────────────────────────────────┘
```

- `suggested_prompt` 预填入编辑框，用户必须看到内容才能确认
- "查看原始消息"展开 `raw_payload` 原文（只读）
- 用户修改 prompt 后提交，修改记录在 `TaskDraft` 中（`user_edited: true`）

### 7.3 Linked Task 入口

confirmed InboxItem 显示：

```
  ✓ 重构 auth 错误处理          Feishu · confirmed
    → Task: hermes/a3f8c1b2  [跳转 →]
```

点击"跳转"直接打开关联的 Task Thread。

### 7.4 Source Filter

Inbox 顶部 tab 栏按 source 过滤，badge 只显示 pending 数量：

```
[全部 (4)]  [Feishu (2)]  [Discord (0)]  [CLI (1)]  [Scheduler (1)]
```

---

## 八、安全边界（硬约束）

| 约束 | 实现位置 |
|---|---|
| 外部入口不能直接执行代码 | `/v1/inbox` 只写 InboxItem，不调用 Orchestrator.createRun |
| 外部入口不能自动确认 | status 从 `pending` 到 `confirmed` 只能由用户点击触发，无 API 可绕过 |
| 外部入口不能绕过 Permission Gate | Task Thread 从 `draft` 发起 run 走标准 Orchestrator 流程 |
| raw_payload 不污染 prompt | `suggested_prompt` 由 `InboxNormalizer` 提取，用户在编辑框中修改后才使用；`raw_payload` 不传给 executor |
| result 回写必须绑定 task/run | `InboxResultCallback` 需要有效 `run_id` 和 `inbox_item_id` 才能写入 |
| 回写内容不含代码或 diff | `InboxResultCallback.summary` 字段限 500 字符纯文本 |
| Scheduler 任务不绑定执行器 | `scheduler` source 只提供 `suggested_prompt`，executor 选择由用户在 Convert 时决定 |
