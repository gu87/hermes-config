# Phase 2 状态模型冲突扫描

> 对比架构文档 vs 代码中已存在的状态模型，输出冲突、复用机会、不动区域和迁移点。

扫描日期：2026-06-03
输入文档：`docs/architecture/hermes-desktop-state-model.md`、`docs/architecture/agent-adapter-layer.md`、`docs/architecture/run-orchestrator.md`
代码范围：`~/.hermes/hermes-agent/` 核心 Python 源码

---

## 状态模型总览对比

| 模型 | 新模型定义 | 代码中已存在位置 | 冲突等级 |
|------|-----------|-----------------|---------|
| TaskStatus | `draft → queued → running → needs_review → done \| failed \| blocked \| cancelled` | 3 处不同定义 | 🔴 严重 |
| SessionStatus | 无显式状态机（隐式 container） | `state.db` end_reason, `gateway/session.py` 无状态 | 🟢 无冲突 |
| RunStatus | `created → queued → starting → running → waiting_review → completed \| failed \| cancelled` | `agent-runs.json` 自由字符串 + `LedgerEventType` | 🟡 中等 |
| Binding Status | 隐式（entrypoint:channel:thread → session） | `session_binding.py` `BindingSource` 含 source 跟踪 | 🟢 可复用 |
| Executor / Agent Type | `ExecutorId = string` + `ExecutorConfig` | `registry.py` `AgentSpec` 丰富但不同工具 | 🟡 需映射 |
| Event Log | `RunEvent { seq, type, payload }` | `session_event_log.py` + `execution_policy.py` 两套事件 | 🔴 严重 |

---

## 1. TaskStatus — 🔴 严重冲突

### 新模型定义（`state-model.md`）

```
TaskStatus = draft | queued | running | needs_review | done | failed | blocked | cancelled
```

### 代码中已有 3 套定义

**a. `agent/task_card.py` — v2.8 TaskCard**

```python
VALID_STATUSES = [
    "pending", "running", "reviewing", "completed",
    "failed", "blocked", "partial",
]
```

- 持久化路径：`~/.hermes/task_cards/{task_id}.json`
- 当前生产使用约 1,786 个卡片文件
- 缺少 `draft`、`queued`、`cancelled`；多出 `partial`、`reviewing`

**b. `hermes_cli/kanban_db.py` — 看板任务**

```python
VALID_STATUSES = {"triage", "todo", "ready", "running", "blocked", "done", "archived"}
```

- 仓库级看板，侧重跨 profile 协作
- 完全不同的语义集

**c. `agent/managed_agents/kanban_bridge.py` — Managed Agent 看板桥**

```python
KANBAN_STATES = (
    "created", "planned", "delegated", "in_progress",
    "review_pending", "changes_requested", "approved",
    "done", "blocked", "failed",
)
```

- 侧重委派流程，有 `changes_requested` 等审批语义

### 冲突分析

| 差异点 | 现有代码 | 新模型 | 影响 |
|--------|---------|--------|------|
| 初始状态 | `pending` | `draft` | v0.1 需要转换 |
| 队列态 | 无 | `queued` | 新概念，需新增 |
| 审核态 | `reviewing` | `needs_review` | 名称不同，语义接近 |
| 终态 | `partial`（部分完成） | 无 `partial` | `partial` 被废弃 |
| 取消态 | 无 | `cancelled` | 新概念 |
| 完成态 | `completed` | `done` | 名称不同 |

### 复用建议

- `TaskCard` 的 `execution_plan`（`mode`、`agents`、`require_gate`）可以**完整复用**
- `CompiledIntent`、`AcceptanceCriteria` 结构可以**直接承接**
- 1,786 个现有卡片的 `pending` / `running` / `completed` 可做一次向后兼容映射

### 不动建议

- `kanban_db.py` 的看板状态**不动** — 看板是独立协作层，Desktop 不直接消费
- `kanban_bridge.py` 的 `KANBAN_STATES`**标记为 managed-agent 内部状态**，Desktop 不引用

---

## 2. SessionStatus — 🟢 无冲突

### 新模型定义

`state-model.md` 没有将 Session 定义为状态机。Session 是 `TaskThread` 的容器（`Project → TaskThread[N]`），隐含在 `session_id` 外键中。

### 代码中已有

**a. `hermes_state.py` — state.db sessions 表**

```sql
sessions (id, source, ..., started_at, ended_at, end_reason, ...)
```

- 没有 status 字段
- `end_reason` 记录结束原因（字符串）

**b. `agent/managed_agents/session.py` — Session 模型**

```python
@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    workspace_id: str
    name: str
    entrypoint: Entrypoint      # cli | feishu | discord | web | mac_app
    external_channel_id: str | None
    external_thread_id: str | None
    created_at: str
    updated_at: str
```

- 无状态字段，仅有元数据
- `entrypoint` 等价于新模型的 `TaskSource` 概念

**c. `gateway/session.py` — SessionContext**

```python
@dataclass
class SessionContext:
    source: SessionSource     # platform, chat_id, user_id, thread_id
    connected_platforms: list
    home_channels: dict
    session_key: str
    session_id: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
```

- 运行时上下文，不持久化 status

### 复用建议

- `managed_agents/session.py` 的 `Session` 模型可以直接作为 Desktop 的 session 基础，增加 `status` 字段即可
- `Session.entrypoint` 可以映射为新模型 `TaskSource`
- `state.db` 的 sessions 表 `parent_session_id` 字段支持分支（与新模型 `TaskThread.last_run_id` 对应）

### 不动建议

- `gateway/session.py` 的 `SessionSource` + `SessionContext` **不动** — 它们是 Gateway 路由上下文，不是存储模型

---

## 3. RunStatus — 🟡 中等冲突

### 新模型定义（`run-orchestrator.md`）

```
RunStatus:
  created → queued → starting → running → waiting_review
  → completed | failed | cancelled
```

### 代码中已有

**a. `agent-runs.json` — 自由字符串**

```json
{
  "run_id": "...",
  "agent_id": "pirlo",
  "status": "completed",
  "started_at": 1779868029.290837,
  "ended_at": 1779868029.290837
}
```

- `status` 是自由字符串，无类型约束
- 存储格式（工作流、agent_id、model_ref、result_summary）与新模型 `AgentRun` 已经很接近

**b. `agent/managed_agents/execution_policy.py` — LedgerEventType**

```python
class LedgerEventType(str, Enum):
    execution_queued = "execution.queued"
    execution_started = "execution.started"
    execution_completed = "execution.completed"
    execution_failed = "execution.failed"
    # ... policy.*, watchdog.*, router.*, user.*
```

- 这是**事件类型**而非状态枚举，但事件 → 状态映射已经隐含
- `execution.queued` ↔ `queued`、`execution.started` ↔ `starting`
- 多出了 `policy.*`、`watchdog.*`、`router.*` 等 Managed Agent 专用事件

### 冲突分析

| 新模型状态 | 代码中对应 | 差距 |
|-----------|-----------|------|
| `created` | `agent-runs.json` 无显式 created | 需新增 |
| `queued` | `LedgerEventType.execution_queued` ✅ | 名称一致 |
| `starting` | 无直接对应 | 需新增 |
| `running` | `agent-runs.json` "running" ✅ | 名称一致 |
| `waiting_review` | 无直接对应 | 需新增 |
| `completed` | `agent-runs.json` "completed" ✅ | 名称一致 |
| `failed` | `agent-runs.json` "failed" ✅ | 名称一致 |
| `cancelled` | `LedgerEventType` 无直接对应 | 需新增 |

### 复用建议

- `agent-runs.json` 的字段结构（`run_id`、`agent_id`/`model_ref`、`session_id`、`task_id`、`result_summary`）与新模型 `AgentRun` 高度对齐，可以直接作为持久化格式基础
- `LedgerEventType` 的事件名称可在 Orchestrator 内存中做内部映射

### 不动建议

- `agent-runs.json` 写入路径**先不动** — 确保 Desktop 的 `AgentRun` 写入不与现有 `agent-runs.json` 冲突
- `LedgerEventType` 是 Managed Agent 的内部调度事件，Desktop Orchestrator 不直接消费

---

## 4. Binding Status — 🟢 可复用

### 新模型定义

`state-model.md` 中无显式的 Binding Status，但 `Project` 概念隐含着 entrypoint → session 的绑定。

### 代码中已有

**`agent/managed_agents/session_binding.py`**

```python
BindingSource = Literal["card", "thread", "alias", "default"]

@dataclass(frozen=True, slots=True)
class SessionBindingValue:
    workspace_id: str
    session_id: str
    source: BindingSource       # 为什么产生绑定
    created_at: str
```

- 持久化到 `~/.hermes/data/session_bindings.json`
- v2.10 格式已包含 `source` 跟踪
- 支持前向兼容的旧格式（`[workspace_id, session_id]` 列表）

### 复用建议

- `SessionBindingValue` 的 source 跟踪（`card`、`thread`、`alias`、`default`）可以直接用
- 新 Desktop 的 "Project" 概念可存储为 `entrypoint=desktop` 的绑定

### 不动建议

- session_binding.json 的读写接口**不动** — 只新增 `entrypoint=desktop` 的绑定

---

## 5. Executor / Agent Type — 🟡 需映射

### 新模型定义（`agent-adapter-layer.md`）

```typescript
interface AgentExecutorAdapter {
  start(run, config): Promise<AdapterStartResult>;
  stop(runId): Promise<void>;
  streamEvents(runId): AsyncIterable<RunEvent>;
  getStatus(runId): Promise<RunStatus>;
}

type ExecutorId = string;  // v0.1: 'hermes-local'
```

### 代码中已有

**a. `agent/managed_agents/registry.py` — AgentSpec**

```python
@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    name: str
    role: str
    aliases: tuple[str, ...]
    model_ref: str
    runtime: str              # 执行器类型
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    permission: PermissionMode
    capabilities: tuple[str, ...]
    # ...
```

- `AgentSpec` 的模型字段远多于新模型的 `ExecutorConfig`（有角色、技能、工具、风险等级等）
- `AgentSpec.runtime` 接近 `ExecutorId` 概念

**b. `agent/managed_agents/execution_policy.py` — TaskType**

```python
class TaskType(str, Enum):
    implementation | bugfix | refactor | test | review
    | architecture | documentation | smoke | migration | investigation
```

- 与 `state-model.md` 的 `TaskSource`（`desktop | feishu | api | cron`）是不同概念
- `TaskType` 是任务分类，`TaskSource` 是来源

**c. `agent/managed_agents/capability_matrix.py`**

- Task type → model tier / timeout / context budget 的预配置映射
- 新模型的 `ExecutorConfig` 可以读取这些作为默认值

### 复用建议

- `AgentRegistry` 的 `resolve_agent_id()` → `AgentSpec` 查找链路可以用于 Desktop 的路由预览（v0.3+）
- `AgentSpec.runtime` 可以映射到 `ExecutorId`
- `capability_matrix.py` 的超时和上下文预算可以复用为 Desktop `ExecutorConfig` 的默认值

### 不动建议

- `AgentRegistry` 的完整 schema（`alias_map`、`find_by_capability`、`risk_allowed` 等）在 v0.1 **不引入** — 它们属于 Managed Agent 调度层
- `config/agent-registry.json` 文件格式**不动** — Desktop 只需新增 `executor_id: 'hermes-local'` 的硬编码

---

## 6. Event Log — 🔴 严重冲突

### 新模型定义（`state-model.md`）

```typescript
type RunEventType =
  'message' | 'reasoning' | 'tool_call' | 'tool_result'
  | 'log' | 'diff' | 'approval_needed' | 'review_decision'
  | 'completed' | 'failed';

interface RunEvent {
  id: string;
  run_id: string;
  seq: number;          // 单调递增
  type: RunEventType;
  payload: unknown;
  created_at: string;
}
```

### 代码中已有 3 套事件系统

**a. `agent/session_event_log.py` — EventLog（events.db）**

```python
EVENT_TASK_CREATED = "task_created"
EVENT_TASK_UPDATED = "task_updated"
EVENT_STATUS_CHANGED = "status_changed"
EVENT_EXECUTION_STARTED = "execution_started"
EVENT_EXECUTION_COMPLETED = "execution_completed"
EVENT_EXECUTION_FAILED = "execution_failed"
EVENT_ARTIFACT_CREATED = "artifact_created"
# + Sprint 5: intent_inferred, task_classified, dispatch_decision, ...
# + Phase A: subagent.started, subagent.completed, ...
```

- Schema：`events(event_id, session_id, task_id, type, timestamp, source, payload_json)`
- SQLite 持久化到 `events.db`
- 事件绑定了 `session_id` + `task_id`，而非 `run_id`（新模型是 `run_id`）

**b. `agent/managed_agents/event_log.py` — ManagedAgentEventLog**

```python
EVENT_POLICY_EVALUATED = "policy_evaluated"
EVENT_TASK_DELEGATED = "task_delegated"
EVENT_TASK_RESULT_RECEIVED = "task_result_received"
EVENT_TOOL_PERMISSION_DENIED = "tool_permission_denied"
EVENT_REVIEW_REQUESTED = "review_requested"
EVENT_REVIEW_COMPLETED = "review_completed"
```

- 是 EventLog 的薄包装
- 关注委派生命周期，而非执行器事件流

**c. `agent/managed_agents/execution_policy.py` — LedgerEventType**

```python
class LedgerEventType(str, Enum):
    execution_queued = "execution.queued"
    execution_started = "execution.started"
    # ... policy.*, watchdog.*, router.*, user.*
```

- 是运行运维事件（策略评估、看门狗、路由），不直接对应 `RunEventType`

### 冲突分析

| 差异点 | 现有代码 | 新模型 | 影响 |
|--------|---------|--------|------|
| 事件定义域 | task/subagent/agent 生命周期 | run 执行事件流 | 根本意图不同 |
| 主实体 | `task_id` + `session_id` | `run_id` + `seq` | 数据模型不同 |
| 排序 | `timestamp` | `seq`（单调递增） | 新模型取消了对 wall clock 的依赖 |
| 持久化 | SQLite `events.db` | 未指定（建议 Store 层） | 可复用 SQLite |
| event 类型数量 | 20+ | 10 | 新模型更精简 |
| `message/reasoning/tool_call/tool_result` | 存在 `state.db` messages 表 | 在 `RunEvent` 中 | 这是最大冲突点 |

### 最严重的冲突点

`RunEvent.message` / `RunEvent.reasoning` / `RunEvent.tool_call` / `RunEvent.tool_result` 的事件类型在现有代码中**存储在 `state.db` 的 `messages` 表中**，而不是 `events.db` 中：

```sql
messages (session_id, role, content, tool_call_id, tool_calls, tool_name, timestamp, ...)
```

这意味着新模型的 RunEvent 需要**重新定义执行事件的存储位置**：

- **方案 A**：在 `events.db` 中新增 `run_id` + `seq` 列，将 `messages` 表的工具事件镜像写入
- **方案 B**：使用独立的 `run_events` 表（新 SQLite 或 JSON 文件）
- **方案 C**：用 adapter 适配器将现有 `messages` 表映射到 `RunEvent`

### 复用建议

- `agent/session_event_log.py` 的 SQLite 基础设施（连接管理、锁、WAL）可以直接复用
- `SessionEvent` 的 `event_id` + `type` + `payload_json` 结构与 `RunEvent` 的 `id` + `type` + `payload` 结构一致

### 不动建议

- `state.db` 的 `messages` 表**不动** — 它是 CLI/Gateway 的主要会话历史存储
- `events.db` 的现有 task/subagent 事件**不动** — Desktop 只新增 run 事件，不侵入已有 namespace
- `LedgerEventType`**不动** — Managed Agent 内部运维事件，Desktop 不消费

---

## 7. v0.1 迁移注意点

### 7.1 TaskCard 迁移

```
现有 → 新映射
TaskCard.status "pending"   → TaskThread.status "draft"    # 新创建时
TaskCard.status "running"   → TaskThread.status "running"   # 直接映射
TaskCard.status "reviewing" → TaskThread.status "needs_review"  # 名称映射
TaskCard.status "completed" → TaskThread.status "done"      # 名称映射
TaskCard.status "failed"    → TaskThread.status "failed"    # 直接映射
TaskCard.status "blocked"   → TaskThread.status "blocked"   # 直接映射
TaskCard.status "partial"   → (废弃，v0.1 不迁移)
```

**动作**：

- v0.1 创建 `TaskThread` 时需要自增转换层
- 现有 1,786 个 JSON 卡片文件**读兼容** — 转换层负责读取旧格式

### 7.2 AgentRun 持久化

```
agent-runs.json 现有格式：
  run_id, agent_id, status, started_at, ended_at,
  task_id(nullable), session_id(nullable), result_summary, error

新 AgentRun 需要新增：
  thread_id (必需), executor_id (v0.1='hermes-local'),
  prompt, worktree_path(v0.4), base_path
```

**动作**：

- v0.1 需要新建 `AgentRun` 存储（建议独立的 SQLite 或接入 `state.db`）
- `agent-runs.json` 不要动 — 它被 Dashboard v1 和现有 CLI 读取
- `LedgerEventType` 不要引入到 Desktop，Desktop 使用自己的 `RunStatus` 枚举

### 7.3 事件流迁移

```
现有消息流 (state.db messages table)：
  session_id → messages (role, content, tool_calls, ...)

Desktop RunEvent 流 (新存储)：
  run_id → events (seq, type, payload)
```

**关键是不要双写现有 `state.db` 的 `messages` 表**。v0.1 的 Adapter 需要在读取 Hermes 后端 SSE 流时：

- 将 SSE 事件归一化为 `RunEvent`
- 持久化到新的 `run_events` 存储
- **不要再写入 `state.db` 的 `messages` 表**

### 7.4 状态转换验证

| 转换 | 谁执行 | 检查点 |
|------|--------|--------|
| draft → queued | User submits task in UI | Orchestrator.createRun() |
| queued → starting | Orchestrator.startRun() | Adapter.start() 返回前 |
| starting → running | Adapter.start() 返回 | 收到首个非起始事件 |
| running → waiting_review | Adapter 上报 approval_needed | RunEvent.type 检查 |
| waiting_review → running | resolveReview(continue) | ReviewDecision 记录 |
| waiting_review → done | resolveReview(done) | ReviewDecision 记录 |
| → completed | Adapter 上报 completed 或正常运行结束 | RunEvent.type 检查 |
| → failed | Adapter 上报失败或异常 | error_summary 填充 |
| → cancelled | UI stop 或外部中断 | 幂等写入 |

**不要在 v0.1 实现**：`retryRun`（创建新 Run 而非修改旧 Run）、`continueThread`（追加 prompt）、`blocked` 状态

### 7.5 SQLite 复用决策

| 数据库 | 复用方式 | 原因 |
|--------|---------|------|
| `state.db` | **只读**（读取 session 历史） | Desktop 只消费不写入现有会话数据 |
| `events.db` | **新增** `run_events` 表 | 复用 `EventLog` 的 SQLite 连接和 WAL 模式 |
| `kanban.db` | **不动** | 看板是独立协作层 |
| Desktop 新建 | 建议新建 `desktop.db` 或 `desktop_state.db` | 隔离 Desktop 专用状态，不污染现有数据库 |

---

## 8. 总结：v0.1 行动清单

| 优先级 | 动作 | 涉及文件 |
|--------|------|---------|
| P0 | 定义 `RunStatus` 枚举（8 值） + `TaskStatus` 枚举（8 值） | 新建 `desktop/models/` |
| P0 | 实现 `TaskCard → TaskThread` 向前兼容映射器 | `agent/task_card.py` 只读 |
| P0 | 新建 `RunEvent` 存储（SQLite `run_events` 表） | 复用 `events.db` 或新建 |
| P0 | HermesLocalAdapter: Hermes SSE → `RunEvent` 归一化 | `acp_adapter/server.py` 参考 |
| P1 | 定义 `AgentExecutorAdapter` 接口 | 新建 `desktop/adapter/` |
| P1 | `ExecutorId = 'hermes-local'` 硬编码，`ExecutorConfig` 从现有配置读取 | `hermes_cli/config.py` |
| P1 | `session_binding.py` 的 `SessionBindingValue` 复用于 Desktop 绑定 | 只读已存在 |
| P2 | `TaskType` 枚举可以从 `execution_policy.py` 引用 | 避免重复定义 |
| P3 | `AgentSpec` 路由预览 | `agent/managed_agents/registry.py` v0.3+ |
| — | **不动** `state.db` messages 表 | — |
| — | **不动** `kanban_db.py` 看板状态 | — |
| — | **不动** `agent-runs.json` 写入路径 | — |
| — | **不动** `LedgerEventType` 运维事件 | — |
