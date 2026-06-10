# Hermes 统一 Task/Run 合同 — Phase 1-3 总结

> 日期：2026-06-11
> 状态：**Phase 1-3 完成**

---

## 1. 提交清单

| Phase | .hermes commit | hermes-agent commit | 说明 |
|-------|---------------|---------------------|------|
| 1A | *(in 1B)* | — | 数据模型 + 纯映射函数 |
| 1B | `eeb19fcb2` | — | Shadow projection builder |
| 1C | `a85e8a1df` | — | 端到端验收 |
| 1D | `c8abf7bf0` | — | 正式投影、审计、Schema 冻结 |
| 2A | `b60194a92` | — | Delegate 审计与设计 |
| 2B | `37064118c` | `80d5b9db2` | Delegate journal + 投影 |
| 2C | `f04044e42` | — | Delegate closeout |
| 3A | `609669c41` | — | Kanban 审计与设计 |
| 3B | `afc191bd4` | — | Kanban SQLite 只读投影 |
| 3C | *(pending)* | — | Kanban closeout + Phase 1-3 summary |

---

## 2. 三来源权威事实源

| 来源 | 命名空间 | 事实源 | 只读/可重建 | 记录数 |
|------|----------|--------|------------|--------|
| **Pipeline** | `pipeline:{project}:` | `~/.claude/teams/{project}/inbox/`, `ledger.jsonl`, `events.jsonl`, `review/*.json` | 派生投影可删除重建 | 747 |
| **Delegate** | `delegate:{session}:` | `~/.hermes/delegations/{session}.jsonl` | Journal 不可删，投影可重建 | 18 |
| **Kanban** | `kanban:{board}:` | `~/.hermes/kanban.db`, `kanban/boards/{slug}/kanban.db` | SQLite mode=ro，投影可重建 | 115 |

三来源 ID 命名空间隔离，独立输出目录，无跨来源误去重。

---

## 3. 统一实体映射总览

```
Task       ← Pipeline inbox, Delegate journal started, Kanban tasks
Run        ← Pipeline ledger run_started/finished, Delegate journal, Kanban task_runs
TaskRelation ← Pipeline revision, Kanban task_links (parent_child/swarm)
RunRelation  ← Delegate journal parent_delegate_run_id
DomainEventEnvelope ← Pipeline lifecycle/run events, Delegate run_started/finished, Kanban 17 whitelisted event kinds
ReviewDecision ← Pipeline gate records
Artifact    ← Pipeline outbox
Evidence    ← Pipeline outbox + gate records
```

---

## 4. 确定性 ID 规则

```
Pipeline:  "pipeline:{project}:task/{run}:{source_id}"
Delegate:  "delegate:{subagent_session_id}:task/{run}:{delegate_call_id}:{task_index}"
Kanban:    "kanban:{board}:task/{run}/{event}:{source_pk}"

Event ID:  SHA-256("{namespace}:{identity}")[:32]
```

禁止 timestamp、PID、随机 UUID、文件顺序回退。

---

## 5. 测试总览

| 套件 | 数量 |
|------|------|
| Pipeline projection (Phase 1) | 185 |
| Delegate projection (Phase 2) | 41 |
| Kanban projection (Phase 3) | 29 |
| **Projection total** | **255** |
| Delegate agent (hermes-agent) | 135 |
| **Grand total** | **390** |

---

## 6. 已知限制（全 Phase）

| 限制 | Phase |
|------|-------|
| Pipeline `run_queued` 事件 | Phase 1 — 8 UnsupportedRecord |
| Delegate 流式事件不持久化 | Phase 2 — thinking/tool/progress |
| Delegate crashed 判定推迟 | Phase 2 — started-only → running |
| Kanban 内部诊断事件 | Phase 3 — 17 UnsupportedRecord（含 3 新发现 kind） |
| Kanban swarm 判定 | Phase 3 — 依赖 workflow_template_id |
| 三来源跨来源关系 | 全 Phase — 不推断 |

---

## 7. 后续阶段建议

| Phase | 范围 | 前置条件 |
|-------|------|----------|
| Phase 4 | 统一控制接口 + Review/Gate 统一 | Phase 1-3 稳定 |
| Phase 5 | Desktop 消费统一投影 | RunOrchestrator 实现 |
| — | Kanban event kind 补充 | Phase 3 发现新 kind |

---

## 8. 文件清单总览

### .hermes repo

| 目录 | 关键文件 |
|------|----------|
| `scripts/` | `task-run-projection.py`（1782+380 lines）、`task-run-projection-build.py`（515+91 lines）、`task-run-projection-acceptance.py` |
| `tests/` | `test_task_run_projection.py`、`test_task_run_projection_build.py`、`test_task_run_projection_acceptance.py` |
| `docs/architecture/` | `unified-task-run-contract.md`、`pipeline-event-schema-phase1.md`、`delegate-task-projection-phase2.md`、`kanban-unified-task-run-phase3.md`、`unified-task-run-phase1-3-summary.md` |
| `docs/releases/` | `unified-task-run-phase1-closeout.md`、`phase2-delegate-projection-closeout.md`、`unified-task-run-phase3-closeout.md` |

### hermes-agent repo

| 文件 | 说明 |
|------|------|
| `tools/delegate_tool.py` | +268 lines — journal 双阶段写入 |
| `run_agent.py` | +6 lines — tool_call_id 参数 |
| `agent/tool_executor.py` | +2 lines — 顺序路径 |
| `agent/agent_runtime_helpers.py` | +2 lines — 并发路径 |
