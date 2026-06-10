# Unified Task/Run Control Interface — Phase 4A 审计与设计

> 状态：**Phase 4A — 审计与设计（修订版，本阶段不实现代码）**
> 日期：2026-06-11
> 基于：Phase 1-3 已推送

---

## 1. 审计：真实控制入口（附源码行号）

### 1.1 Pipeline（run-task-gate.py）

**关键发现：Pipeline 没有独立的外部 approve/reject 入口。** `run_gate()` (line 490) 始终运行完整的 verify→review→gate-policy 链。不存在「仅设置 gate_decision=approved」的轻量接口。

| 能力 | 真实入口 | 说明 |
|------|----------|------|
| gate 决策 | `run_gate()` → verify-task.py + review-task.py + gate-policy.py | 完整 pipeline，非独立 approve |
| revision 创建 | `build_revision_inbox()` | 从 gate record 生成 revision inbox |
| auto revision dispatch | `dispatch_command()` | 重新 dispatch revision |
| 生命周期追踪 | `run_with_ledger()` | lifecycle_event + run_started + run_finished |

**Phase 4B 结论：Pipeline 不纳入 approve/reject 的 Phase 4B 范围。** 实现 Pipeline approve 需要完整 gate 运行——这与统一控制接口的「轻量命令」目标冲突。Pipeline approve/reject 推迟到 Phase 4C+（需要更深入的 gate 重构或 wrapping）。

### 1.2 Delegate（delegate_tool.py）

| 能力 | 函数 | 源码行号 | 约束 |
|------|------|----------|------|
| interrupt | `interrupt_subagent(subagent_id)` | line 192 | 进程存活期内有效 |
| pause spawn | `set_spawn_paused(True)` | line 162 | 全局；不中断运行中子 Agent |
| resume spawn | `set_spawn_paused(False)` | line 162 | 恢复 |
| 查询活跃 | `list_active_subagents()` | line 215 | 返回 `[{subagent_id, parent_id, depth, goal, model, started_at, status, tool_count}]` |

**Phase 4B 结论：Delegate 控制不纳入 Phase 4B。** 全部控制在进程存活期，跨重启后 `_active_subagents` 丢失 → 命令结果 `failed_unavailable`。

### 1.3 Kanban（kanban_db.py）

**关键发现：Kanban 有真实的、可外部调用的控制入口，且已有 `expected_run_id` 乐观锁机制。**

| 能力 | 函数 | 源码行号 | 参数 |
|------|------|----------|------|
| 完成 | `complete_task(conn, task_id, *, result, summary, metadata, created_cards, expected_run_id)` | line 3562 | `expected_run_id` 提供乐观并发控制 |
| 归档 | `archive_task(conn, task_id)` | line 4543 | 设置 status=archived, 清除 claim |
| 阻塞 | `block_task(conn, task_id, reason)` | line 4047 | 设置 outcome=blocked |
| 解阻 | `unblock_task(conn, task_id)` | line 4173 | 恢复 ready |
| 抢占 Review | `claim_review_task(conn, task_id, ttl_seconds)` | line 3086 | CAS claim |

**Phase 4B 结论：Kanban 是唯一有 ready-to-use 控制入口的来源。** Phase 4B 仅实现 Kanban 的 `approve`（→ `complete_task`）和 `reject`（→ `archive_task`）。

---

## 2. 控制模型（修订版）

### 2.1 CommandEnvelope

```
CommandEnvelope {
  command_id:        string        // 必填。SHA-256("{source}:{target_id}:{command_type}:{requested_at}:{nonce}")[:32]
  command_type:      string        // 必填。Phase 4B: "approve" | "reject"
  target_task_id:    string        // 必填。统一 Task ID（kanban:{board}:task:{id}）
  target_run_id:     string?       // 可选。统一 Run ID。不提供时作用于 Task 的当前活跃 Run
  requested_by:      string        // 必填。非空。"user" | "codex" | "ambrosini" | ...
  requested_at:      timestamp     // 必填。ISO-8601
  reason:            string?       // 可选
  expected_version:  string?       // 可选。Kanban 使用 task_runs.id 的字符串形式
}
```

**target 一致性校验：** 同时提供 `target_task_id` 和 `target_run_id` 时，必须验证 Run 确实属于该 Task（从统一投影中校验 `run.task_id == target_task_id`）。不匹配 → rejected。

### 2.2 CommandResult

```
CommandResult {
  command_id:        string        // 与请求相同
  status:            string        // accepted | rejected | completed | failed_unavailable
  accepted_at:       timestamp?    // 接受时设置
  completed_at:      timestamp?    // 来源系统产生权威事件后设置
  source_event_id:   string?       // 来源系统产生的事件 ID（Kanban: task_events.id）
  error:             string?       // 失败原因
  details:           object?       // 来源系统特定响应
}
```

### 2.3 命令生命周期

```
requested → accepted → (来源系统执行) → completed
                 ↓              ↓
              rejected      failed_unavailable

rejected 原因：
  - target_task_id 命名空间不是 "kanban:"
  - Task 不存在（投影中无记录）
  - Task 已终态（done/archived）
  - target_run_id 不归属于 target_task_id
  - expected_version 不匹配（并发冲突）
  - command_type 不是 "approve" | "reject"（UnsupportedCommand）
  - requested_by 为空

failed_unavailable 原因：
  - Kanban SQLite 不可写（mode=ro、权限错误、磁盘满）
  - SQLite busy 超时（重试 3 次后放弃）
```

**命令不是事实事件。** 命令成功执行后，Kanban 产生 `completed` 或 `archived` event kind（写入 `task_events` 表），投影从权威事件重建状态。

---

## 3. 幂等与并发

### 3.1 命令日志

```
~/.hermes/commands/{yyyy-mm-dd}.jsonl
```

每次命令执行追加一行：

```jsonl
{"command_id":"abc123...","command_type":"approve","target_task_id":"kanban:default:task:t6","target_run_id":null,"requested_by":"user","requested_at":"2026-06-11T10:00:00Z","status":"completed","source_event_id":"42","completed_at":"2026-06-11T10:00:01Z"}
```

写入协议：flock + O_APPEND + 单次 write + fsync（同 delegation journal）。

### 3.2 command_id 幂等

```
1. 收到命令 → 用 command_id 查命令日志
2. 已存在 + status=completed → 返回已有 CommandResult
3. 已存在 + 内容不同 → rejected（command_id 冲突，禁止重复不同请求）
4. 不存在 → 执行 → 追加命令日志 → 返回 CommandResult
```

### 3.3 崩溃恢复（三窗口）

**窗口 1：命令日志已写 accepted，来源未执行**

- 恢复：下次收到相同 command_id → 日志显示 "accepted" → 重新执行
- Kanban `complete_task` 幂等：task 仍是 running/ready → 正常执行 ✓
- 安全：不会重复完成 ✓

**窗口 2：来源已执行（task done/archived），命令日志未更新**

- 恢复：收到相同 command_id → 日志显示 "accepted" → **先读 Kanban 权威状态再执行**
  - task.status=done → 命令已静默成功 → 更新日志为 "completed"，返回成功
  - task.status=archived → 命令已静默成功 → 更新日志为 "completed"，返回成功
  - task.status 仍是 running/ready → 窗口 1，执行命令
- **禁止直接重新执行 `complete_task` 后根据返回值猜测。** `complete_task` 返回 False 可能是「已完成」也可能是「其他并发操作抢先」。
- 正确做法：**先通过只读 SELECT 确认 Kanban task 当前状态**。已到达目标状态 → completed。未到达 → 执行命令。

**窗口 3：来源已执行 + 命令日志已更新**

- 日志显示 "completed" → 幂等返回已有结果 ✓

**三重保护总结：**
1. 命令日志（持久化命令状态）
2. Kanban 权威状态预检（区分窗口 1 和窗口 2）
3. Kanban `expected_run_id` CAS（仅 approve，防止并发重复 complete）

### 3.4 expected_run_id 并发控制（仅 approve，Kanban native）

**源码验证（kanban_db.py:3630-3660）：**

```python
if expected_run_id is None:
    cur = conn.execute("""UPDATE tasks SET status='done', ...
        WHERE id=? AND status IN ('running','ready','blocked')""", ...)
else:
    cur = conn.execute("""UPDATE tasks SET status='done', ...
        WHERE id=? AND status IN ('running','ready','blocked')
        AND current_run_id = ?""", (..., int(expected_run_id)))
if cur.rowcount != 1:
    return False  # CAS failed or task not in valid status
```

`expected_run_id` 向 UPDATE 添加 `AND current_run_id = ?` 条件——标准 CAS（compare-and-swap）。如果当前 `current_run_id` 与期望值不匹配（例如被 dispatcher 重新 claim），`rowcount=0` → `False`。

**关键不对称性：**

| 命令 | Kanban 入口 | 乐观锁 |
|------|-----------|--------|
| `approve` | `complete_task()` | ✅ `expected_run_id` CAS |
| `reject` | `archive_task()` | ❌ 无 expected_run_id。仅检查 `status != 'archived'` |

**Phase 4B 处理：**
- `approve`：传 `expected_version` = `current_run_id`。冲突时返回 `rejected: expected_version_mismatch`
- `reject`：不传 `expected_version`。archive_task 天然幂等（archive 后再次 archive → rowcount=0 → False → `rejected: already_archived`）
- 文档明确标注 `expected_version` 仅 `approve` 有效，`reject` 不适用

---

## 4. 路由与安全

### 4.1 确定性命名空间路由

```
target_task_id 前缀：
  "kanban:"   → Kanban Adapter（唯一 Phase 4B 实现）
  "pipeline:" → UnsupportedCommand（Phase 4C+）
  "delegate:" → UnsupportedCommand（Phase 4C+）
  其他        → rejected: unknown namespace
```

**禁止：** title、time、file path 或模糊匹配。

### 4.2 Adapter 安全

- Kanban Adapter 调用 `complete_task()` / `archive_task()` 通过 SQLite 写连接
- **不**直接写投影文件或 journal
- **不**构造或伪造 `task_events` 行
- **不**修改 Kanban schema
- `requested_by` 记录到命令日志

### 4.3 审计日志

所有命令写入 `~/.hermes/commands/{date}.jsonl`。完全可审计、可重建。

---

## 5. Phase 4B 实现范围（修订版）

### 5.1 实现内容

**仅 Kanban approve/reject。**

| 文件 | 修改量 | 内容 |
|------|--------|------|
| `scripts/task-run-control.py` | ~250 行 | CommandEnvelope/Result 数据类、命令日志、idempotency、Kanban adapter（调用 `complete_task` / `archive_task`） |
| `scripts/task-run-control-cli.py` | ~100 行 | CLI 入口：`--command approve --target kanban:default:task:t6 --by user` |
| `tests/test_task_run_control.py` | ~250 行 | 路由、幂等、冲突、stale、UnsupportedCommand、崩溃恢复 |

### 5.2 测试要求

| 场景 | 验证 |
|------|------|
| `approve` 成功 | Kanban `complete_task` 被调用，task status=done |
| `reject` 成功 | Kanban `archive_task` 被调用，task status=archived |
| 重复 command_id | 返回原 CommandResult |
| 冲突 command_id（不同内容） | rejected |
| expected_version 匹配 | 执行成功 |
| expected_version 冲突 | rejected（Kanban 侧 `complete_task` 返回 False） |
| target_task_id 不存在 | rejected |
| target_task_id 不是 kanban: | UnsupportedCommand |
| target_run_id 不归属 | rejected |
| requested_by 为空 | rejected |
| Kanban DB 不可达 | failed_unavailable |
| Phase 1-3 390 tests 无回归 | ✅ |

### 5.3 不实现

- ❌ Pipeline / Delegate 命令
- ❌ cancel / interrupt / pause / resume / retry / review / qa
- ❌ UI / Gateway / Desktop
- ❌ 通用 Event Bus

---

## 6. 验收标准

1. `approve` → Kanban task done，`task_events` 有 `completed` 行
2. `reject` → Kanban task archived，`task_events` 有 `archived` 行
3. command_id 幂等，命令日志可重建
4. expected_version 冲突 → rejected
5. 非 kanban: 命名空间 → UnsupportedCommand
6. Phase 1-3 390 tests 无回归

---

## 7. 风险和开放问题

| 风险 | 缓解 |
|------|------|
| Pipeline/Delegate 控制缺失 | 明确推迟到 Phase 4C+ |
| Kanban SQLite 写需获取连接 | Phase 4B 从配置获取 kanban.db 路径 |
| expected_version 语义仅 Kanban 支持 | 来源特定，不强制统一 |
| 命令日志与投影不同步 | 命令日志只记录控制事实；状态查询走投影 |

---

## 8. 文件清单

| 文件 | 说明 |
|------|------|
| `docs/architecture/unified-task-run-control-phase4.md` | 本设计文档（修订版） |

Phase 4B 预计：
| 文件 | 修改量 |
|------|--------|
| `scripts/task-run-control.py` | ~250 行 |
| `scripts/task-run-control-cli.py` | ~100 行 |
| `tests/test_task_run_control.py` | ~250 行 |
