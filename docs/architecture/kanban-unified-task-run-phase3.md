# Kanban — Phase 3A 审计与统一消费设计

> 状态：**Phase 3A — 审计与设计（修订版，本阶段不实现代码）**
> 日期：2026-06-10
> 基于：Phase 2 commits `37064118c` + `80d5b9db2`

---

## 1. 审计总结

### 1.1 源码

| 文件 | 行数 | 角色 |
|------|------|------|
| `hermes_cli/kanban_db.py` | 7648 | SQLite schema、CRUD、状态机、task_events、通知订阅、stale audit |
| `hermes_cli/kanban.py` | 2830 | CLI、dispatcher、worker、reap loop |
| `hermes_cli/kanban_swarm.py` | 279 | Swarm 编排 |

### 1.2 SQLite 数据模型

**tasks 表（kanban_db.py:974）：**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | TEXT PK | 用户定义 ID（如 "t6"、"wire-fix"） |
| `title` | TEXT NOT NULL | 任务标题 |
| `status` | TEXT NOT NULL | 9 个有效值（见 §1.3） |
| `assignee` | TEXT | 负责的 profile |
| `workspace_kind` | TEXT | scratch / worktree / dir |
| `workspace_path` | TEXT | 工作空间绝对路径 |
| `current_run_id` | INTEGER | 当前活跃 run → task_runs.id（可空） |
| `session_id` | TEXT | 来源 Gateway session UUID（可空） |
| `consecutive_failures` | INTEGER DEFAULT 0 | 断路器计数器 |
| `workflow_template_id` / `current_step_key` | TEXT | v2 工作流（v1 未使用） |
| `skills` / `model_override` / `goal_mode` | TEXT / TEXT / INTEGER | 调度器配置 |

**task_runs 表（kanban_db.py:1073）：**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | INTEGER PK AUTOINCREMENT | 自增 run ID |
| `task_id` | TEXT NOT NULL | FK → tasks.id |
| `status` | TEXT NOT NULL | 7 个有效值：running / done / blocked / crashed / timed_out / failed / released |
| `outcome` | TEXT | 7 个值：completed / blocked / crashed / timed_out / spawn_failed / gave_up / reclaimed（null=running） |
| `summary` | TEXT | handoff 摘要 |
| `metadata` | TEXT (JSON) | 结构化事实 |
| `error` | TEXT | 错误信息 |

**task_events 表（kanban_db.py:1057）：**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | INTEGER PK AUTOINCREMENT | 自增事件 ID，跨重启稳定 |
| `task_id` | TEXT NOT NULL | FK → tasks.id |
| `run_id` | INTEGER | FK → task_runs.id（可空） |
| `kind` | TEXT NOT NULL | 事件种类（见 §1.4 完整列表） |
| `payload` | TEXT (JSON) | 事件负载 |
| `created_at` | INTEGER NOT NULL | Unix 时间戳 |

**task_links 表（kanban_db.py:1043）：** `(parent_id, child_id)` PRIMARY KEY。

**task_comments 表（kanban_db.py:1049）：** `(id, task_id, author, body, created_at)`。

**task_attachments 表（kanban_db.py:1101）：** `(id, task_id, filename, stored_path, ...)`。Phase 3 不映射 attachments。

**kanban_notify_subs 表（kanban_db.py:1116）：** Gateway notifier 订阅。Phase 3 不读取。

### 1.3 Task 状态（VALID_STATUSES，kanban_db.py:100）

```
triage → todo → scheduled → ready → running → done
                         ↓          ↓
                       (跳过)    blocked → ready → running
                                     ↓
                                   review → done
                            running → archived（取消）

9 个有效值：triage, todo, scheduled, ready, running, blocked, review, done, archived
```

`VALID_INITIAL_STATUSES = {"running", "blocked"}`（允许的初始状态，kanban_db.py:101）。

### 1.4 完整 event kind 列表

从 `_append_event()` 调用和 `_audit_stale_runs()` / `_end_run()` 派生的全部 event kind（kanban_db.py:2700 + 各调用点）：

| # | kind | 来源 | 说明 |
|---|------|------|------|
| 1 | `created` | L4467 | 任务创建 |
| 2 | `assigned` | L2405, L6129 | 分配 assignee |
| 3 | `claimed` | L3078, L3152 | 抢占任务 |
| 4 | `claim_rejected` | L3008 | 抢占被拒（父任务未完成） |
| 5 | `claim_extended` | L3268 | 心跳续约 |
| 6 | `spawned` | L5761 | worker 进程已启动 |
| 7 | `scheduled` | L4738 | 手动调度 |
| 8 | `promoted` | L2963 | 依赖满足自动 promotion |
| 9 | `promoted_manual` | L4163 | 手动 promotion |
| 10 | `completed` | L3706 | 任务完成 |
| 11 | `completion_blocked_hallucination` | L3613 | LLM 幻觉引用不存在的卡片 |
| 12 | `suspected_hallucinated_references` | L3724 | 引用不存在的文件 |
| 13 | `blocked` | L4098 | 任务阻塞 |
| 14 | `unblocked` | L4222 | 取消阻塞 |
| 15 | `gave_up` | L5685 | 断路器触发放弃 |
| 16 | `reclaimed` | L3321, L3386 | 回收过期 claim |
| 17 | `timed_out` | L5217 | 超时 |
| 18 | `crashed` | L5481 | worker 崩溃 |
| 19 | `stale` | L5346 | 无心跳过时 |
| 20 | `respawn_guarded` | L6201 | 断路器阻止 respawn |
| 21 | `archived` | L4561 | 归档 |
| 22 | `linked` | L2437, L4483 | 建立 task_link |
| 23 | `unlinked` | L2473 | 删除 task_link |
| 24 | `decomposed` | L4525 | 分解任务 |
| 25 | `edited` | L4032 | 编辑任务字段 |
| 26 | `specified` | L4305 | 设置 workspace/branch |
| 27 | `commented` | L2540 | 添加评论 |
| 28 | `attachment_removed` | L2664 | 删除附件 |
| 29 | `heartbeat` | L5117 | worker 心跳 |
| 30 | `tip_scratch_workspace` | L3969 | scratch workspace 提示 |
| 31 | `protocol_violation` | L5447 | worker 协议违规 |
| 32 | `rate_limited` | L5467 | worker 被限速 |
| — | `reprioritized` | L1798 (migration) | 旧名 `priority` 的迁移重命名 |

**关键发现：** `running` 不是 event kind（是 task status）。`crashed` 是 event kind（由 crash audit 发出，不是 `_end_run` 的 outcome）。

### 1.5 Run outcome 值

从 `_end_run()` 参数和 SQL UPDATE 中提取（kanban_db.py:2728-2737）：

```
completed | blocked | crashed | timed_out | spawn_failed | gave_up | reclaimed
```

共 7 个值。`null` = 仍在运行。

### 1.6 持久化

- SQLite WAL 模式，路径：`~/.hermes/kanban/boards/{slug}/kanban.db` 或 `~/.hermes/kanban.db`（default）
- `tasks` 通过 `session_id` 弱关联 Gateway session
- `task_events` 被 Gateway notifier watcher 轮询推送到飞书/微信

---

## 2. 统一映射设计

### 2.1 确定性 ID

```
board = board slug（如 "default"、"atm10-server"）
        board slug 来自 kanban.db 所在目录名或 "default"

task_id     = "kanban:{board}:task:{tasks.id}"
run_id      = "kanban:{board}:run:{task_runs.id}"
event_id    = SHA-256("kanban:{board}:event:{task_events.id}")[:32]
relation_id = "tr_{child_task_id}_{relation_type}"
```

**稳定性：** `tasks.id` 是 TEXT PK，`task_runs.id` 是 INTEGER AUTOINCREMENT，`task_events.id` 是 INTEGER AUTOINCREMENT。跨重启、跨数据库副本均稳定。board slug 来自目录名，稳定不变。

**碰撞保护：** `kanban:` 命名空间与 `pipeline:` / `delegate:` 隔离。`{board}` 段隔离不同 board。禁止使用时间戳、文件顺序或 PID。

### 2.2 状态映射

| Kanban Task status | 统一 TaskStatus |
|-------------------|----------------|
| `triage` | `draft` |
| `todo` | `draft` |
| `scheduled` | `queued` |
| `ready` | `queued` |
| `running` | `running` |
| `blocked` | `blocked` |
| `review` | `needs_review` |
| `done` | `done` |
| `archived` | `cancelled` |

| Kanban Run outcome | 统一 RunStatus | 统一 outcome |
|-------------------|---------------|-------------|
| (null — running) | `running` | `null` |
| `completed` | `completed` | `completed` |
| `blocked` | `failed` | `blocked` |
| `crashed` | `failed` | `crashed` |
| `timed_out` | `failed` | `timeout` |
| `spawn_failed` | `failed` | `error` |
| `gave_up` | `failed` | `gave_up` |
| `reclaimed` | `cancelled` | `reclaimed` |

**注意：** Kanban task status 和 run status 是两个不同的概念。`task.status = "running"` 表示任务有活跃 worker；`run.status = "running"` 表示特定执行尝试正在进行。统一合同 Task status 由 task.status 映射，统一 Run status 由 run outcome 映射。

### 2.3 事件映射（Phase 3 明确白名单）

使用明确白名单控制支持的 event kind。不在白名单中的 kind → `UnsupportedRecord`。

**Phase 3 支持的事件（语义映射）：**

| Kanban kind | 统一 event_type | event_scope | 说明 |
|------------|----------------|-------------|------|
| `created` | `kanban.task_created` | `task` | |
| `assigned` | `kanban.task_assigned` | `task` | |
| `claimed` | `kanban.run_claimed` | `run` | |
| `scheduled` | `kanban.task_scheduled` | `task` | |
| `promoted` | `kanban.task_promoted` | `task` | |
| `promoted_manual` | `kanban.task_promoted` | `task` | 与 promoted 合并 |
| `completed` | `kanban.run_completed` | `run` | |
| `blocked` | `kanban.run_blocked` | `run` | |
| `unblocked` | `kanban.run_unblocked` | `run` | |
| `gave_up` | `kanban.task_gave_up` | `task` | 断路器 |
| `reclaimed` | `kanban.run_reclaimed` | `run` | |
| `timed_out` | `kanban.run_timed_out` | `run` | |
| `crashed` | `kanban.run_crashed` | `run` | |
| `archived` | `kanban.task_archived` | `task` | |
| `linked` | `kanban.task_linked` | `task` | |
| `unlinked` | `kanban.task_unlinked` | `task` | |
| `decomposed` | `kanban.task_decomposed` | `task` | |

**Phase 3 不支持（→ UnsupportedRecord）的事件：** `claim_rejected`, `claim_extended`, `spawned`, `completion_blocked_hallucination`, `suspected_hallucinated_references`, `stale`, `respawn_guarded`, `edited`, `specified`, `commented`, `attachment_removed`, `heartbeat`, `tip_scratch_workspace`, `protocol_violation`, `rate_limited`, `reprioritized`

这些事件是内部诊断/调度/编辑元数据，不影响 Task/Run 语义。Phase 4+ 可逐步纳入。

### 2.4 关系映射

```
task_links(parent_id, child_id) →
  TaskRelation:
    type: "parent_child" (默认)
    type: "swarm" (仅当 parent 为 swarm root 且有 workflow_template_id)

判定规则：
  - parent 有 workflow_template_id → type=swarm
  - 否则 → type=parent_child
  - 禁止从 title/goal/task_index 推断类型
```

### 2.5 SessionBinding

```
tasks.session_id (NOT NULL 时) →
  SessionBinding(source="feishu"/"cli"/"discord"/..., session_id=tasks.session_id)
```

### 2.6 Run 元数据

- `task_runs.summary` → `Run.summary`
- `task_runs.error` → `Run.error_summary`
- `task_runs.metadata` (JSON) → 解析为 `SchedulerMetadata` / `ProcessMetadata`
- `task_runs.started_at` / `ended_at` → `Run.started_at` / `ended_at`

### 2.7 异常处理

| 场景 | 行为 |
|------|------|
| task 无任何 run（从未 claim） | Task 正常投影，无 Run |
| run 的 task_id 不指向任何 task | `MappingError` — 外键断裂 |
| task_events 的 run_id 指向不存在的 run | event 正常投影，run_id=null |
| task_link 的 parent/child 指向不存在 task | `MappingError` |
| 未知 task status | `UnsupportedRecord` |
| 未知 run outcome | `UnsupportedRecord` |
| 未知 event kind | `UnsupportedRecord` |
| metadata JSON 解析失败 | `MappingError`，metadata=null |

---

## 3. 只读接入架构

### 3.1 连接协议

```
sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
```

- `mode=ro` — 只读，不创建、不迁移、不加锁（SQLite 共享读锁除外）
- WAL 模式下 reader 看到开始读取时的快照，不受并发 writer 影响
- SQLite busy → 重试最多 3 次（1s 间隔）
- 数据库损坏 → 投影构建失败，不影响 Kanban
- schema drift（缺少表/列）→ `MappingError`，不崩溃

### 3.2 投影输出

```
~/.hermes/projections/kanban/{board}/events.jsonl
```

### 3.3 与 Phase 1/2 的合并

Kanban 投影与 Pipeline / Delegate 投影通过 `source` 字段（`"kanban"` / `"pipeline"` / `"delegate"`）和 `kanban:` / `pipeline:` / `delegate:` 命名空间隔离：

- 三个来源的投影写入**不同输出目录**，不合并为单一 JSONL
- ID 命名空间隔离（`kanban:{board}:` vs `pipeline:{project}:` vs `delegate:{session}:`），不存在跨来源碰撞
- Kanban 数据不存在时（无 kanban.db 或无 delegations 目录），Phase 1/2 输出必须 byte-identical
- 构建工具通过独立 CLI flag（`--pipeline` / `--delegation` / `--kanban`）分别触发

---

## 4. Phase 3B 实现范围

### 4.1 代码修改

| 文件 | 修改量 | 内容 |
|------|--------|------|
| `scripts/task-run-projection.py` | +~400 行 | Kanban 映射函数、ID 函数、事件词汇表白名单、状态映射、异常处理 |
| `scripts/task-run-projection-build.py` | +~100 行 | `--kanban` CLI flag、SQLite 只读连接、board 发现、`build_kanban_projection()` |

### 4.2 测试

| 类别 | 内容 |
|------|------|
| ID 函数 | board slug + task.id / run.id → 确定性 kanban ID |
| 状态映射 | 9 task status + 7 run outcome → 统一 status |
| 事件映射 | 17 种支持 kind → DomainEventEnvelope；未知 kind → UnsupportedRecord |
| 关系映射 | parent_child、swarm、孤立 link |
| SQLite 真实数据库 fixture | 内存 db 含完整 schema + 测试数据 |
| Builder 集成 | `--kanban` flag、board 扫描、空 board |
| 异常 | 坏 metadata JSON、孤立 run、断裂 link、损坏 db |
| 跨版本回归 | Phase 1/2 acceptance SHA 不变、byte-identical rebuild |

### 4.3 不实现

- ❌ 不修改 Kanban schema、event kind 或状态流
- ❌ 不接入 Desktop / Orchestrator / Gateway
- ❌ 不自动刷新或 daemon
- ❌ 不从 Kanban 推断缺失数据
- ❌ 不映射 `task_comments`、`task_attachments`、`kanban_notify_subs`

---

## 5. 验收标准

1. Phase 1/2 全部测试通过，SHA 不变
2. Kanban 白名单事件全部映射为正确 event_type 和 event_scope
3. 未知 event kind / task status / run outcome → UnsupportedRecord
4. 确定性 ID：同 board+ID → 同统一 ID
5. SQLite 只读连接，不修改数据库
6. 空 board / 损坏 db / 缺表 → 不崩溃
7. byte-identical rebuild
8. 三个来源输出互相隔离

---

## 6. 文件清单

### 本阶段

| 文件 | 说明 |
|------|------|
| `docs/architecture/kanban-unified-task-run-phase3.md` | 本设计文档 |

### Phase 3B 预计

| 文件 | 修改量 |
|------|--------|
| `scripts/task-run-projection.py` | +~400 行 |
| `scripts/task-run-projection-build.py` | +~100 行 |
| `tests/test_task_run_projection.py` | +~280 行 |
| `tests/test_task_run_projection_build.py` | +~100 行 |
