# Hermes 统一 Task/Run 合同 — Phase 1-4 总结

> 日期：2026-06-11
> 状态：**Phase 1-4 完成**

---

## 1. 提交清单

| Phase | .hermes commit | hermes-agent commit |
|-------|---------------|---------------------|
| 1A-D | `eeb19fcb2` → `c8abf7bf0` (4 commits) | — |
| 2A-C | `b60194a92` → `f04044e42` (3 commits) | `80d5b9db2` |
| 3A-C | `609669c41` → `8ed93f21a` (3 commits) | — |
| 4A-B | `256663afa` → `e6d030763` (2 commits) | — |

---

## 2. 四来源能力矩阵

| 能力 | Pipeline | Delegate | Kanban | Control |
|------|:--:|:--:|:--:|:--:|
| 只读投影 | ✅ 747 recs | ✅ 18 recs | ✅ 115 recs | — |
| SQLite mode=ro | — | — | ✅ 7 DBs | — |
| Journal 持久化 | ✅ ledger.jsonl | ✅ delegations/ | — | ✅ commands/ |
| 确定性 ID | ✅ pipeline: | ✅ delegate: | ✅ kanban: | ✅ command_id |
| Event 映射 | ✅ 10 types | ✅ 2 types | ✅ 17 whitelist | — |
| UnsupportedRecord | ✅ 8 (run_queued) | ✅ 0 | ✅ 19 diagnostics | — |
| 控制命令 | — | — | ✅ approve/reject | — |
| CAS 并发 | — | — | ✅ expected_run_id | — |

---

## 3. 测试总览

| 套件 | 数量 |
|------|------|
| Pipeline projection (Phase 1) | 185 |
| Delegate projection (Phase 2) | 41 |
| Kanban projection (Phase 3) | 29 |
| Control (Phase 4) | 27 |
| **Projection total** | **282** |
| Delegate agent (hermes-agent) | 135 |
| **Grand total** | **417** |

---

## 4. 确定性 ID 规则

```
Pipeline:  "pipeline:{project}:task/{run}:{source_id}"
Delegate:  "delegate:{session}:task/{run}:{dcid}:{idx}"
Kanban:    "kanban:{board}:task/{run}/{event}:{source_pk}"
Control:   SHA-256("control:{target}:{type}:{at}:{nonce}")[:32]
```

---

## 5. 已知限制

- Pipeline: 8 UnsupportedRecord (run_queued), 无运行时控制
- Delegate: 流式事件不持久化, crashed 推迟, 控制仅进程存活期
- Kanban: 36 event kinds (17 whitelist + 19 diagnostic), swarm 判定 best-effort
- Control: 仅 Kanban approve/reject, Pipeline/Delegate 推迟

---

## 6. 后续阶段

| Phase | 范围 | 前置条件 |
|-------|------|----------|
| Phase 5 | Desktop 消费统一投影 | RunOrchestrator 实现 |
| Phase 4D+ | Pipeline/Delegate 控制扩展 | 来源系统控制入口就绪 |
| — | Agent Fleet 编排 | Phase 1-5 稳定 |
