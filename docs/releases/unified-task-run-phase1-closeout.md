# Unified Task/Run Contract — Phase 1 Closeout

> 日期：2026-06-10
> 状态：**Phase 1D review 修订完成，等待复审**

---

## 1. Phase 1 各阶段完成内容

### Phase 1A：数据模型与纯映射函数

**文件：** `scripts/task-run-projection.py`（1269 行）

**内容：**
- 14 个 @dataclass 统一模型定义
- 3 个确定性 ID 生成函数（SHA-256 派生，禁止随机 UUID/ULID）
- 5 个纯映射函数（map_task_card, map_ledger_record, map_gate_record, map_outbox_record, map_events_jsonl_record）
- 1 个共享生命周期归一化函数（_normalize_lifecycle）
- 去重匹配键函数（ledger_lifecycle_key, _events_jsonl_lifecycle_key）

### Phase 1B：Shadow Projection 构建器

**提交：** `eeb19fcb2` — "Complete Phase 1B shadow projection contract"

**文件：** `scripts/task-run-projection-build.py`（454 行）+ 测试（768 行）

### Phase 1C：端到端验收

**提交：** `a85e8a1df` — "Complete Phase 1C projection acceptance"

**文件：** `scripts/task-run-projection-acceptance.py`（211 行）+ 测试（112 行）

### Phase 1D：正式投影、审计、Schema 冻结、Review 修订

**本次变更：**
- `.gitignore`：纳入 Phase 1A 核心文件
- `scripts/task-run-projection.py`：修复 lifecycle run_id/related_run_id 混淆、添加 phase 白名单
- `tests/test_task_run_projection.py`：更新为真实 ledger 结构 fixtures，添加 12 个 mapper/生命周期回归测试
- `tests/test_task_run_projection_build.py`：新增 8 个调用 `build_projection()` 的 Builder 级去重集成测试
- `docs/architecture/pipeline-event-schema-phase1.md`：冻结（修订版）
- `docs/releases/unified-task-run-phase1-closeout.md`：本 closeout（修订版）

---

## 2. Phase 1D Review 发现并修复的真实问题

### Bug 1：lifecycle_event 的 run_id 被错误当作执行 Run（严重）

**根因：** `run_ledger.py` 的 `append_lifecycle_event()` 产出的 `lifecycle_event` 中：
- `run_id` = lifecycle 事件自身的 ID（如 `life_staam_phase1c_..._778263`）
- `related_run_id` = 真实关联的执行 Run ID（如 `run_staam_phase1c_..._087177`）

修复前的 `_normalize_lifecycle` 将顶层 `run_id`（lifecycle ID）当作执行 Run 使用，导致：
- `gate_checked`、`revision_created` 等事件去重失败（ledger 和 events.jsonl 的 run_id 维度不匹配）
- `revision_dispatched` 错误关联 lifecycle ID 而非真实执行 Run
- 投影中出现 4 条重复 lifecycle 事件

**修复：**
- `_normalize_lifecycle` 接受显式 `execution_run_id` 参数，由调用方根据来源正确提取
- `map_ledger_record` lifecycle_event 分支：使用 `related_run_id`
- `map_events_jsonl_record`：使用顶层 `run_id`
- `ledger_lifecycle_key`：使用 `related_run_id` 参与去重匹配

### Bug 2：未知 lifecycle phase 静默扩展统一事件词汇表（中等）

**根因：** 修复前的实现将任意 `lifecycle_event` phase 动态转换为 `pipeline.{phase}`，无白名单控制。

**修复：**
- 定义 `_SUPPORTED_LIFECYCLE_PHASES` 白名单（12 个 phase）
- 不在白名单中的 phase → `UnsupportedRecord`
- 不允许未知 phase 静默扩展统一事件词汇表

### Bug 3：Phase 1A 核心文件未被 .gitignore 追踪（阻塞）

**根因：** `.gitignore` 使用默认拒绝 + 白名单策略，Phase 1A 的 `scripts/task-run-projection.py` 和 `tests/test_task_run_projection.py` 未列入白名单。

**修复：** 将 Phase 1A/1B/1C 全部 6 个文件加入 `.gitignore` 白名单。

---

## 3. 真实验收根 Task ID

```
staam_phase1c_20260610_084511
```

---

## 4. 正式投影（修订后）

### 路径

```
~/.hermes/projections/task-card-pipeline/staam/events.jsonl
```

### 统计

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 总记录数 | 751 | **747** |
| SHA-256 | `1bae7db4...` | `508b3c7071612ad3c3b1dd8c231087adf7feb4d54a8eb43a8573b3f131f404dd` |
| DomainEventEnvelope | 475 | **471** |
| gate_checked 事件 | 5（含 2 条重复） | **3**（无重复） |
| revision_dispatched | 2（含 1 条重复） | **1**（无重复） |
| revision_created | 2（含 1 条重复） | **1**（无重复） |

### 投影类型分布（修订后）

| projection_type | 数量 |
|-----------------|------|
| Artifact | 10 |
| DomainEventEnvelope | 471 |
| Evidence | 7 |
| ProcessMetadata | 30 |
| ReviewDecision | 2 |
| Run | 174 |
| RunExecutionRef | 30 |
| Task | 7 |
| TaskRelation | 1 |
| TaskSpec | 7 |
| UnsupportedRecord | 8 |

---

## 5. UnsupportedRecord 审计（修订后）

| 指标 | 值 |
|------|-----|
| 总数 | 8 |
| 来源 | ledger.jsonl（全部） |
| 事件类型 | `run_queued`（全部） |
| 涉及 task | `s2`（全部） |
| 分类 | **预期不支持**：`run_queued` 不在 Phase 1 支持的事件类型列表中 |

无数据质量问题。无投影器 Bug。

---

## 6. 测试和验收结果（修订后）

### 单元测试

```
185 passed
```

**`tests/test_task_run_projection.py`** — 新增 12 个 mapper/生命周期回归测试：
- gate_checked/revision_created/revision_dispatched/gate_checked_rev 四条事件去重
- lifecycle run_id 隔离（两测试）
- lifecycle_run_id 和 related_run_id 在 payload 中正确保留
- 已知 phase 通过 / 未知 phase → UnsupportedRecord / 空 phase → MappingError

**`tests/test_task_run_projection_build.py`** — 新增 8 个 Builder 级集成测试（调用 `build_projection()`）：
- gate_checked ledger + events.jsonl → 最终只输出一条
- revision_created ledger + events.jsonl → 最终只输出一条
- revision_dispatched ledger + events.jsonl → 最终只输出一条
- revision_dispatched 统一 run_id 使用 related_run_id
- lifecycle 自身 ID 不会泄露为统一执行 Run ID
- gate_checked / revision_created 的 run_id 为 None、event_scope 为 task
- 全部 lifecycle 事件类型不超过 1 条

### 端到端验收

全部 14 项检查通过：
- no_mapping_errors (0) ✅
- no_invented_runs (174/174) ✅
- no_revision_dispatch_run_relation ✅
- events_traceable (471/471) ✅
- byte_identical_rebuild ✅
- 完整生命周期覆盖 9/9 ✅

### 额外验证

- ✅ 4 条真实 Phase 1C 生命周期事件不再重复（gate_checked: 5→3, revision_dispatched: 2→1, revision_created: 2→1）
- ✅ revision_dispatched 关联真实 related_run_id（`run_staam_phase1c_..._087177`）
- ✅ Phase 1A 文件已进入 git 追踪状态
- ✅ py_compile 三个脚本全部通过
- ✅ git diff --check 无空白警告

---

## 7. Phase 1 明确未做的事项

| 未做事项 | 原因 |
|----------|------|
| delegate_task 接入 | Phase 2 |
| Kanban 接入 | Phase 3 |
| Gateway/Desktop 接入 | Phase 5 |
| Event Bus / daemon / 自动刷新 | 不在 Phase 1 范围 |
| 修改 Pipeline 原始数据 | 硬性约束 |
| 读取 tasks/index.jsonl | 永久排除 |
| 虚构 Run/RunRelation | 合同禁止 |
| gate approved = Task accepted | 合同禁止，Phase 1 终点为 needs_review |

---

## 8. Phase 2 进入条件

1. ✅ Phase 1 所有测试通过（185 tests）
2. ✅ Phase 1 端到端验收通过（14/14 checks）
3. ✅ 正式投影可重建（byte-identical rebuild）
4. ✅ Pipeline Event Schema 已冻结
5. ✅ Phase 1 closeout 文档已完成
6. ✅ lifecycle 去重 Bug 已修复
7. ✅ Phase 1A 文件已纳入 git 追踪

---

## 9. 文件清单

### 本次变更文件

| 文件 | 变更 |
|------|------|
| `.gitignore` | 添加 Phase 1A/1B/1C 六个文件的追踪白名单 |
| `scripts/task-run-projection.py` | Bug 修复：lifecycle run_id/related_run_id、phase 白名单 |
| `tests/test_task_run_projection.py` | 更新 fixtures + 新增 12 个 mapper/生命周期回归测试 |
| `tests/test_task_run_projection_build.py` | 新增 8 个真实结构 Builder 去重集成测试 |
| `docs/architecture/pipeline-event-schema-phase1.md` | 修订：双 ID 约束、白名单、去重规则 |
| `docs/releases/unified-task-run-phase1-closeout.md` | 修订：记录真实 Bug 发现和修复 |

### 派生数据（不入 git）

| 路径 | 说明 |
|------|------|
| `~/.hermes/projections/task-card-pipeline/staam/events.jsonl` | 747 条记录，SHA-256: `508b3c7071612ad3c3b1dd8c231087adf7feb4d54a8eb43a8573b3f131f404dd` |
