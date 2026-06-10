# Pipeline Event Schema — Phase 1 冻结

> 状态：**Frozen (Phase 1D review)**
> 日期：2026-06-10
> 本文档记录 Phase 1 代码实际支持的所有统一事件类型、溯源规则和约束。
> 内容必须与 `scripts/task-run-projection.py` 的真实实现一致。

---

## 1. 事实源优先级

```
ledger.jsonl  >  events.jsonl  >  (无其他来源)
  主事实源           fallback 补充
```

| 优先级 | 来源 | 角色 |
|--------|------|------|
| 1 | `runs/ledger.jsonl` | **首选事实源**。`lifecycle_event`、`run_started`、`run_finished` 三种 event。 |
| 2 | `events.jsonl` | **fallback 补充**。仅当 ledger 无匹配记录时才生成 DomainEventEnvelope。 |
| ✗ | `tasks/index.jsonl` | **永久排除**。派生 read model，不读取、不映射。 |
| ✗ | `review/*.json` | **不生成** DomainEventEnvelope。Gate record 仅投影 ReviewDecision + Evidence。 |

---

## 2. 关键数据结构约定

### 2.1 ledger lifecycle_event 双 ID 约束

`run_ledger.py` 的 `append_lifecycle_event()` 产出的 `lifecycle_event` 记录有两个不同含义的 ID 字段：

| 字段 | 含义 | 示例 |
|------|------|------|
| `event_id` | 生命周期事件的稳定标识 | `life_staam_phase1c_..._523893` |
| `run_id` | **生命周期事件自身的 ID**（与 `event_id` 相同） | `life_staam_phase1c_..._523893` |
| `related_run_id` | **真实关联的执行 Run ID**（可能为空） | `run_staam_phase1c_..._087177` |

投影器**必须**区分两者：
- 统一 `run_id` 使用 `related_run_id`，不是 lifecycle 自身的 `run_id`
- 没有 `related_run_id` 时，统一 `run_id` 为 `null`
- lifecycle 自身的 `run_id` 保留在 payload 的 `lifecycle_run_id` 字段中

### 2.2 events.jsonl run_id 约定

`events.jsonl` 中 `run_id` 即为真实执行 Run ID（无生命周期 ID 概念）。

---

## 3. 统一事件词汇表

### 3.1 event_scope 定义

| event_scope | 含义 | run_id |
|-------------|------|--------|
| `task` | 事件归属为 Task，不绑定特定 Run | 必须为 `null` |
| `run` | 事件归属为特定 Run | 必须为非 null 的 namespaced run_id |

### 3.2 事件类型一览

#### 3.2.1 来自 ledger `run_started` / `run_finished`

| event_type | event_scope | 源 event | task_id 归属 | run_id | 说明 |
|------------|-------------|----------|-------------|--------|------|
| `pipeline.run_started` | `run` | `run_started` | 原 `task_id` → namespaced | `pipeline:{project}:run:{source_run_id}` | 子进程执行开始 |
| `pipeline.run_finished` | `run` | `run_finished` | 原 `task_id` → namespaced | `pipeline:{project}:run:{source_run_id}` | 子进程执行结束 |

#### 3.2.2 来自 ledger `lifecycle_event`（Phase 1 白名单）

Phase 1 使用**明确白名单**控制支持的 lifecycle phase。未知 phase → `UnsupportedRecord`，不允许静默扩展统一事件词汇表。

| event_type | event_scope | task_id 归属 | run_id | 说明 |
|------------|-------------|-------------|--------|------|
| `pipeline.compiled` | `task` | 原 `task_id` | `null` | 任务编译完成 |
| `pipeline.execution_handoff_finished` | `task` | 原 `task_id` | `null` | 执行交接完成 |
| `pipeline.execution_handoff_started` | `task` | 原 `task_id` | `null` | 执行交接开始 |
| `pipeline.execution_policy_applied` | `task` | 原 `task_id` | `null` | 执行策略已应用 |
| `pipeline.gate_checked` | `task` | 原 `task_id` | `null` | Gate 审查完成 |
| `pipeline.opencode_result_evaluated` | `task` | 原 `task_id` | `null` | OpenCode 结果评估 |
| `pipeline.revision_created` | `task` | 原 `task_id` | `null` | Revision inbox 已生成 |
| `pipeline.revision_dispatched` | `run`（有 related_run_id 时）或 `task` | 有 `revision_task_id` 时用 revision task；否则用原 `task_id` | namespaced（有 related_run_id 时） | Revision 已派发 |

白名单常量：`_SUPPORTED_LIFECYCLE_PHASES`（共 12 个 phase）

#### 3.2.3 来自 events.jsonl（fallback，仅当 ledger 无匹配记录）

支持 7 种 event kind，使用与 ledger 完全相同的归一化函数：

| event_type | events.jsonl kind | event_scope | task_id 归属 | run_id |
|------------|-------------------|-------------|-------------|--------|
| `pipeline.gate_checked` | `gate_checked` | `task` | 原 `task_id` | `null` |
| `pipeline.revision_created` | `revision_created` | `task` | 原 `task_id` | `null` |
| `pipeline.revision_dispatched` | `revision_dispatched` | `run`（有 run_id 时） | 有 `revision_task_id` 时用 revision task | namespaced（有 run_id 时） |
| `pipeline.revision_dispatch_timeout` | `revision_dispatch_timeout` | `run`（有 run_id 时） | 同上 | namespaced（有 run_id 时） |
| `pipeline.revision_dispatch_skipped` | `revision_dispatch_skipped` | `task` | 原 `task_id` | `null` |
| `pipeline.revision_policy_blocked` | `revision_policy_blocked` | `task` | 原 `task_id` | `null` |
| `pipeline.revision_limit_reached` | `revision_limit_reached` | `task` | 原 `task_id` | `null` |

---

## 4. ID 归属规则

### 4.1 task_id

```
格式: pipeline:{project_id}:task:{source_task_id}
```

- `project_id` = Pipeline team 目录名（如 `staam`）
- `source_task_id` = Task Card 的 `task_card_id` 或 `task_id`
- Revision 事件：当 `revision_task_id` 存在且 event kind 为 `revision_dispatched` 或 `revision_dispatch_timeout` 时，使用 `revision_task_id` 作为 `source_task_id`

### 4.2 run_id

```
格式: pipeline:{project_id}:run:{source_run_id}
```

- **Ledger lifecycle_event**：使用 `related_run_id`（真实执行 Run），不是 lifecycle 自身的 `run_id`
- **Ledger run_started/run_finished**：使用顶层 `run_id`
- **events.jsonl**：使用顶层 `run_id`（即执行 Run ID）
- 禁止为缺失 run_id 的记录生成假 Run
- lifecycle 自身 `run_id` 永远不作为统一执行 Run ID

### 4.3 event_id

**Ledger lifecycle_event 来源：**
```
SHA-256("pipeline:{project_id}:ledger.jsonl:{raw_event_id}")[:32]
```

**Ledger run_started/run_finished 来源：**
```
SHA-256("pipeline:{project_id}:ledger.jsonl:{source_run_id}:started")[:32]
SHA-256("pipeline:{project_id}:ledger.jsonl:{source_run_id}:finished")[:32]
```

**events.jsonl 来源：**
```
SHA-256("pipeline:{project_id}:events.jsonl:{source_location}")[:32]
```
- `source_location` 必须包含行号（缺失 → MappingError）

---

## 5. 去重匹配键

### 5.1 匹配键格式

```
{effective_task_id}|{phase_or_kind}|{revision_task_id}|{execution_run_id}|{decision}|{attempt}
```

各字段缺失时为空字符串。

### 5.2 execution_run_id 规则

- **ledger_lifecycle_key**：使用 `related_run_id`（不使用 lifecycle 自身的 `run_id`）。因为 `events.jsonl` 的 `run_id` 是执行 Run ID，使用 `related_run_id` 才能对齐。
- **_events_jsonl_lifecycle_key**：使用顶层 `run_id`。

### 5.3 effective_task_id 规则

与 `_normalize_lifecycle` 相同路由：
- `revision_dispatched` / `revision_dispatch_timeout` 且有 `revision_task_id` → 使用 `revision_task_id`
- 其他 → 使用原 `task_id`

### 5.4 去重流程

1. 先读取所有 ledger `lifecycle_event` 记录，计算匹配键 → `ledger_keys` set
2. 读取 events.jsonl 记录，计算匹配键
3. 若匹配键在 `ledger_keys` 中 → **跳过**（合同强制）
4. 否则 → 调用 `map_events_jsonl_record` 生成 DomainEventEnvelope

---

## 6. 溯源字段

| 字段 | 来源 | ledger 值 | events.jsonl 值 |
|------|------|-----------|-----------------|
| `source` | 固定 | `"pipeline"` | `"pipeline"` |
| `source_event_id` | 原始事件标识 | ledger 的 `event_id` 或 `run_id` | `null` |
| `source_location` | 文件位置 | `"{path}:{line}"` | `"{path}:{line}"` |

---

## 7. payload 字段保留规则

### 7.1 lifecycle_event payload

归一化函数保留以下字段（存在于原始记录时）：

```
phase, status, message, decision, policy_action,
revision_task_id, attempt,
classification, exit_code, duration_seconds,
reason, max_revisions,
inbox_path, outbox_path, gate_record_path, revision_inbox_path
```

额外字段：
- `related_run_id`：规范执行 Run 链接（ledger 独有）
- `lifecycle_run_id`：lifecycle 自身 ID，用于追溯（ledger 独有）
- `run_id`：events.jsonl 的执行 Run ID（events.jsonl 独有）

### 7.2 run_started payload

```
command, cwd
```

### 7.3 run_finished payload

```
exit_code, classification, duration_seconds, stdout_tail, stderr_tail
```

---

## 8. 未知事件处理

### 8.1 ledger 未知 event 类型

非 `lifecycle_event`/`run_started`/`run_finished` → `UnsupportedRecord`

Phase 1 已知的未支持 ledger event 类型：
- `run_queued`（真实数据中 8 条记录）

### 8.2 lifecycle_event 未知 phase

不在 `_SUPPORTED_LIFECYCLE_PHASES` 白名单 → `UnsupportedRecord`

### 8.3 events.jsonl 未知 event kind

不在 7 种支持列表 → `UnsupportedRecord`

### 8.4 禁止行为

- ❌ 静默丢弃任何记录
- ❌ 将 UnsupportedRecord 强行映射为猜测数据
- ❌ 为未知事件虚构 DomainEventEnvelope
- ❌ lifecycle 自身 `run_id` 伪装为执行 Run ID
- ❌ 未知 phase 静默扩展统一事件词汇表

---

## 9. 不生成 DomainEventEnvelope 的来源

| 来源 | 产出实体 |
|------|----------|
| `inbox/*.json` | Task, TaskSpec, TaskRelation |
| `outbox/*.json` | Artifact, Evidence |
| `review/*.json` | ReviewDecision, Evidence |

---

## 10. 同时产生的非事件实体

| 原始记录 | DomainEventEnvelope | 其他实体 |
|----------|-------------------|----------|
| `run_started` | `pipeline.run_started` | Run + RunExecutionRef + ProcessMetadata |
| `run_finished` | `pipeline.run_finished` | Run（覆盖同一 run_id 的状态） |
| `lifecycle_event` | `pipeline.{phase}` | 无（仅事件） |

---

## 11. 事件排序

投影输出按确定性 `_sort_key` 排序：
1. 来源类型：inbox(0) → review(1) → ledger(2) → outbox(3) → events(4) → unknown(5)
2. source_location（文件路径 + 行号）
3. projection_type（实体类型名）
4. 稳定 identity

---

## 12. 版本信息

| 项目 | 值 |
|------|-----|
| schema_version | `"2.8"`（继承自 Pipeline 原始数据） |
| Phase 1 冻结日期 | 2026-06-10（review 修订） |
| 实现文件 | `scripts/task-run-projection.py` |
| 构建工具 | `scripts/task-run-projection-build.py` |
| 验收工具 | `scripts/task-run-projection-acceptance.py` |
