# Phase 4 — Unified Control Interface Closeout

> 日期：2026-06-11
> 状态：**Phase 4C complete**

---

## 1. Commits

| 仓库 | Commit | 说明 |
|------|--------|------|
| .hermes | `256663afa` | Phase 4A: Control interface design |
| .hermes | `e6d030763` | Phase 4B: Kanban-only control implementation |

---

## 2. 实现范围

### 支持的命令

| 命令 | Kanban 入口 | CAS | 说明 |
|------|-----------|:--:|------|
| `approve` | `complete_task(conn, task_pk, expected_run_id)` | ✅ | transitions task → done |
| `reject` | `archive_task(conn, task_pk)` | ❌ | transitions task → archived |

### 不支持的命令（→ UnsupportedCommand）

- Pipeline: approve / reject / revision — gate always requires full verify→review chain
- Delegate: interrupt / pause — 仅在进程存活期可用
- cancel / retry / review / qa — 无真实实现

---

## 3. 真实 CLI 验收证据

使用临时 Kanban SQLite DB 和真实 `task-run-control-cli.py`：

| 测试 | 结果 |
|------|------|
| `approve kanban:demoboard:task:demo-1` | ✅ completed, source_event_id=1 |
| `reject kanban:demoboard:task:demo-2` | ✅ completed, source_event_id=2 |
| `approve pipeline:staam:task:t1` | ✅ rejected (unsupported namespace, exit 1) |
| `approve delegate:s1:task:tc:0` | ✅ rejected (unsupported namespace, exit 1) |
| `approve` already done task | ✅ completed (idempotent) |
| Same `--command-id` retry | ✅ same result, no duplicate side effect |
| Structured JSON output | ✅ |
| Exit codes: success=0, rejected=1 | ✅ |

---

## 4. 幂等与崩溃恢复

- 命令日志：`~/.hermes/commands/{date}.jsonl` (flock + O_APPEND + fsync)
- 窗口 1 (日志 accepted, Kanban 未修改) → 安全重试 ✅
- 窗口 2 (Kanban 已 done/archived, 日志未更新) → 权威预检 → completed ✅
- 窗口 3 (全部持久化) → 幂等返回 ✅

---

## 5. 安全边界

- board slug 使用 `_BOARD_RE` 严格校验，拒绝路径穿越
- Pipeline/Delegate 命名空间 → UnsupportedCommand
- `reject` 携带 `expected_version` → 拒绝（不对称性已标注）
- 命令日志不写 Kanban SQLite、来源 journal 或统一投影

---

## 6. 测试结果

```
282 projection + 135 delegate + 27 control = 417 tests ✅
Phase 1: SHA 508b3c70..., 747 records, 14/14 ✅
```

---

## 7. 已知限制

| 限制 | 说明 |
|------|------|
| Pipeline/Delegate 控制 | 推迟到 Phase 4D+ |
| cancel/retry/review/qa | 无真实入口 |
| expected_version 仅 approve | reject 无 CAS |
| Delegate 进程重启 | 控制不可用 |
