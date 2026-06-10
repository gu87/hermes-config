# Phase 2 — Delegate Task Projection Closeout

> 日期：2026-06-10
> 状态：**Phase 2C complete — ready for Phase 3**

---

## 1. Commits

| 仓库 | Commit | 说明 |
|------|--------|------|
| .hermes (`main`) | `37064118c` | feat: project delegate task journals into unified runs |
| hermes-agent (`codex/desktop-browser-visible-phase3`) | `80d5b9db2` | feat: persist delegate task run journals |

---

## 2. 实现内容

### 2.1 hermes-agent（4 files, +271/-7）

| 文件 | 内容 |
|------|------|
| `tools/delegate_tool.py` | Journal 双阶段写入（`_write_started` before `run_conversation`、`_write_terminal` in finally）、确定性 ID 函数、`_build_delegate_tool_trace`、Phase 2B 身份字段（`parent_delegate_task_id`/`parent_delegate_run_id`/`root_task_id`）、registry handler `tool_call_id` 提取 |
| `run_agent.py` | `_dispatch_delegate_task` 增加 `tool_call_id` 参数 |
| `agent/tool_executor.py` | 顺序路径传入 `tool_call_id=tool_call.id` |
| `agent/agent_runtime_helpers.py` | 并发路径传入 `tool_call_id=tool_call_id` |

### 2.2 .hermes（4 files, +947 lines）

| 文件 | 内容 |
|------|------|
| `scripts/task-run-projection.py` | Delegation 映射（ID 函数、数据类、pairing、dedup、冲突检测、异常边界规则） |
| `scripts/task-run-projection-build.py` | `build_delegation_projection` + `--delegation` CLI flag |
| `tests/test_task_run_projection.py` | 37 delegation 映射测试 |
| `tests/test_task_run_projection_build.py` | 4 CLI wrapper 测试 + 8 builder 去重集成测试 |

---

## 3. Journal Schema

```
~/.hermes/delegations/{parent_session_id}.jsonl
```

```
run_started:
{"schema_version":"delegate_v1","phase":"run_started","parent_session_id":"uuid","delegate_call_id":"toolu_xxx","task_index":0,"subagent_session_id":"uuid","parent_delegate_task_id":null,"parent_delegate_run_id":null,"root_task_id":null,"depth":1,"role":"leaf","goal":"...","toolsets":["read"],"model":"claude-sonnet-4-6","started_at":"..."}

run_finished:
{"schema_version":"delegate_v1","phase":"run_finished",...,"status":"completed","summary":"...","api_calls":5,"duration_seconds":10.5,"tokens":{...},"cost_usd":0.01,"tool_trace":[...],"files_written":[],"files_read":[],"error":null,"ended_at":"..."}
```

---

## 4. 真实 Smoke Test 证据

使用真实 `_write_journal_record` 函数（venv Python）生成了包含 4 种场景的 journal：

```
Journal: ~/.hermes/delegations/ddcff28e-...jsonl
Lines: 8 (4 started + 4 terminal)
  - Single task (toolu_smoke_001, task_index=0)
  - Batch task [0] (toolu_smoke_002)
  - Batch task [1] (toolu_smoke_002)
  - Nested task (toolu_smoke_003, with parent_delegate_task_id/run_id/root_task_id)
```

全部 4 对均有 started + finished 记录。✅

---

## 5. 正式投影统计

从真实 journal 构建：

```
Delegation projection: 18 records
  Task: 4
  Run: 4
  DomainEventEnvelope: 8 (run_started + run_finished per pair)
  TaskRelation: 1 (nested → parent)
  RunRelation: 1 (delegated)
  MappingError: 0
  UnsupportedRecord: 0
```

- byte-identical rebuild ✅
- started-only → status=running, outcome=null ✅（测试验证）
- Phase 1 投影：747 records, SHA `508b3c7071612ad3...`, 14/14 acceptance ✅（无回归）

---

## 6. 测试结果

| 套件 | 结果 |
|------|------|
| 226 projection tests (.hermes) | ✅ |
| 135 delegate tests (hermes-agent) | ✅ |
| Phase 1 acceptance (14/14) | ✅ |
| CLI wrapper tests (4 tests) | ✅ |
| py_compile (3 scripts) | ✅ |
| git diff --check (both repos) | ✅ |
| byte-identical rebuild | ✅ |

---

## 7. 设计和实现限制

| 限制 | 说明 |
|------|------|
| 流式事件不支持 | `subagent.thinking`/`subagent.tool`/`subagent.progress` 不在 Phase 2 范围 |
| crashed 判定推迟 | started-only → `running`；`crashed` 需未来 finalize journal 记录 |
| CLI 模式 session_id | 无 Gateway SessionDB 时 `subagent_session_id` 不可用 → journal 写入跳过 |
| 非标准 provider tool_call_id | tool_call_id 为 None 时 journal 跳过 + MappingError |
| Parent run_id 不可得 | 无 `parent_delegate_run_id` → 不生成 RunRelation |

---

## 8. Phase 3 前置条件

1. ✅ Phase 1 Pipeline 投影稳定（747 records, SHA `508b3c70...`）
2. ✅ Phase 2 Delegate 投影稳定（18 records, 0 MappingError）
3. ✅ 所有测试通过（361 total）
4. ✅ Journal 双阶段持久化在生产代码中
5. ⬜ Kanban `tasks`/`task_runs`/`task_events` SQLite schema 审计完成
6. ⬜ Kanban Swarm 拓扑映射设计完成

---

## 9. 文件清单

### Phase 2 新增/修改

**.hermes：**
- `scripts/task-run-projection.py` — +513 行
- `scripts/task-run-projection-build.py` — +61 行
- `tests/test_task_run_projection.py` — +271 行
- `tests/test_task_run_projection_build.py` — +102 行
- `docs/architecture/delegate-task-projection-phase2.md` — 设计文档

**hermes-agent：**
- `tools/delegate_tool.py` — +268 行
- `run_agent.py` — +6 行
- `agent/tool_executor.py` — +2 行
- `agent/agent_runtime_helpers.py` — +2 行
