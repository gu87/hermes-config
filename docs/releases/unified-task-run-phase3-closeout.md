# Phase 3 — Kanban 统一投影 Closeout

> 日期：2026-06-11
> 状态：**Phase 3C complete**

---

## 1. Commits

| 仓库 | Commit | 说明 |
|------|--------|------|
| .hermes | `609669c41` | Phase 3A: Kanban 审计与设计文档 |
| .hermes | `afc191bd4` | Phase 3B: Kanban SQLite 只读投影实现 |
| .hermes | *(待提交)* | Phase 3C: closeout + summary 文档 |

---

## 2. 真实 Kanban 验收

### 数据源

7 个 SQLite 数据库（`mode=ro` 只读访问）：

| Board | tasks | task_runs | task_events | task_links |
|-------|-------|-----------|-------------|------------|
| default | 0 | 0 | 0 | 0 |
| dongqiudi | 11 | 8 | 45 | 8 |
| rc2-mpz47sx4 | 1 | 1 | 6 | 0 |
| rc3-mpz7dyjf | 1 | 1 | 6 | 0 |
| rc4-mpz8oukq | 1 | 1 | 9 | 0 |
| rc4-mpzauryu | 1 | 1 | 9 | 0 |
| v1-rc-test-mpz3b3at | 1 | 1 | 3 | 0 |
| **合计** | **16** | **13** | **78** | **8** |

### 投影产出

| 实体 | 数量 |
|------|------|
| Task | 16 |
| Run | 13 |
| TaskRelation | 8 |
| DomainEventEnvelope | 61 |
| UnsupportedRecord | 17 |
| **合计** | **115** |

### mode=ro 只读证明

7 个数据库投影前后 SHA-256 完全一致 ✅。

### UnsupportedRecord 分类

| 类型 | 数量 | 说明 |
|------|------|------|
| `spawned` | 10 | 诊断事件，不在白名单 |
| `commented` | 1 | 诊断事件，不在白名单 |
| `diff` | 2 | 审计遗漏（review/QA 插件事件），已加入诊断列表 |
| `review_result` | 2 | 审计遗漏，已加入诊断列表 |
| `qa_result` | 2 | 审计遗漏，已加入诊断列表 |

Phase 3C 发现 3 个审计遗漏的 event kind。已加入 `_KANBAN_DIAGNOSTIC_KINDS`，总 event kind 数从 32 更新为 36（17 whitelist + 19 diagnostic/other）。

---

## 3. 三来源联合验收

| 来源 | 记录数 | SHA-256 |
|------|--------|---------|
| Pipeline | 747 | `508b3c7071612ad3...` |
| Delegate | 18 | `e39bb74977bd184d...` |
| Kanban | 115 | `15fbb4ac9c9a1148...` |

- 三来源 ID 命名空间独立（`pipeline:` / `delegate:` / `kanban:{board}:`）✅
- 无跨来源误去重或虚构关系 ✅
- Pipeline 精简输出中无 Kanban ID ✅
- 删除联合投影后重建 byte-identical ✅
- 关闭 Kanban 后 Phase 1/2 输出 byte-identical ✅

---

## 4. 测试与回归

```
255 projection tests ✅
135 delegate tests ✅
Phase 1: SHA 508b3c70..., 747 records, 14/14 ✅
Phase 2: 18 records delegation projection ✅
py_compile ✅
git diff --check ✅
```

---

## 5. 已知限制

| 限制 | 说明 |
|------|------|
| Kanban event kind 覆盖 | 3 个新发现的内部 kind（`diff`、`review_result`、`qa_result`）不在 Phase 3A 审计中，正确映射为 UnsupportedRecord |
| 流式事件 | Phase 2/3 不持久化 thinking/tool/progress 事件 |
| crashed 判定 | Phase 2 不自动判定 crashed；started-only → running |
| Kanban swarm 判定 | 依赖 `workflow_template_id` 字段 |

---

## 6. 文件清单

### Phase 3 新增/修改

- `docs/architecture/kanban-unified-task-run-phase3.md` — 设计文档
- `scripts/task-run-projection.py` — +380 lines
- `scripts/task-run-projection-build.py` — +91 lines
- `tests/test_task_run_projection.py` — +281 lines
- `tests/test_task_run_projection_build.py` — +87 lines
- `docs/releases/unified-task-run-phase3-closeout.md` — 本 closeout
