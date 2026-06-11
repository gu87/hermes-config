# Hermes 统一 Task/Run 合同 — Phase 1-5 总结

> 日期：2026-06-11
> 状态：**Phase 1-5 完成**

---

## 1. 提交清单

| Phase | .hermes commits | hermes-agent |
|-------|----------------|--------------|
| 1A-D | 4 | — |
| 2A-C | 3 | `80d5b9db2` |
| 3A-C | 3 | — |
| 4A-C | 3 | — |
| 5A-B | 2 | — |
| **Total** | **15** | **1** |

---

## 2. 能力矩阵

| 能力 | Pipeline | Delegate | Kanban | Control | Fleet |
|------|:--:|:--:|:--:|:--:|:--:|
| 只读投影 | ✅ | ✅ | ✅ | — | — |
| Journal 持久化 | ✅ | ✅ | ✅ | ✅ | — |
| 确定性 ID | ✅ | ✅ | ✅ | ✅ | — |
| SQLite mode=ro | — | — | ✅ | — | — |
| 控制命令 | — | — | ✅ | ✅ | — |
| CAS 并发 | — | — | ✅ | ✅ | — |
| Agent 状态聚合 | — | — | — | — | ✅ |
| FleetSnapshot | — | — | — | — | ✅ |

---

## 3. 测试

```
304 projection/control/fleet + 135 delegate = 439 tests
Phase 1: SHA 508b3c70..., 747 records, 14/14 acceptance
```

---

## 4. ID 规则

```
Pipeline:  "pipeline:{project}:task/{run}:{source_id}"
Delegate:  "delegate:{session}:task/{run}:{dcid}:{idx}"
Kanban:    "kanban:{board}:task/{run}/{event}:{source_pk}"
Control:   SHA-256("control:{target}:{type}:{at}:{nonce}")[:32]
Fleet:     managed-agents.yaml agent_id
```

---

## 5. 已知限制

- Pipeline: 8 UnsupportedRecord (run_queued)
- Delegate: 流式事件不持久化, model_ref 非唯一 → unassigned
- Kanban: 36 event kinds (17 whitelist), swarm best-effort
- Control: 仅 Kanban approve/reject
- Fleet: active_agents 是计数, Gateway stale → idle
