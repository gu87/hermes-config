# Hermes 统一 Task / Run 合同设计

> 状态：**审计阶段（Phase 0）**
> 日期：2026-06-09
> 本文档仅做代码与文档审计，不修改任何运行时代码、配置、数据库或现有文档。

---

## 1. 审计范围

### 1.1 已审计的文档

| 文档 | 路径 |
|------|------|
| 多 Agent 体系全景图 | `docs/hermes-multi-agent-architecture-2026-06-08.md` |
| 桌面应用架构详解 | `docs/hermes-desktop-architecture-2026-06-08.md` |
| Desktop 状态模型 | `docs/architecture/hermes-desktop-state-model.md` |
| Run Orchestrator 设计 | `docs/architecture/run-orchestrator.md` |
| Agent Adapter 层设计 | `docs/architecture/agent-adapter-layer.md` |
| ADR: Control-plane-first Workbench | `docs/adr/ADR-codex-like-desktop-workbench-control-plane-first.md` |

### 1.2 已审计的代码实现

| 机制 | 关键文件 | 行数 |
|------|----------|------|
| 实时委托 | `hermes-agent/tools/delegate_tool.py` | 2,831 |
| Kanban 数据库 | `hermes-agent/hermes_cli/kanban_db.py` | ~3,000+ |
| Kanban CLI | `hermes-agent/hermes_cli/kanban.py` | ~2,200+ |
| Kanban Swarm | `hermes-agent/hermes_cli/kanban_swarm.py` | ~200 |
| Task Card 组装 | `scripts/compile-task.py` | ~350 |
| 任务派发 | `scripts/dispatch-task.py` | ~250 |
| 结构验收 | `scripts/verify-task.py` | ~350 |
| 语义验收 | `scripts/review-task.py` | ~250 |
| Gate 总闸 | `scripts/run-task-gate.py` | ~300 |
| 运行账本 | `scripts/run-ledger.py` | ~250 |
| Gate 策略 | `scripts/gate-policy.py` | 221 |
| Gateway 代理缓存 | `hermes-agent/gateway/run.py` | ~16,000+ |
| 代理注册表 | `config/managed-agents.yaml` | 657 |
| 代理注册表 JSON | `config/agent-registry.json` | ~400 |

### 1.3 文档与代码差异

| 差异点 | 文档描述 | 实际代码 |
|--------|----------|----------|
| pipeline 脚本位置 | 多 Agent 架构文档写 `hermes-agent/scripts/` | 实际位于 `/Users/gu/.hermes/scripts/`（HERMES_HOME 根级别，非 hermes-agent 子目录） |
| `_AGENT_CACHE_MAX_SIZE` | 文档说 128 | 代码确认 128，另有 1h TTL（`_AGENT_CACHE_IDLE_TTL_SECS = 3600`） |
| Desktop `RunStatus` | 文档定义了 `created/queued/starting/running/waiting_review/completed/failed/cancelled` | 仅存在于设计文档中，v0.1 尚未实现运行时代码 |
| Desktop `TaskThread` | 文档定义了完整模型 | 仅存在于设计文档中，尚未实现 |
| `HERMES_KANBAN_DB` env | 多 Agent 文档提到此变量 | Kanban 代码使用 `HERMES_KANBAN_BOARD` + `HERMES_KANBAN_HOME` 做路径解析，`HERMES_KANBAN_DB` 为 legacy fallback |
| Kanban `session_id` | 多 Agent 文档未提及 | 数据库中实际已存在 `tasks.session_id` 字段，用于链接网关会话 |
| Managed Agent 数量 | 多 Agent 文档称 "9 个注册 Agent" | `managed-agents.yaml` 实际注册了 10 个 Agent（含 2026-05-21 新增的 `opencode`） |

---

## 2. 当前三条执行链的独立定义

### 2.1 执行链 A：对话内实时委托 (delegate_task)

#### 2.1.1 Task

```text
概念：一次委托调用 = 一个或多个 task
标识：无持久化 ID。subagent_id = "sa-{task_index}-{uuid8}"
      例：sa-0-a1b2c3d4
创建：delegate_task(goal="...", context="...", toolsets=[...])
生命周期：函数调用开始 → 子 agent 运行结束 → 结果返回父 agent
持久化：无。完全在内存中。
可嵌套：是（role='orchestrator'，受 max_spawn_depth 限制，默认 1 层）
```

**Task 字段（委托调用级别）：**
| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `goal` | string | 调用者传入 | 任务目标文本 |
| `context` | string? | 调用者传入 | 附加上下文 |
| `toolsets` | string[]? | 调用者传入/继承父 | 工具集列表 |
| `role` | "leaf"\|"orchestrator" | 调用者传入 | 子 agent 是否能再委托 |
| `task_index` | int | 自动分配 | 在 tasks 数组中的 0-based 位置 |
| `subagent_id` | string | 自动生成 | 格式 `sa-{idx}-{uuid8}` |
| `parent_id` | string? | 继承父 agent | 嵌套链路的父 subagent_id |
| `depth` | int | 自动计算 | 0=父 agent, 1=第一层子 agent, ... |

#### 2.1.2 Run

```text
概念：一个子 AIAgent 实例的 run_conversation() 执行
标识：subagent_id 同时承担 task 和 run 的双重身份
      无独立 run ID
范围：从 ThreadPoolExecutor worker 线程启动到 child.close()
状态：running → completed | failed | error | timeout | interrupted
持久化：无。仅在 _active_subagents 字典中注册，最后返回 dict。
```

**Run 结果字段（从 `_run_single_child` 返回）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `task_index` | int | 委托调用中的任务索引 |
| `status` | string | completed/failed/error/timeout/interrupted |
| `summary` | string? | 子 agent 的 final_response |
| `api_calls` | int | LLM API 调用次数 |
| `duration_seconds` | float | 运行耗时 |
| `model` | string? | 实际使用的模型 |
| `exit_reason` | string | completed/interrupted/max_iterations |
| `tokens` | {input, output} | token 用量 |
| `tool_trace` | list | 工具调用追踪 [{tool, args_bytes, result_bytes, status}] |
| `error` | string? | 错误信息（失败时） |
| `_child_role` | string? | 子 agent 的实际 role |
| `_child_cost_usd` | float? | 子 agent 的 API 费用 |

#### 2.1.3 Child Run / Subagent

```text
概念：嵌套委托中的下一级 agent
标识：每个子 agent 有独立的 subagent_id + parent_id
注册：_active_subagents 字典，按 subagent_id 检索
TUI 可查：subagent_id, parent_id, depth, goal, model, started_at, tool_count, status
生命周期事件：spawn_requested → start → thinking/tool → complete
```

#### 2.1.4 Status

**`_active_subagents` 注册表状态：**
| 值 | 含义 |
|----|------|
| `running` | 子 agent 正在执行（注册表中的唯一状态） |

**子 agent 结果状态（`_run_single_child` 返回值）：**
| 值 | 含义 |
|----|------|
| `completed` | 正常完成，有 summary 输出 |
| `failed` | 执行异常（无 summary 输出） |
| `error` | Python 异常被捕获 |
| `timeout` | 超过 child_timeout_seconds（默认 600s） |
| `interrupted` | 被父 agent 中断或 TUI kill 信号 |

#### 2.1.5 Event

**DelegateEvent 枚举（`tools/delegate_tool.py`）：**

| 枚举值 | 对应旧字符串 | 说明 |
|--------|-------------|------|
| `TASK_SPAWNED` | — | 保留，未在当前实现中发出 |
| `TASK_PROGRESS` | `subagent_progress` | 批量化工具进度摘要 |
| `TASK_COMPLETED` | — | 保留，未在当前实现中发出 |
| `TASK_FAILED` | — | 保留，未在当前实现中发出 |
| `TASK_THINKING` | `_thinking` / `reasoning.available` | 推理流 |
| `TASK_TOOL_STARTED` | `tool.started` | 工具调用开始 |
| `TASK_TOOL_COMPLETED` | `tool.completed` | 工具调用完成（仅注册，不 relay 到父） |

**进度回调事件（`subagent.{event}` 字符串，relay 到父 agent 和 Gateway）：**
| 事件字符串 | 方向 | 说明 |
|-----------|------|------|
| `subagent.spawn_requested` | 子→父 | 子 agent 已构建，进入队列 |
| `subagent.start` | 子→父 | 子 agent 开始运行 |
| `subagent.thinking` | 子→父 | 推理内容 |
| `subagent.tool` | 子→父 | 单个工具调用 |
| `subagent.progress` | 子→父 | 批量化工具名称 relay |
| `subagent.complete` | 子→父 | 完成（含 status/duration/tokens/files/cost） |

**Gateway RPC 事件（pushes 到 Desktop/CLI）：**
| 事件 | 说明 |
|------|------|
| `subagent.queued` | 入队等待执行 |
| `subagent.running` | 开始运行 |
| `subagent.progress` | 进度更新 |
| `subagent.thinking` | 思考流 |
| `subagent.completed` | 完成 |
| `subagent.failed` | 失败 |
| `subagent.interrupted` | 被中断 |

#### 2.1.6 Result

委托调用的最终产物是 `delegate_task()` 返回的 JSON 字符串：
```json
{
  "results": [
    {
      "task_index": 0,
      "status": "completed",
      "summary": "...",
      "api_calls": 12,
      "duration_seconds": 45.3,
      "model": "claude-sonnet-4-6",
      "exit_reason": "completed",
      "tokens": {"input": 5000, "output": 1200},
      "tool_trace": [{"tool": "read", "args_bytes": 80, "result_bytes": 2000, "status": "ok"}],
      "error": null
    }
  ],
  "total_duration_seconds": 45.3
}
```

#### 2.1.7 Review / Gate

- **无正式 Review/Gate**。
- 父 agent 自行解读 summary 并决定下一步。
- 子 agent 危险命令审批：由 `delegation.subagent_auto_approve` 配置控制（默认 auto-deny）。
- TUI 提供 kill/pause 手动控制。

---

### 2.2 执行链 B：Kanban 持久化调度

#### 2.2.1 Task

```text
概念：Kanban 看板上的一个卡片
标识：TEXT PRIMARY KEY（如 t6, t6-wire-fix）
创建：hermes kanban create "title" --assignee <profile>
持久化：SQLite kanban.db → tasks 表
状态机：triage → todo → scheduled → ready → running → blocked/review → done → archived
可关联：session_id（来源网关会话）、workflow_template_id + current_step_key（v2 工作流）
```

**`tasks` 表核心字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | 任务 ID，如 "t6" |
| `title` | TEXT | 任务标题 |
| `body` | TEXT | 详细说明（可选） |
| `assignee` | TEXT | 负责的 profile 名称 |
| `status` | TEXT | triage/todo/scheduled/ready/running/blocked/review/done/archived |
| `priority` | INTEGER | 优先级（默认 0） |
| `tenant` | TEXT | 命名空间隔离 |
| `workspace_kind` | TEXT | scratch/worktree/dir |
| `workspace_path` | TEXT | 工作空间绝对路径 |
| `branch_name` | TEXT | worktree 的 git 分支名 |
| `claim_lock` | TEXT | CAS 抢占令牌 |
| `claim_expires` | INTEGER | 抢占过期时间戳 |
| `worker_pid` | INTEGER | worker 子进程 PID |
| `current_run_id` | INTEGER | 指向 task_runs 的当前活跃 run |
| `consecutive_failures` | INTEGER | 连续失败计数（断路器） |
| `result` | TEXT | 最终结果文本 |
| `session_id` | TEXT | 来源网关会话 ID |
| `skills` | TEXT (JSON) | 强制加载的 skill 列表 |
| `max_retries` | INTEGER | 每任务重试上限 |
| `goal_mode` | INTEGER | 是否启用 goal loop 模式 |
| `created_by` | TEXT | 创建者 |
| `created_at` / `started_at` / `completed_at` | INTEGER | 时间戳 |

#### 2.2.2 Run

```text
概念：对任务的单次执行尝试
标识：INTEGER PRIMARY KEY AUTOINCREMENT（如 1, 2, 3...）
创建：dispatcher claim 任务时自动创建 task_runs 行
持久化：SQLite kanban.db → task_runs 表
与 Task 关系：多对一（一个 task 可有多条 run，每次 retry 创建一个新 run）
```

**`task_runs` 表：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 run ID |
| `task_id` | TEXT | 外键关联 tasks.id |
| `profile` | TEXT | 执行此 run 的 profile |
| `step_key` | TEXT | v2 工作流步骤键（当前 nullable，kernel 忽略） |
| `status` | TEXT | running/done/blocked/crashed/timed_out/failed/released |
| `claim_lock` | TEXT | 抢占令牌 |
| `claim_expires` | INTEGER | 抢占过期时间戳 |
| `worker_pid` | INTEGER | worker 进程 PID |
| `max_runtime_seconds` | INTEGER | 运行时上限 |
| `last_heartbeat_at` | INTEGER | 最后心跳时间戳 |
| `started_at` | INTEGER | 开始时间戳 |
| `ended_at` | INTEGER | 结束时间戳 |
| `outcome` | TEXT | completed/blocked/crashed/timed_out/spawn_failed/gave_up/reclaimed |
| `summary` | TEXT | 结构化 handoff 摘要 |
| `metadata` | TEXT (JSON) | 结构化事实数据 |
| `error` | TEXT | 错误信息 |

#### 2.2.3 Child Run / Subagent

```text
概念：Kanban Swarm 中的并行 worker
模型：planning_root → [worker A, worker B, worker C] → verifier → synthesizer
实现：每个 worker 是独立的 Kanban Task（有独立 task_id + runs）
关联：通过 task_links (parent_id, child_id) 建立父子关系
共享：通过 root task 的 task_comments（结构化 JSON blackboard）
```

#### 2.2.4 Status

**Task 状态流转：**
```
triage → todo → scheduled → ready → running → done
                           ↓          ↓
                         (跳过)    blocked → ready → running
                                     ↓
                                   review → done
                            running → archived (取消)

任意活跃状态 → archived（手动归档）
```

**Run 状态流转：**
```
[claim 时创建] → running
                  ├→ done       (outcome: completed)
                  ├→ blocked    (outcome: blocked)
                  ├→ crashed    (outcome: crashed)
                  ├→ timed_out  (outcome: timed_out)
                  ├→ failed     (outcome: spawn_failed)
                  └→ released   (outcome: reclaimed / gave_up)
```

#### 2.2.5 Event

**`task_events` 表：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增事件 ID |
| `task_id` | TEXT | 关联任务 |
| `run_id` | INTEGER | 关联 run（可空） |
| `kind` | TEXT | 事件类型 |
| `payload` | TEXT (JSON) | 事件负载 |
| `created_at` | INTEGER | 时间戳 |

**事件种类（kind）：**
`created` `assigned` `claimed` `claim_rejected` `promoted`（原 `ready`）`running` `completed` `blocked` `unblocked` `archived` `scheduled` `reprioritized`（原 `priority`）`gave_up`（原 `spawn_auto_blocked`）`crashed` `timed_out` `reclaimed` `heartbeat` `comment`

**Gateway notifier 关注的终端事件种类（TERMINAL_KINDS）：**
`completed` `blocked` `gave_up` `crashed` `timed_out` — 这些事件通过 `_kanban_notifier_watcher` 推送到订阅该 task 的 gateway 平台（飞书/微信等），订阅在 task 到达 `done` 或 `archived` 后自动移除。

#### 2.2.6 Result

```text
任务级结果：
  tasks.result          — 文本摘要
  tasks.consecutive_failures — 断路器计数
运行级结果：
  task_runs.summary     — 结构化 handoff 摘要（供下游 worker 读取）
  task_runs.metadata    — JSON 结构化事实（如 changed_files, tests_run）
  task_runs.error       — 错误文本
  task_runs.outcome     — 终态分类
```

#### 2.2.7 Review / Gate

```text
- review status: 任务可标记为 review 状态（阻塞后续流程）。
  review 状态的 task 通过 claim_review_task() 独立抢占（review -> running），
  创建新的 task_runs 行，与原始 worker run 分离追踪。这等效于 Kanban 内置的
  "review agent" 机制——一个 task 被标记为 review 后，会由专门的审核方
  （如 ambrosini）claim 并执行，结果写入 review run 的 summary/metadata。
- kanban_diagnostics: 规则引擎计算 board 级和 task 级诊断
  - severity: warning / error / critical
  - 诊断类型：stale-claim, crash-loop, orphan-run, exceed-max-runtime, ...
- 断路器：consecutive_failures 超过 max_retries 后自动 gave_up
- notifier 推送：终端事件通过 _kanban_notifier_watcher 推送到订阅 gateway
  平台（每 5s 轮询，订阅在 task done/archived 后自动移除）
- 无结构化 Gate 策略文档（不同于 pipeline 的 gate-policy.py），但 review
  claim 机制提供了等效的 "人工/Gate Agent 审核后再决定" 的路径
```

---

### 2.3 执行链 C：Task Card Pipeline

#### 2.3.1 Task

```text
概念：以 JSON 文件形式存在的 Task Card
标识：task_card_id 或 task_id（来自 compiled_intent 或自动生成）
创建：compile-task.py 将意图 + 记忆库 + Agent Registry 合并
持久化：文件系统 ~/.claude/teams/<project>/inbox/<task_id>.json
状态：created → dispatched → running → waiting_for_verification → 
       needs_human_review / completed / discarded / failed / blocked
```

**Task Card JSON 核心字段（来自 compile-task.py）：**
| 字段 | 说明 |
|------|------|
| `task_card_id` | 唯一标识 |
| `project` | 项目名 |
| `compiled_intent` | 意图编译结果（raw_request, interpreted_intent, real_task, risk_level, task_category...） |
| `execution_plan` | 执行计划（primary_agent, mode, agents） |
| `output_contract` | 输出约定（path, schema_version, required_fields） |
| `allowed_files` | 允许修改的文件范围 |
| `context` | 项目上下文（project_context, user_preferences, feedback_memory） |

#### 2.3.2 Run

```text
概念：一次 dispatch-task.py → hermes -z → outbox.json 的子进程执行
标识：run_{task_id}_{timestamp}（如 run_t6-wire-fix_20260307_152200_123456）
创建：run-ledger.py 的 run_with_ledger() 在子进程启动时写入
持久化：ledger.jsonl（~/.claude/teams/<project>/runs/ledger.jsonl）
与 Task 关系：多对一（一次 task 可以经历多轮 dispatch-verify-review 迭代）
```

**ledger.jsonl Run 记录结构：**

run_started 事件：
```json
{
  "schema_version": "2.8",
  "event": "run_started",
  "run_id": "run_t6_20260307_152200_123456",
  "task_id": "t6",
  "agent_id": "claude",
  "run_type": "main",
  "started_at": "2026-03-07T15:22:00.123456+00:00",
  "command": "hermes -z ...",
  "cwd": "/path/to/project",
  "timeout_seconds": 600
}
```

run_finished 事件：
```json
{
  "schema_version": "2.8",
  "event": "run_finished",
  "run_id": "run_t6_20260307_152200_123456",
  "task_id": "t6",
  "agent_id": "claude",
  "run_type": "main",
  "exit_code": 0,
  "classification": "ok",
  "duration_seconds": 45.3,
  "stdout_tail": "...",
  "stderr_tail": "..."
}
```

**Run 分类（classification）：** `ok` `timeout` `permission_error` `auth_error` `rate_limited` `process_error`

**Revision dispatch sub-run：** 当 gate 决策为 `revision_needed` 且 policy 允许 `auto_dispatch_allowed` 时，
`run-task-gate.py` 的 `--auto-dispatch-revision` 标志会触发二次 `run_with_ledger()`，
创建 `run_type="revision_dispatch"` 的子 run。该 run 有独立的 `run_id`、`exit_code`、
`classification`，记录在 gate record 的 `revision_dispatch` 字段中。

#### 2.3.3 Child Run / Subagent

```text
- Pipeline 不直接管理子 agent 内部结构
- dispatch-task.py 通过 hermes -z 调用 delegate_task，子 agent 的执行细节对 pipeline 透明
- 子 agent 的输出写入 outbox.json 即被视为整体 run 结果
- 无子 agent 树的可观测性（pipeline 视角只能看到一件事：hermes 进程退出码 + stdout）
- 例外：run-task-gate.py 的 --auto-dispatch-revision 会创建 revision dispatch sub-run
  （run_type="revision_dispatch"），其 run_id、exit_code、classification 记录在 gate
  record 的 revision_dispatch 字段和 ledger.jsonl 中
```

#### 2.3.4 Status

**verify-task.py 定义的 TASK_STATUSES：**
| 值 | 说明 |
|----|------|
| `created` | 已创建 |
| `dispatched` | 已派发 |
| `running` | 运行中 |
| `waiting_for_verification` | 等待验证 |
| `needs_human_review` | 需要人工审查 |
| `completed` | 完成 |
| `discarded` | 已丢弃 |
| `failed` | 失败 |
| `blocked` | 阻塞 |

**TERMINAL 状态：** `completed` `discarded` `failed` `blocked`

**Outbox 状态（`VALID_OUTBOX_STATUSES`）：** `success` `failed` `blocked`

**Outbox next_action：** `complete` `review` `revision` `manual_review`

#### 2.3.5 Event

Pipeline 有两层事件记录机制：

**A. ledger.jsonl（`run-ledger.py`，3 种 event 类型）：**

| event 类型 | 说明 |
|-----------|------|
| `lifecycle_event` | 管道阶段事件（phase: compiled/dispatched/revision_created/gate_checked/revision_dispatched/revision_dispatch_timeout/revision_dispatch_skipped/revision_policy_blocked/revision_limit_reached） |
| `run_started` | 子进程执行开始（含 run_id, task_id, agent_id, run_type, command） |
| `run_finished` | 子进程执行结束（含 exit_code, classification, duration_seconds, stdout_tail, stderr_tail） |

**B. events.jsonl（`run-task-gate.py` 的 `record_event()`，管道特有事件）：**

| event | 说明 |
|-------|------|
| `gate_checked` | gate 审查完成（含 decision, policy_action） |
| `revision_created` | revision inbox 已生成（含 revision_task_id, attempt） |
| `revision_dispatched` | revision 已派发（含 run_id, exit_code, classification） |
| `revision_dispatch_timeout` | revision 派发超时 |
| `revision_dispatch_skipped` | policy 不允许 auto dispatch |
| `revision_policy_blocked` | policy 不允许 auto revision |
| `revision_limit_reached` | 已达到 max_revisions 上限 |

`tasks/index.jsonl` 同样由 `record_event()` 写入，但它是从管道事实派生的查询索引，不是权威事实源。
Phase 1B 已审计该文件，并永久排除其读取和映射；索引缺失、损坏或内容变化不得影响 Shadow Projection。

**注意**：Pipeline 的事件模型在子进程运行期间是盲区——没有流式事件（tool_call, reasoning, thinking），
没有审批事件（approval_needed）。整个子进程运行期间管道只能看到 "started → finished" 两个边界事件。

#### 2.3.6 Result

**主产物：outbox.json（由 Agent 写入文件系统）**
```json
{
  "schema_version": "2.8",
  "task_id": "t6",
  "agent_id": "claude",
  "status": "success",
  "summary": "...",
  "changed_files": ["path/to/file.py"],
  "changed_files_source": "git_diff",
  "verification": {
    "commands_run": ["pytest"],
    "output_summary": "All tests passed"
  },
  "evidence": {
    "changed_files": [...],
    "verification_commands": [...],
    "verification_output_summary": "...",
    "known_risks": [...]
  },
  "known_risks": [],
  "errors": [],
  "error_taxonomy": {},
  "needs_human_review": false,
  "notes": ""
}
```

#### 2.3.7 Review / Gate

**Gate 执行流程（`run-task-gate.py` 的 `run_gate()` + `apply_gate_policy()`）：**

```
[1] verify-task.py (subprocess)
     → 结构验证：JSON 合法性、required_fields、task_id 匹配、changed_files 范围、文件存在/修改
     → exit 0 (pass) / exit 1 (fail) / exit 2 (needs_human_review)
     → fail 时：直接生成 failure record（decision=revision_needed 或 rejected），
       跳过 review-task.py

[2] review-task.py (subprocess，仅在 verify pass 后运行)
     → 语义验证：goal 对齐、allowed_files 越界、must_avoid 违反、must_keep 覆盖、evidence
     → 输出：approved / revision_needed / rejected（含 failed_checks + revision_instructions）

[3] apply_gate_policy() (subprocess 调用 gate-policy.py)
     → gate-policy.py 定义了两套路由函数：
       a. policy_for_v2_8_1（taxonomy-driven）：基于 review 输出的 taxonomy code
          自动路由到 complete/auto_revision/reject/manual_review/switch_agent。
          当前已定义但 CLI main() 未调用；仅在内部通过 policy_for 的 fallback 链间接触达。
       b. policy_for（legacy check-name 路由）：基于 failed check names 分类。
          当前 CLI main() 实际调用的入口，是生产生效的策略。
     → 输出 policy JSON：{policy_action, policy_reason, auto_revision_allowed, auto_dispatch_allowed}

[4] revision 处理（在 run-task-gate.py main() 内）
     → decision=revision_needed + auto_revision_allowed=true
       → build_revision_inbox() → write_revision_inbox()
       → 可选 --auto-dispatch-revision 自动调用 dispatch-task.py
     → decision=revision_needed + auto_revision_allowed=false
       → 直接退出，不生成 revision inbox
     → revision limit 达到 → manual_review
```

**Gate 决策：**
| 决策 | 行为 |
|------|------|
| `approved` | 写入 output gate record JSON，ledger 记录 lifecycle_event(gate_checked)，events.jsonl 记录 gate_checked |
| `revision_needed` | policy 允许时生成 revision inbox（含 revision_brief + output_contract）→ 可选自动重新 dispatch |
| `rejected` | 终止，写入 output gate record JSON |

**gate-policy.py 的关键策略常量与调用关系：**
- CLI 入口：`main()` → `policy_for()`（legacy 路径，生产生效）
- `AUTO_REVISION_CHECKS`：`evidence_quality, changed_files_source, invalid_output_schema, required_fields, must_keep_reflected, must_change_fulfilled, success_criteria_mentioned` — 这些检查失败可自动 revision
- `HARD_STOP_CHECKS`：`allowed_files_check, must_avoid_respected` — 这些检查失败直接 reject
- `_TAXONOMY_POLICY`：9 种 taxonomy code → (action, auto_revision, auto_dispatch) 映射表。仅被 `policy_for_v2_8_1()` 使用，该函数已定义但 CLI 未直接调用；`policy_for()` 内部不读取 `_TAXONOMY_POLICY`
- 当前生产策略优先级（`policy_for`）：timeout → hard-stop → revision limit → auto_revision（check-name 匹配 `AUTO_REVISION_CHECKS`）→ manual_review（unclassified checks）

---

### 2.4 执行链 D：Gateway 会话（隐式机制）

Gateway 会话本身不是"执行链"，但它是所有交互的上游入口，需要纳入合同：

```text
概念：一个网关会话 = 一个平台用户在一个 chat/thread 中的对话
标识：SessionKey = platform + chat_id + thread_id （agent cache 键）
      SessionDB session_id = UUID（持久化到 state.db）
生命周期：首条消息创建 → 每轮复用缓存 agent → 闲置 1h 驱逐 → Gateway 重启后重建
Agent 缓存：_agent_cache (OrderedDict, max 128 entries, LRU 淘汰)
```

---

## 3. 重复、冲突、缺失分析

### 3.1 Task ID 体系碎片化

| 机制 | ID 格式 | ID 空间 | 跨系统唯一？ |
|------|---------|---------|-------------|
| delegate_task | `sa-{idx}-{uuid8}` | 进程内 | ❌ 不跨调用 |
| Kanban Task | TEXT（如 t6） | 单 board 内 | ❌ 不跨 board |
| Pipeline Task Card | task_card_id（如 staam_t6） | 单 project 内 | ❌ 不跨 project |
| Desktop TaskThread | UUID（设计） | 全局 | ✅ 但未实现 |

**冲突：** 同一个用户请求在 Gateway 中有 session_id，在 Kanban 中有 task_id（经由 session_id 弱关联），在 Pipeline 中有 task_card_id。三者互不引用，无法统一追踪完整生命周期。

### 3.2 Run ID 三套体系

| 机制 | Run ID | 持久化 | 与 Task 关联 |
|------|--------|--------|-------------|
| delegate_task | 无独立 run ID（subagent_id 同时是 task 和 run） | ❌ | N/A |
| Kanban | INTEGER AUTOINCREMENT | ✅ | 通过 task_id + tasks.current_run_id |
| Pipeline | `run_{task_id}_{timestamp}` | ✅ (ledger.jsonl) | 通过 task_id |
| Desktop 设计 | UUID | 待实现 | 通过 thread_id |

### 3.3 Status 状态词汇冲突

不同机制中"同样的词"表示不同语义：

| 词汇 | delegate_task | Kanban | Pipeline | Desktop 设计 |
|------|--------------|--------|----------|-------------|
| `completed` | 有输出 ≠ 完成工作 | N/A（task 用 `done`） | task 终态 | run 终态 |
| `running` | 注册表中所有活跃 agent | task 被 claim 后 | task 派发后 | executor 运行中 |
| `failed` | 子 agent 无输出 | N/A（run 用 `failed`） | task 终态 | run 终态 |
| `blocked` | N/A | task 被阻塞 | task 终态 | N/A |
| `ready` | N/A | task 等待 dispatch | N/A | N/A |

### 3.4 Event 模型碎片化

| 能力 | delegate_task | Kanban | Pipeline | Desktop 设计 |
|------|--------------|--------|----------|-------------|
| 流式推理事件 | ✅ thinking | ❌ | ❌ | ✅ reasoning |
| 工具调用事件 | ✅ tool_started/tool_completed | ❌ | ❌ | ✅ tool_call/tool_result |
| 审批事件 | ✅（auto-deny/approve, 非事件） | ❌ | ❌ | ✅ approval_needed |
| diff 事件 | ❌ | ❌ | ❌ | ✅ diff |
| 心跳事件 | ✅ heartbeat loop | ✅ heartbeat events | ❌ | ❌ |
| 生命周期事件 | ✅ spawn/start/complete | ✅ created→...→completed | ✅ lifecycle_event/run_started/run_finished | ✅ created→...→completed |
| 事件持久化 | ❌（仅内存） | ✅ task_events 表 | ✅ ledger.jsonl | 待实现 |
| 事件去重/seq | ❌ | ❌ | ❌ | ✅ Orchestrator 分配 seq |

### 3.5 Result 结构碎片化

| 产物 | delegate_task | Kanban | Pipeline | Desktop 设计 |
|------|--------------|--------|----------|-------------|
| 摘要 | summary (string) | task_runs.summary (string) | outbox.summary (string) | AgentRun.error_summary |
| 变更文件 | files_written (list) | task_runs.metadata.changed_files | outbox.changed_files | ChangedFile[] |
| 工具追踪 | tool_trace (list) | ❌ | ❌ | RunEvent(type=tool_call) |
| token 用量 | tokens.{input,output} | ❌ | ❌ | ❌ |
| API 费用 | _child_cost_usd | ❌ | ❌ | ❌ |
| 错误分类 | error (string) | task_runs.error + outcome | outbox.error_taxonomy | AgentRun.error_summary |
| 证据/验证 | ❌ | ❌ | outbox.evidence + outbox.verification | ❌ |

### 3.6 重大缺失

1. **Gateway session → Task/Run 链路不完整。** Kanban 有 `session_id` 字段但仅用于创建标记；Pipeline 完全不知道 Gateway 会话；delegate_task 完全在内存中。从"用户在飞书群发了一条消息"到"Agent 完成了一项代码修改"的端到端链路在任何单一数据源中都不可见。

2. **子 Agent 树在 Pipeline 和 Kanban 中不可见。** Pipeline 将 `hermes -z` 视为黑盒子；Kanban worker 内置的 delegate_task 调用完全不被 Kanban 追踪。只有实时 TUI 能看到子 agent 树。

3. **Review/Gate 不一致。** Pipeline 有完整的 5 阶段 gate，Kanban 只有基本 review status 和诊断规则引擎，delegate_task 完全没有。

4. **无统一 Event 总线。** 三个系统的 event 互不相通。Desktop 的 `RunOrchestrator` 设计是正确方向，但当前仅有设计文档。

5. **Token 用量和成本无处汇合。** delegate_task 追踪了 cost_usd 但仅在内存中；Kanban 和 Pipeline 完全不追踪 token 消耗。

6. **Changed files 来源不一致。** Pipeline outbox 区分 `changed_files_source`（git_diff vs agent 自述）；delegate_task 通过 file_state registry 追踪但仅用于 stale-path 提醒；Kanban 由 worker 自行在 metadata 中声明。

---

## 4. 统一模型定义

### 4.1 核心模型

```
Project
  └── Task
       ├── TaskSpec              // "做什么"：编译后的意图 + 执行计划 + 输出约定 + 约束
       ├── SessionBinding        // "谁发起的"：Gateway session → task 的链接
       ├── TaskRelation          // "任务之间什么关系"：parent/child/revision/swarm
       └── Run                   // "谁执行、怎么执行、结果如何"
            ├── RunRelation      // "运行之间什么关系"：delegated/review/qa/retry/gate/revision
            ├── DomainEventEnvelope // "发生了什么"：统一事件信封
            ├── Artifact / Evidence  // "产出了什么"：文件、验证数据、diff
            └── ReviewDecision   // "审查结论是什么"：纯记录，不负责控制命令
```

### 4.2 核心实体定义

#### 4.2.1 Project

```text
Project {
  id: string            // 全局唯一，如 "staam"
  name: string          // 人类可读名称
  path: string          // 本地绝对路径（git root）
  git_remote: string?   // 可选 remote URL
}
```

**设计说明：** Kanban Board 和 Pipeline Team 通过 `name` 做 natural join。Board 的 `default_workdir` 映射为 `path`。

#### 4.2.2 Task

```text
Task {
  id: string            // 全局唯一，建议格式 "{project}:task:{short_id}"，如 "staam:task:t6"
  project_id: string    // 外键 → Project
  title: string         // 简短标题
  body: string?         // 详细描述（TaskSpec 可替代或增强）
  status: TaskStatus    // 投影状态，由 Orchestrator 根据最新 Run 归纳
  created_at: timestamp
  updated_at: timestamp
}

TaskStatus = 'draft' | 'queued' | 'running' | 'needs_review' | 'done' | 'failed' | 'blocked' | 'cancelled'
```

**设计说明：**
- `Task.status` 是面向列表/筛选的投影状态，不是 Run 生命周期的唯一事实源。事实源始终是 `Run.status` + `DomainEventEnvelope`。
- 当前 Kanban `tasks` 表、Pipeline Task Card、delegate_task `goal` 三者的 Task 概念在此统一。
- Kanban 的 `tasks.id`（TEXT 如 t6）保持兼容，通过 `project_id` + `id` 提供全局唯一性。

#### 4.2.3 TaskSpec

```text
TaskSpec {
  // 意图编译（来自 compile-task.py 的 compiled_intent）
  interpreted_intent: string   // LLM 解译后的意图
  real_task: string            // 实际要做的事
  task_category: string        // feature | bugfix | refactor | research | ...
  risk_level: string           // R0 | R1 | R2 | R3 | R4

  // 执行计划（来自 managed-agents.yaml 的 routing rules）
  execution_mode: 'single_agent' | 'pipeline' | 'review_only'
  primary_agent: string        // 首选 agent_id
  agents: string[]             // 完整 agent 链

  // 输出约定（来自 outbox v2.8 contract）
  output_schema_version: string
  required_output_fields: string[]

  // 约束（来自 compiled_intent + Pipeline inbox）
  allowed_files: string[]
  must_keep: string[]
  must_change: string[]
  must_avoid: string[]
  success_criteria: string[]
}
```

**设计说明：** TaskSpec 是 Task 的 "输入面"。当前这些信息分散在 Task Card JSON、Kanban task body、routing rules、outbox template 四个地方。统一到 TaskSpec 后，三个执行链复用同一份定义。

#### 4.2.4 SessionBinding

```text
SessionBinding {
  task_id: string         // 外键 → Task
  source: TaskSource      // 来源平台
  session_id: string      // Gateway SessionDB 的 session_id
  platform: string?       // feishu | wechat | discord | telegram | ...
  chat_id: string?        // 平台会话 ID
  user_id: string?        // 平台用户 ID
  bound_at: timestamp
}

TaskSource = 'desktop' | 'cli' | 'feishu' | 'discord' | 'api' | 'scheduler'
```

**设计说明：**
- `SessionBinding` 是 Task 的 "来源面"，记录请求来自哪里。
- 当前 Kanban `tasks.session_id` 已是单向绑定；Gateway `SessionDB` 已有持久化 session；Pipeline 的 `inbox_path` 文件路径隐含了来源但未显式绑定。
- Desktop 状态模型已定义 `TaskSource` 枚举，直接复用。

#### 4.2.5 TaskRelation

```text
TaskRelation {
  id: string
  parent_task_id: string   // 外键 → Task
  child_task_id: string    // 外键 → Task
  relation_type: TaskRelationType
  created_at: timestamp
}

TaskRelationType = 'parent_child' | 'swarm' | 'revision'
```

**关键决策：TaskRelation 与 RunRelation 严格分离。**

TaskRelation 用于关联**独立的 Task 实体**，不用于关联 Run：

| 当前概念 | TaskRelation 映射 |
|----------|------------------|
| Kanban Swarm Worker | `TaskRelation(type=swarm, parent=root, child=worker)` — Worker 是独立 Task |
| Kanban Swarm Verifier | `TaskRelation(type=swarm, parent=root, child=verifier)` — Verifier 是独立 Task |
| Kanban Swarm Synthesizer | `TaskRelation(type=swarm, parent=root, child=synthesizer)` — Synthesizer 是独立 Task |
| Pipeline Revision Task Card | `TaskRelation(type=revision, parent=original, child=revision)` — Revision 是独立 Task |
| Kanban task_links (parent→child) | `TaskRelation(type=parent_child)` — 通用父子依赖 |

**禁止：** 不得将 Kanban Swarm Worker、Verifier、Synthesizer 建模为 ChildRun。它们是拥有自己 Run 历史的独立 Task。

#### 4.2.6 Run

```text
Run {
  // === 核心字段（所有执行链共用）===
  id: string              // 全局唯一 run ID。Phase 1 shadow projection 使用确定性 namespaced ID；未来权威 Orchestrator 创建的新对象 ID 方案另行决定
  task_id: string         // 外键 → Task
  parent_run_id: string?  // 父 Run ID（形成 Run 树），NULL 表示是 task 的首个 run 或顶层 run
  run_seq: number?        // 同一 task 内单调递增。Phase 1 shadow projection 中原数据无可靠 seq 时必须为 null；禁止根据文件顺序猜测。未来权威 Orchestrator 才负责分配非空 run_seq
  run_type: RunType       // 运行类型
  executor_id: string     // 执行器标识：hermes-local | claude-code-cli | codex-cli | ...
  agent_id: string        // 执行此 run 的 managed agent ID（来自 agent-registry）
  status: RunStatus       // 权威状态（是状态机的唯一事实源）
  outcome: string?        // 终态语义分类：completed | blocked | crashed | timed_out | spawn_failed | gave_up | reclaimed | revision_needed | rejected
  summary: string?        // 文本摘要
  error_summary: string?  // 错误简述
  base_path: string       // 执行目录（绝对路径）
  created_at: timestamp
  started_at: timestamp?
  ended_at: timestamp?
}

RunType = 'main' | 'review' | 'qa' | 'gate' | 'retry' | 'revision'
RunStatus = 'created' | 'queued' | 'starting' | 'running' | 'waiting_review' | 'completed' | 'failed' | 'cancelled'
```

**设计说明：**
- 核心 Run 只保留跨执行链通用的字段。私有字段拆分到以下子结构：
- `RunStatus` 合并了 Desktop 设计（created→queued→starting→running→waiting_review→completed/failed/cancelled）和 Kanban（running/running→done/blocked/...）。Kanban 的细化分类通过 `outcome` 字段表达。
- `retry` 不改变旧 Run 的状态——创建新 Run，新 Run 的 `parent_run_id` 指向被重试的 Run，`run_type=retry`。

#### 4.2.7 Run 私有元数据子结构

将执行链专属字段从核心 Run 中剥离，避免字段膨胀：

```text
// 外部系统引用 — 将 Run 桥接到具体 executor 的原生记录
RunExecutionRef {
  run_id: string           // 外键 → Run
  external_run_id: string? // 具体 executor 返回的运行 ID（如 Kanban task_runs.id, Pipeline ledger run_id）
  source_system: string    // 'kanban' | 'pipeline' | 'desktop' | 'delegate_task'
}

// 调度器元数据 — Kanban dispatcher / Pipeline timeout 机制专用
SchedulerMetadata {
  run_id: string
  claim_lock: string?           // CAS 抢占令牌（Kanban）
  claim_expires: number?        // 抢占过期时间戳（Kanban）
  worker_pid: number?           // worker 子进程 PID（Kanban + Pipeline）
  max_runtime_seconds: number?  // 运行时上限（Kanban + Pipeline timeout）
  last_heartbeat_at: number?    // 最后心跳时间戳（Kanban）
}

// 进程级元数据 — 子进程 / CLI 执行器专用
ProcessMetadata {
  run_id: string
  command: string?          // 执行的命令（Pipeline）
  cwd: string?              // 工作目录（Pipeline）
  exit_code: number?        // 进程退出码（Pipeline）
  classification: string?   // ok | timeout | permission_error | auth_error | rate_limited | process_error（Pipeline）
  model: string?            // 实际使用的模型（delegate_task + Desktop）
  profile: string?          // 执行此 run 的 profile（Kanban）
  git_snapshot: string?     // git 快照（Adapter start 时记录）
  worktree_path: string?    // worktree 路径（Desktop v0.4）
}
```

#### 4.2.8 RunRelation

```text
RunRelation {
  id: string
  parent_run_id: string    // 外键 → Run
  child_run_id: string     // 外键 → Run
  relation_type: RunRelationType
  created_at: timestamp
}

RunRelationType = 'delegated' | 'review' | 'qa' | 'gate' | 'retry'
```

**关键决策：delegate_task 子 Agent 是子 Run，不是子 Task。**

| 当前概念 | RunRelation 映射 |
|----------|-----------------|
| delegate_task 子 Agent | `RunRelation(type=delegated, parent=parent_run, child=child_run)` |
| Review run（claim_review_task） | `RunRelation(type=review, parent=main_run, child=review_run)` |
| QA run | `RunRelation(type=qa, parent=main_run, child=qa_run)` |
| Gate 执行 | `RunRelation(type=gate, parent=main_run, child=gate_run)` |
| Retry | `RunRelation(type=retry, parent=failed_run, child=retry_run)` |

**禁止：** 不得将任何 TaskRelation 级别的概念（Swarm Worker、Revision Task Card）建模为 RunRelation。RunRelation 仅用于同一 Task 下的 Run 之间。跨 Task 的关联（如 Revision Task 与其触发 Task）使用 TaskRelation，不使用 RunRelation。Revision dispatch run 属于独立的 Revision Task，其追溯通过 `TaskRelation(type=revision)` 和 `revision_task_id` 完成。

#### 4.2.9 DomainEventEnvelope

```text
DomainEventEnvelope {
  event_id: string          // 全局唯一事件 ID。Phase 1 shadow projection 使用确定性 SHA-256 派生 ID；未来权威 Orchestrator 创建的新对象 ID 方案另行决定
  event_scope: 'task' | 'run'  // 事件作用域
  event_type: string        // 事件类型标识（统一词汇表）
  task_id: string           // 必填：事件归属的 Task
  run_id: string?           // event_scope=run 时必填；event_scope=task 时可为 NULL
  parent_run_id: string?    // 可选：父 Run ID（子 run 事件时使用）
  source: string            // 事件来源系统：'delegate_task' | 'kanban' | 'pipeline' | 'desktop' | 'gateway'
  source_event_id: string?  // 来源系统中的原始事件 ID（用于去重和追溯）
  occurred_at: timestamp    // 事件发生时间
  payload: object           // 按 event_type 各有结构
  schema_version: string    // payload schema 版本
}
```

**设计说明：**
- 本阶段**只定义事件信封结构**，不设计 Event Bus、不定义 pub/sub、不规定持久化后端。
- Task 事件（`event_scope=task`）允许 `run_id=NULL`，如 task 创建、assignee 变更、依赖关系变更等。
- `source` + `source_event_id` 用于跨系统事件去重和端到端链路追溯。
- `parent_run_id` 用于子 Run 事件（delegate_task 子 Agent 事件）与父 Run 的关联。

**Phase 1 事件来源优先级：**
1. `ledger.jsonl` 是生命周期 DomainEventEnvelope 的**首选事实源**（`lifecycle_event` + `run_started` + `run_finished`）。
2. `review/*.json`（gate record）**只投影 ReviewDecision 和 Evidence**，不生成 DomainEventEnvelope。
3. `events.jsonl` 是 ledger 的**兼容镜像/缺失补充**：
   - 若 ledger 已存在语义相同的 `lifecycle_event`，不重复生成事件（按匹配键显式跳过）。
   - 若 ledger 缺失对应事件，才从 events.jsonl 生成 fallback DomainEventEnvelope。
   - 生命周期匹配键：`task_id + event/phase + revision_task_id + run_id + decision + attempt`；缺失字段统一为 null，禁止按时间近似匹配。
4. `events.jsonl` 支持七种事件：`gate_checked`、`revision_created`、`revision_dispatched`、`revision_dispatch_timeout`、`revision_dispatch_skipped`、`revision_policy_blocked`、`revision_limit_reached`。未知事件返回 UnsupportedRecord。

**统一生命周期归一化：**
- `ledger.jsonl` 的 `lifecycle_event` 与 `events.jsonl` 的 fallback **必须使用同一个归一化函数**，产生相同的 `task_id`、`run_id`、`event_scope`、`event_type` 和 `payload` 语义。事实源是否存在不能改变统一事件语义。
- `revision_dispatched` 和 `revision_dispatch_timeout` 有 `revision_task_id` 时，统一归属于 Revision Task；有 `run_id` 时统一为 run scope。
- 其他生命周期事件统一为原 task_id、task scope、`run_id=None`。
- `ledger lifecycle_event` payload 必须保留原始可用字段（`revision_task_id`、`decision`、`attempt`、`run_id`、`policy_action`、`classification`、`exit_code`、`duration_seconds`、`reason`、`max_revisions`），禁止只保留 `phase/status/message`。
- 禁止创建 Run、RunRelation、Task 或 TaskRelation。

**事件 ID 规则：**
- `ledger lifecycle_event` 继续使用原始稳定 `event_id` 生成事件 ID。
- `events.jsonl` 没有原始 `event_id`，event ID 基于 `project_id + source_location`（含行号）确定性生成，避免多次相同语义事件 ID 冲突。缺 `source_location` 返回 MappingError。

#### 4.2.10 Artifact / Evidence

```text
Artifact {
  id: string
  task_id: string            // 必填：归属的 Task。run_id 为空时通过 task_id 归属
  run_id: string?            // 外键 → Run，可为空
  artifact_type: string      // 'outbox' | 'diff_patch' | 'screenshot' | 'report' | 'changed_file' | ...
  path: string?              // 文件系统路径
  mime_type: string?
  size_bytes: number?
  checksum: string?          // SHA-256
  created_at: timestamp?     // 可空：原始数据无可靠时间戳时为 None，禁止伪造
  metadata: object?          // 原始属性透传（如 changed_files_source）
}

Evidence {
  task_id: string            // 必填：归属的 Task。run_id 为空时通过 task_id 归属
  run_id: string?            // 外键 → Run，可为空
  commands_run: string[]     // 执行的验证命令
  test_results: object?      // 测试结果摘要
  verification_output: string?  // 验证输出文本
  coverage_delta: string?    // 覆盖率变化
  risks: string[]            // 已知风险
}
```

**设计说明：**
- `Artifact` 和 `Evidence` 必须包含 `task_id`；`run_id` 可空。`run_id` 为空时仍可通过 `task_id` 归属到正确的 Task。
- `Artifact.metadata` 用于原样保留原始属性（如 outbox 的 `changed_files_source`），不推断或升级。
- `Artifact.created_at` 可空。outbox 没有可靠时间戳时置 None，禁止生成当前时间或空字符串。
- Pipeline `outbox.json` 的投影**只产生 Artifact 和 Evidence**，不产生 DomainEventEnvelope。`outbox_mapped` 是投影器行为而非原始 Pipeline 事实。`error_taxonomy` 是 outbox 字段而非原始事件，不得为每项虚构 DomainEventEnvelope。
- `Evidence` 记录 Run 的验证证据。Pipeline `outbox.evidence` 已有结构化字段，直接映射。Kanban 和 delegate_task 当前缺少此层，Phase 3+ 逐步补充。

#### 4.2.11 ReviewDecision

```text
ReviewDecision {
  id: string
  run_id: string             // 外键 → Run（被审查的 Run）
  reviewer: string           // 审查方：'ambrosini' | 'codex' | 'human' | agent_id
  decision: string           // 审查结论：'approve' | 'needs_revision' | 'reject'
  summary: string            // 审查摘要
  failed_checks: {check_name: detail}[]  // 未通过的检查项及详情
  revision_instructions: string[]       // 返工指引（仅在 needs_revision 时有意义）
  decided_at: timestamp
}
```

**审查结论语义：**

| decision | 含义 |
|----------|------|
| `approve` | 当前 Run 通过审查。**不代表整个 Task 已接受。** Task 的整体接受是 `TaskCommand.accept`。 |
| `needs_revision` | 当前 Run 未通过审查，需要创建新的 Revision Run（同一 Task 下）或 Revision Task（独立 Task）。 |
| `reject` | 当前 Run 被拒绝。Run 进入终态，Task 可能需要人工干预。 |

**关键设计决策：**

1. **ReviewDecision 只记录审查事实，不执行控制命令。** 审查方声明结论；调用方（Orchestrator/用户）根据结论自主决定后续动作（创建 Revision Run、accept Task 等）。

2. **一个 Run 可以有多次审查。** 同一个 Run 可以被 codex 审查、再被 ambrosini 审查、最后被人类审查——每次审查产生一条独立的 ReviewDecision 行。不强制 0..1。

3. **Pipeline gate decision 映射。** Pipeline 当前的 `approved`/`revision_needed`/`rejected` 是现有事实，统一投影分别映射为 `approve`/`needs_revision`/`reject`。Pipeline 实际行为不变，仅定义投影语义。

4. **映射关系：**

| 当前概念 | ReviewDecision 映射 |
|----------|-------------------|
| Pipeline gate record（`run-task-gate.py` 输出） | `approved`→`approve`, `revision_needed`→`needs_revision`, `rejected`→`reject` |
| Kanban review status + `claim_review_task` 的 review run | review run 的 outcome/summary + 可选的显式 ReviewDecision |
| delegate_task 父 agent 对子 agent 结果的判断 | 当前仅在内存中；Phase 3+ 持久化为 ReviewDecision |

#### 4.2.12 RunCommand 与 TaskCommand

控制命令是调用方基于 ReviewDecision 和 Run 状态**主动发出的指令**，不属于 ReviewDecision 的属性。

**RunCommand（作用于单个 Run）：**

| 命令 | 语义 | 前置条件 |
|------|------|----------|
| `continue` | 恢复当前等待审批的非终态 Run（`waiting_review` → `running`），不创建新 Run | Run 必须处于 `waiting_review` |
| `stop` | 停止当前活跃 Run，Run 进入 `cancelled` 终态 | Run 必须处于非终态（`created`/`queued`/`starting`/`running`/`waiting_review`） |
| `retry` | 因失败或中断创建新的 Retry Run（`run_type=retry`），通过 `RunRelation(type=retry)` 关联旧 Run | 旧 Run 必须处于终态（`failed`/`cancelled`/`completed`） |

**TaskCommand（作用于整个 Task）：**

| 命令 | 语义 | 前置条件 |
|------|------|----------|
| `accept` | 用户接受整个 Task 的最终结果，Task 进入 `done` | Task 必须处于 `needs_review` 或 `running` |
| `cancel` | 取消整个 Task，Task 进入 `cancelled` | Task 必须处于非终态 |

**关键设计决策：**

1. **`continue` 恢复现有 Run，不创建新 Run。** 用于审批通过后继续执行当前 Run。这不是 ReviewDecision 的属性——审查方说 `approve`，调用方决定 `continue`。

2. **Retry 与 Revision 严格区分：**

| 维度 | Retry | Revision |
|------|-------|----------|
| 触发场景 | Run 失败、超时、中断后的**重新执行** | Run 完成但**审查未通过**后的返工 |
| 创建方式 | `RunCommand.retry` → 创建新 Run（`run_type=retry`） | 基于 `ReviewDecision.needs_revision` → 创建新 Run（`run_type=revision`）或新 Task（`TaskRelation(type=revision)`） |
| 关联方式 | `RunRelation(type=retry)` | `RunRelation(type=revision)` 或 `TaskRelation(type=revision)` |
| 旧 Run | 保持终态不变 | 保持终态不变 |
| 新 Run 的 task_id | 同一个 Task | 同一个 Task（Run-level revision）或独立 Task（Task-level revision） |

3. **终态 Run 不可恢复运行或改变历史状态。** `completed`/`failed`/`cancelled` 是终态。`retry` 和 `revision` 都创建新 Run，不修改旧 Run。

4. **Pipeline 的 revision task 是独立 Task。** 通过 `TaskRelation(type=revision)` 关联原 Task。它的 dispatch 是该 Revision Task 下的新 Run。不修改原 Task 和原 Run。

---

### 4.3 现有概念映射表

| 现有概念 | 统一模型映射 | 说明 |
|----------|-------------|------|
| **Kanban Board** | `Project` | Board slug → Project.name；Board default_workdir → Project.path |
| **Pipeline Team** | `Project` | `~/.claude/teams/<name>/` → Project(name, path) |
| **Kanban Task** (`tasks` 行) | `Task` | `tasks.id` 保持 TEXT 格式兼容，通过 `project_id` 全局唯一 |
| **Pipeline Task Card** (inbox JSON) | `Task` + `TaskSpec` | Card 的 `compiled_intent` + `execution_plan` + `output_contract` → TaskSpec；Card 本身是 Task 的 specification 载体 |
| **Pipeline Revision Task Card** | 独立 `Task` + `TaskRelation(type=revision)` | Revision 是独立 Task，通过 TaskRelation 关联原 Task |
| **Kanban Swarm Root** | `Task` | Root card 是普通 Task，status=done |
| **Kanban Swarm Worker** | 独立 `Task` + `TaskRelation(type=swarm)` | Worker 是独立 Task，不是 ChildRun。通过 TaskRelation 关联 Root |
| **Kanban Swarm Verifier** | 独立 `Task` + `TaskRelation(type=swarm)` | 同上 |
| **Kanban Swarm Synthesizer** | 独立 `Task` + `TaskRelation(type=swarm)` | 同上 |
| **Kanban task_runs 行** | `Run` + `SchedulerMetadata` | `id`→Run.id, `claim_lock/worker_pid/...` → SchedulerMetadata |
| **Pipeline dispatch run** (ledger.jsonl) | `Run` + `ProcessMetadata` + `SchedulerMetadata` | `run_*` ID→Run.id, `command/exit_code/...` → ProcessMetadata |
| **Pipeline revision dispatch run** | `Run`（属于独立 Revision Task）+ `ProcessMetadata` | Revision Task 有自己的 Run；与原始 Task 的关联通过 `TaskRelation(type=revision)`，当前原始数据无 `parent_run_id` 故 Phase 1 不生成 RunRelation |
| **delegate_task 子 Agent** | 子 `Run` + `RunRelation(type=delegated)` | 子 Agent 是子 Run，挂在同一个 Task 下，通过 `parent_run_id` 和 RunRelation 关联父 Run |
| **delegate_task 嵌套子 Agent** (orchestrator 的 child) | 孙 `Run` + `RunRelation(type=delegated)` | 多级嵌套：每层都是一个 Run，通过 `parent_run_id` 形成树 |
| **Gateway Session** | `SessionBinding` | `SessionDB.session_id` → SessionBinding.session_id；`source='feishu'` 等 |
| **Pipeline outbox.json** | `Artifact`(type=outbox) + `Evidence` | outbox 文件→Artifact；outbox.evidence→Evidence |
| **Pipeline gate record** (review JSON) | `ReviewDecision` | gate record 的 decision + failed_checks + revision_instructions → ReviewDecision |
| **Kanban review (claim_review_task)** | `Run`(type=review) + 可选 `ReviewDecision` | review run 的结果可记录为 ReviewDecision |
| **Kanban task_links** | `TaskRelation` | `parent_id → child_id` 映射为 `TaskRelation(type=parent_child)` |
| **Kanban task_events** | `DomainEventEnvelope`(source=kanban, event_scope=task\|run) | kind/payload/created_at → event_type/payload/occurred_at |
| **Pipeline ledger.jsonl events** | `DomainEventEnvelope`(source=pipeline, event_scope=run) | lifecycle_event/run_started/run_finished → event_type |
| **delegate_task DelegateEvent** | `DomainEventEnvelope`(source=delegate_task, event_scope=run) | DelegateEvent 枚举值 → 归一化 event_type |
| **Desktop RunEvent 设计** | `DomainEventEnvelope`(source=desktop, event_scope=run) | 10 种 RunEventType → 归一化 event_type |

---

### 4.4 关键架构决策摘要

1. **TaskRelation ≠ RunRelation。** Swarm Worker 是子 Task；delegate_task 子 Agent 是子 Run。两者不可互换。

2. **核心 Run 保持最小化。** 调度器字段（claim_lock, worker_pid）、进程字段（command, exit_code）、执行器字段（external_run_id）全部外移到子结构。新增执行链只需新增子结构，不修改核心 Run schema。

3. **ReviewDecision 只记录审查事实，不编码控制流。** 控制命令（continue/stop/retry/accept/cancel）由 RunCommand 和 TaskCommand 独立定义。审查方声明 `approve`/`needs_revision`/`reject`；调用方决定后续动作。Retry 和 Revision 都创建新 Run，不修改旧 Run；Revision 还可创建独立 Task。

4. **DomainEventEnvelope 是事件信封，不是事件类型枚举。** 本阶段只定义信封结构；`event_type` 的统一词汇表由 Phase 1 Event Schema 统一阶段产出。

5. **一个 Run 支持多次审查。** 每次审查产生一条独立的 ReviewDecision 行，不强制 0..1。

6. **Pipeline Revision Task Card 是独立 Task。** Revision 拥有自己完整的 Task → Run → ReviewDecision 生命周期，通过 `TaskRelation(type=revision)` 关联原 Task。Revision dispatch 的 sub-run 属于该 Revision Task 自身，当前原始数据无 `parent_run_id`，因此 Phase 1 不生成 RunRelation。追溯通过 `TaskRelation(type=revision)` 和 `revision_task_id` 完成。未来原始数据明确提供父 Run ID 时，才允许生成 RunRelation。

---



---

## 5. 推荐的渐进接入路线

### 5.1 Phase 0.1：修订并冻结合同

- 持续完善本文档，直至所有事实错误修正、模型决策定稿。
- 不修改任何运行时代码、配置、数据库。
- 本阶段以文档被接受并冻结为结束条件。

---

### 5.2 Phase 1A 冻结决策

以下决策在进入 Phase 1A 实现前已冻结，Phase 1A 不得自行选择其他方案。

#### 5.2.1 确定性 ID 规则

Shadow projection 必须使用确定性 ID，**禁止生成随机 ULID/UUID**。

| ID 类型 | 格式 | 说明 |
|---------|------|------|
| `task_id` | `pipeline:{project_id}:task:{source_task_id}` | `project_id` 来自 Pipeline team 目录名；`source_task_id` 为 Task Card 的 `task_card_id` 或 `task_id` |
| `run_id` | `pipeline:{project_id}:run:{source_run_id}` | `source_run_id` 来自 `ledger.jsonl` 的 `run_id` 字段 |
| `event_id` | `SHA-256(source + project_id + source_record_identity)[:32]` | 对 `"pipeline:{project_id}:{source_file}:{source_record_offset}"` 做 SHA-256，取前 32 位十六进制字符 |

**确定性保证：** 相同原始数据重复投影，必须产生完全相同的 ID。删除投影后重建，所有 ID 不变。

#### 5.2.2 Revision Task 的 ID 与关联

- Revision Task 拥有**独立 `task_id`**：`pipeline:{project_id}:task:{revision_task_card_id}`。
- `root_task_id` 始终指向最初的根 Task（`pipeline:{project_id}:task:{root_task_card_id}`），与 revision 深度无关。
- 使用 `TaskRelation(type=revision)` 关联**直接触发它的前一个 Task**（可能是根 Task 或前一个 Revision Task）。
- 这样同时保留完整 revision 链（沿 TaskRelation 遍历）和根任务归属（通过 `root_task_id`）。

#### 5.2.3 禁止虚构 Run

当前 Pipeline 未持久化独立 Review/Gate run_id（verify-task.py、review-task.py、gate-policy.py 均作为子进程运行，不出现在 `ledger.jsonl` 的 `run_started`/`run_finished` 记录中）。

- 只有原始记录明确包含 `run_id` 时才能投影为 `Run`。
- Review/Gate 的执行结果只能投影为 `DomainEventEnvelope`、`ReviewDecision` 和 `Evidence`。
- **禁止为缺失的运行生成假 Run。**

#### 5.2.4 Shadow Projection 输出位置

```
~/.hermes/projections/task-card-pipeline/{project_id}/events.jsonl
```

规则：
- 每个 Project 一个 JSONL 文件，按 `occurred_at` 追加写入。
- 全量重建时先写临时文件（`events.jsonl.tmp.{pid}`），完成后原子 `os.replace()` 替换。
- 投影目录可安全删除（`rm -rf ~/.hermes/projections/`），不影响原 Pipeline。
- 原始 Pipeline 文件（inbox/outbox/review/ledger）仍是**唯一事实源**。

#### 5.2.5 纯映射函数规则

Phase 1A 实现的每个映射函数必须满足：

1. 只接收已经解析的原始记录（dict/list/string），返回统一投影对象（`@dataclass` 或 typed dict）。
2. **不读取文件、不写文件、不访问网络、不修改环境变量。** 文件 I/O 由调用方负责。
3. 不调用 Pipeline、Kanban、Gateway 或 Desktop 的任何模块。
4. 无法可靠映射时返回明确的 `UnsupportedRecord` 或 `MappingError` 结果。**禁止猜测、禁止静默丢弃、禁止填充假数据。**
5. 每个投影对象必须保存溯源字段：
   - `source`：`'pipeline'`
   - `source_event_id`：原始事件在原文件中的标识
   - `source_location`：`"{file_path}:{line_number}"` 或 `"{file_path}:{key}"`

---

### 5.3 Phase 1B：仅为 Task Card Pipeline 实现 Shadow Projection

**范围：** 仅 Pipeline（Task Card Pipeline），不含 Kanban、delegate_task、Gateway、Desktop。

**输入（原始数据源）：**
- Task Card（`~/.claude/teams/<project>/inbox/*.json`）
- outbox（`~/.claude/teams/<project>/outbox/*.json`）
- gate record（`~/.claude/teams/<project>/review/*.json`）
- events.jsonl（`~/.claude/teams/<project>/events.jsonl`）
- ledger.jsonl（`~/.claude/teams/<project>/runs/ledger.jsonl`）

**已审计但永久排除的派生 read model：**
- tasks/index.jsonl（`~/.claude/teams/<project>/tasks/index.jsonl`）：不得读取或映射，其缺失、损坏或内容变化不得影响投影输出。

**产出（投影输出）：**
- 从以上权威原始数据生成 §4 定义的 `Task`、`TaskSpec`、`TaskRelation`、`Run`、`RunRelation`、`DomainEventEnvelope`、`Artifact`、`Evidence`、`ReviewDecision` 的统一投影。

**硬性约束：**

| 约束 | 说明 |
|------|------|
| 原 Pipeline 完全不变 | 状态、事件格式、文件路径、执行行为 —— 一行代码不改 |
| Shadow projection 是只读派生数据 | 不得写入原始 Pipeline 文件、原 ledger、原 events.jsonl |
| 投影失败不能影响原 Pipeline | 投影进程崩溃/报错 = 原 Pipeline 继续正常工作 |
| 可删除、可重建 | 删除全部投影输出后，从原始 Pipeline 数据可完整重建 |
| 不修改 Kanban、delegate_task、Gateway、Desktop | 这些系统在 Phase 1 中完全不接触 |
| 不修改现有 Pipeline 状态和事件格式 | 包括 verify-task.py 的 TASK_STATUSES、events.jsonl 的 event kind、ledger.jsonl 的 event 类型 |
| 不迁移历史数据 | 不修改已有 inbox/outbox/review/ledger 文件的内容 |
| 不替换原 ledger | 原 `ledger.jsonl` 仍然是权威事实源 |
| 不创建统一 Event Bus | Phase 1 不引入 pub/sub、消息队列、或流式事件分发 |
| 不实现统一 Orchestrator | Desktop 的 `RunOrchestrator` 设计文档不变，Phase 1 不实现 |
| 不要求迁移 Kanban `task_events.kind` | Kanban 的 kind 自由文本在 Phase 1 中完全不接触 |

**Phase 1 的 source of truth：** 仍是 Pipeline 原有文件和 ledger.jsonl。Shadow projection 不是新的权威事实源。

---

### 5.4 Phase 1C：端到端验收

使用一个真实 Pipeline 任务验证完整生命周期可以通过投影还原。

**验收命令：**

```bash
python scripts/task-run-projection-acceptance.py \
  --project staam \
  --team-dir ~/.claude/teams/staam \
  --root-task-id staam_t6 \
  --require-complete-lifecycle
```

验收器只读取 Pipeline 原始文件，并在临时目录执行两次完整构建。它不会读取或覆盖正式投影，
也不会修改原 Pipeline 文件。两次输出必须逐字节一致；真实数据缺少 revision 生命周期时，
必须明确报告覆盖缺口，不得误报为完整生命周期通过。

**验收场景：**

```
原始 Task Card (task_card_id: "staam_t6")
  │  → 统一 task_id: "pipeline:staam:task:staam_t6"
  │  → root_task_id: "pipeline:staam:task:staam_t6"
  │
  ├─ [1] Main Dispatch Run
  │      run_id: pipeline:staam:run:{source_run_id}
  │      agent: claude
  │      → 写入 outbox.json
  │
  ├─ [2] Gate Review
  │      verify-task.py → review-task.py → gate-policy.py → run-task-gate.py
  │      → 写入 gate record (review/*.json)
  │      → 投影为 ReviewDecision + DomainEventEnvelope(gate_checked)
  │      → 不生成 Run（当前无持久化 review run_id）
  │
  ├─ [3] decision = revision_needed
  │      → 创建独立 Revision Task Card (task_card_id: "staam_t6_rev1")
  │      → 统一 task_id: "pipeline:staam:task:staam_t6_rev1"
  │      → root_task_id: "pipeline:staam:task:staam_t6"（始终指向根）
  │      → TaskRelation(type=revision,
  │           parent="pipeline:staam:task:staam_t6",
  │           child="pipeline:staam:task:staam_t6_rev1")
  │
  ├─ [4] Revision Task Dispatch Run
  │      run_id: pipeline:staam:run:{revision_source_run_id}
  │      agent: claude
  │      → 写入 revision outbox.json
  │      → 自动 revision dispatch 可同时记录外层 revision_dispatch Run 和内层 dispatch Run；
  │        两者都必须来自 ledger 中的真实 run_id，并归属于独立 Revision Task
  │      → 不生成 RunRelation（当前无 parent_run_id）
  │
  └─ [5] Gate approved
         → 写入 gate record
         → 投影为 ReviewDecision(approve) + DomainEventEnvelope(gate_checked)
         → Task 状态：needs_review（等待用户 TaskCommand.accept）
         → gate approved ≠ Task accepted
```

**验收要求：**

| 要求 | 说明 |
|------|------|
| 全生命周期保留稳定 `root_task_id` | 从原始 Task Card 到 Gate approved，所有投影记录使用同一个 `root_task_id`（`pipeline:staam:task:staam_t6`） |
| Revision Task 使用独立 `task_id` | `pipeline:staam:task:staam_t6_rev1` 是独立 Task，不是用原 task_id 覆盖 |
| Revision Task 关联根 Task | 通过 `TaskRelation(type=revision)` 关联 `pipeline:staam:task:staam_t6` |
| 每次 dispatch 使用独立 `run_id` | Main dispatch 和 Revision dispatch 使用互不重叠的真实 ledger `run_id`；自动 revision dispatch 可包含外层 `revision_dispatch` Run 和内层 `dispatch` Run |
| 不生成 RunRelation(revision_dispatch) | Revision dispatch run 属于独立 Revision Task；当前原始数据无 `parent_run_id`，Phase 1 不生成 RunRelation |
| 不虚构 Review/Gate Run | [2] 和 [5] 的 Gate 执行不投影为 Run，仅投影为 ReviewDecision + DomainEventEnvelope |
| Gate approved ≠ Task accepted | `ReviewDecision(approve)` 表示当前 Run 通过审查；Task 的最终接受需要 `TaskCommand.accept`。Phase 1 生命周期终点为"Gate approved，等待用户接受"，不投影为 accepted |
| 每个投影事件可追溯到原始记录 | ledger 事件使用 `source` + `source_event_id`；无原始 event ID 的 `events.jsonl` fallback 使用含行号的 `source_location` |
| 不读取 Kanban、Gateway、delegate_task、Desktop 数据 | 验收的全量输入仅来自 Pipeline 文件系统 |
| 删除投影后可以完整重建 | 删除投影输出目录 → 重新运行投影 → 逐条对比 → 完全一致 |

---

### 5.5 Phase 2：接入 delegate_task

- 为 delegate_task 的内存执行记录生成统一投影。
- 子 Agent 树通过 `RunRelation(type=delegated)` 投影。
- 不改变 delegate_task 的内存执行模型，投影为只读附加层。

### 5.6 Phase 3：接入 Kanban

- 从 Kanban `tasks`、`task_runs`、`task_events`、`task_links` 生成统一投影。
- `task_events.kind` 自由文本通过映射表归一化，不修改原数据。
- Kanban Swarm 拓扑通过 `TaskRelation(type=swarm)` 投影。
- Kanban `claim_review_task` 的 review run 通过 `RunRelation(type=review)` 投影。

### 5.7 Phase 4：统一控制接口与 Review/Gate

- 在投影层之上实现统一控制接口（创建 Task、启动 Run、提交 ReviewDecision）。
- Pipeline gate 决策和 Kanban review 结果统一写入 `ReviewDecision` 投影。
- `retry` 实现为创建新 Run（`run_type=retry`）而非修改旧 Run。

### 5.8 Phase 5：Desktop 消费统一投影

- Desktop 通过统一投影读取所有执行链的状态。
- `RunOrchestrator` 实现（按现有设计文档 `docs/architecture/run-orchestrator.md`）。
- UI 始终是只读消费者，所有状态写入经过控制接口。

---

## 6. 关键设计约束

### 6.1 不可破坏的现有行为

1. **Kanban CAS 抢占机制。** claim_lock + CAS UPDATE 是 Kanban 调度的核心，任何统一模型必须保留 SQLite WAL 级别的原子抢占。
2. **delegate_task 的隔离性。** 子 agent 不继承父 agent 历史、工具集受限、审批策略独立——这些隔离约束是安全边界。
3. **Pipeline 的重试循环。** revision_needed → 重新 dispatch → re-verify 的循环必须保持。
4. **Gateway 会话缓存的语义。** `_agent_cache` 的 LRU + TTL 驱逐策略与 prompt caching 的成本优化直接相关。

### 6.2 不可重复的现有缺陷

1. **不要创建第 4 套 Task ID / Run ID / Status 体系。** 统一模型的意义是减少碎片，而非增加。
2. **不要绕过已有持久化层。** Kanban 的 SQLite 和 Pipeline 的 ledger.jsonl 各有其存在原因（Kanban 需要 SQL 查询/事务；Pipeline 需要 JSONL 追加的可读性和容错性）。统一 Event 层应写入二者都能消费的格式。
3. **不要假设全局同步时钟。** 三个执行链运行在不同进程/机器上，event 的 `seq` 只能通过单点（Orchestrator）分配。

### 6.3 采纳的 Desktop 设计先例

Desktop 状态模型文档（`docs/architecture/hermes-desktop-state-model.md`）已经做出了几个关键设计决策，本统一模型直接采纳：

1. **Run 是状态事实源。** TaskThread.status 是投影，Run.status 是权威。
2. **retry 创建新 Run，不改旧 Run。** 所有终态不可逆。
3. **一个 Run 可以有多条 ReviewDecision。** 不是每个 Run 都需要审查；需要审查的 Run 可以被多方多次审查。不得强制为 0..1。
4. **UI 是只读消费者。** 所有状态写入经过 Orchestrator。
5. **ChangedFile 有 absolute_path。** UI 不需要根据 executor 类型拼路径。

---

## 7. 审计检查清单

- [x] delegate_task.py — 子 agent 生命周期、事件、结果结构已审计
- [x] kanban_db.py — tasks/task_runs/task_events/task_comments/task_links 表结构已审计
- [x] kanban.py — CLI 命令面和 status 流转已审计
- [x] kanban_swarm.py — Swarm 拓扑和父子关系已审计
- [x] compile-task.py — Task Card 组装和 compiled_intent schema 已审计
- [x] dispatch-task.py — 派发流程和 outbox contract 已审计
- [x] verify-task.py — 结构验证规则和 TASK_STATUSES 定义已审计
- [x] review-task.py — 语义验证维度和 Decision 定义已审计
- [x] run-task-gate.py — Gate 总闸协调逻辑（含 run_gate、apply_gate_policy、build_revision_inbox）已审计
- [x] gate-policy.py — 两层策略引擎（taxonomy-driven policy_for_v2_8_1 + legacy policy_for）已审计
- [x] run-ledger.py — JSONL 账本结构和 event 类型已审计
- [x] gateway/run.py — Agent 缓存池、SessionKey 模型、_kanban_notifier_watcher 通知机制已审计
- [x] managed-agents.yaml — Agent 配置、路由规则、风险管理字段已审计
- [x] agent-registry.json — JSON 快照和 subagent_profile 结构已审计
- [x] hermes-desktop-state-model.md — Desktop 状态模型设计已审计
- [x] run-orchestrator.md — Orchestrator 状态机设计已审计
- [x] agent-adapter-layer.md — Adapter 接口和事件归一化设计已审计
- [x] ADR-codex-like-desktop-workbench — 控制平面优先架构决策已审计

---

## 附录 A：完整状态词汇对照表

| 概念 | delegate_task | Kanban (task) | Kanban (run) | Pipeline (task) | Pipeline (run) | Desktop 设计 |
|------|--------------|---------------|--------------|-----------------|----------------|-------------|
| 创建 | spawn_requested | created (event) | (INSERT) | created | lifecycle_event(compiled) | created |
| 排队 | — | — | — | — | — | queued |
| 就绪 | — | ready | — | — | — | — |
| 启动 | subagent.start | running | running | dispatched | run_started | starting→running |
| 推理中 | thinking | — | — | — | — | reasoning |
| 工具调用 | tool.started/completed | — | — | — | — | tool_call/tool_result |
| 待审查 | — | review | — | waiting_for_verification | — | waiting_review |
| 需人工 | — | — | — | needs_human_review | — | approval_needed |
| 完成 | completed | done | done (outcome: completed) | completed | run_finished (exit 0) | completed |
| 失败 | failed/error | — | failed/crashed/timed_out | failed | run_finished (exit ≠0) | failed |
| 阻塞 | — | blocked | blocked | blocked | — | — |
| 超时 | timeout | — | timed_out | — | run_finished (timeout) | — |
| 中断 | interrupted | — | released (outcome: reclaimed) | discarded | — | cancelled |
| 放弃 | — | — | released (outcome: gave_up) | discarded | — | — |
| 归档 | — | archived | — | — | — | — |

## 附录 B：文件路径约定

| 路径 | 用途 | 当前状态 |
|------|------|----------|
| `~/.hermes/kanban.db` | default board 的 Kanban DB | ✅ 生产使用 |
| `~/.hermes/kanban/boards/<slug>/kanban.db` | 多 board DB | ✅ 生产使用 |
| `~/.hermes/kanban/workspaces/` | Kanban worktree 工作空间 | ✅ 生产使用 |
| `~/.hermes/kanban/logs/` | Kanban worker 日志 | ✅ 生产使用 |
| `~/.hermes/kanban/current` | 当前活跃 board 指针 | ✅ 生产使用 |
| `~/.claude/teams/<project>/inbox/` | Pipeline task card 入队 | ✅ 生产使用 |
| `~/.claude/teams/<project>/outbox/` | Pipeline agent 输出 | ✅ 生产使用 |
| `~/.claude/teams/<project>/review/` | Pipeline gate 审查记录 | ✅ 生产使用 |
| `~/.claude/teams/<project>/runs/ledger.jsonl` | Pipeline 运行账本 | ✅ 生产使用 |
| `~/.hermes/state.db` | Gateway SessionDB | ✅ 生产使用 |
| `~/.hermes/logs/` | 系统日志 + delegate_timeout 诊断 | ✅ 生产使用 |
| `~/.hermes/runs/` | 建议：统一 Run 事件日志 | ❌ 待创建 |
