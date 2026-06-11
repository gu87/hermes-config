# Phase 5 — Agent Fleet Status Closeout

> 日期：2026-06-11
> 状态：**Phase 5C complete**

---

## 1. Commits

| 仓库 | Commit | 说明 |
|------|--------|------|
| .hermes | `38aaa8d46` | Phase 5A: Fleet design |
| .hermes | `bcd9c38e3` | Phase 5B: Fleet implementation |

---

## 2. 真实 FleetSnapshot

**路径：** `~/.hermes/projections/fleet/snapshot.json`

**统计：** 10 agents — 0 online, 10 idle, 0 working, 0 error

**判定证据：** gateway pid=45768 存活（hermes-gateway），`gateway_state.json` `updated_at` 61min stale → idle；24h recency 过滤器消除 stale Pipeline Runs → working=0。

### Per-agent today tasks

| Agent | Tasks |
|-------|------:|
| opencode | 12 |
| deepseek-tui | 6 |
| codex | 2 |
| hermes-internal | 2 |
| Others | 0 |

### Unassigned

- `unassigned_delegate_runs`: 0
- `unassigned_kanban_assignees`: []

---

## 3. 确定性验证

- 固定 `observed_at` 重建 → byte-identical ✅
- 不同 `observed_at` → 观察字段合理变化 ✅
- 无 secret/API key 泄露 ✅

---

## 4. 测试

```
304 projection/fleet/control + 135 delegate = 439 tests ✅
Phase 1: SHA 508b3c70..., 747 records, 14/14 ✅
```

---

## 5. 已知限制

| 限制 | 说明 |
|------|------|
| `active_agents` 是计数 | 无法区分具体哪个 Agent 在线 |
| Delegate Run 归属 | 全部 `unassigned_delegate`（model_ref 非唯一） |
| Kanban assignee | best-effort 匹配 |
| observed_at 影响快照 | 不同时间的状态可能不同（预期行为） |

---

## 6. Desktop Fleet UI 前置条件

1. 统一投影与 FleetSnapshot 稳定构建
2. Desktop 只读消费 `snapshot.json`（不修改）
3. 不引入 OpenClaw 后端或 Mission Control 数据模型
4. 不新增 daemon/API/Postgres
