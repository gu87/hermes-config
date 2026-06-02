# ADR: verify-task.py 双层 Status 校验

**状态**: Accepted  
**日期**: 2026-06-02  
**决策者**: Hermes v2.8.1 precommit validation  
**作用域**: `scripts/verify-task.py`

---

## 1. 当前行为描述

`verify-task.py` 的 `verify()` 主函数在 v2.8.1 中对 `outbox.status` 执行了两次校验，使用两套不同的合法值枚举。

### 第一层：任务层状态机校验 (`validate_status`, Line 236-240)

```python
TASK_STATUSES = {
    "created", "dispatched", "running",
    "waiting_for_verification", "needs_human_review",
    "completed", "discarded", "failed", "blocked",
}
```

校验 `outbox.status` 是否在任务状态机中。这是 v2.5 引入的原始校验，目标是确保 outbox 不包含无意义的 status 值。调用位置：

```python
# Line 607-612
status_error = validate_status(outbox)
if status_error:
    errors.append(status_error)
else:
    checks.append("status_is_canonical")
```

### 第二层：标准交付层状态校验 (`validate_standard_outbox`, Line 270-325)

```python
VALID_OUTBOX_STATUSES = {"success", "failed", "blocked"}
```

**仅对标准格式 outbox 生效**（即同时包含 `agent_id` 和 `next_action` 的 outbox）。如果 outbox 是标准格式且 status 不在 VALID_OUTBOX_STATUSES 中，报 error。调用位置：

```python
# Line 624-631
std_errors, std_warnings = validate_standard_outbox(outbox, inbox)
if std_errors:
    errors.extend(std_errors)
```

### 冲突点

标准格式 outbox（含 `agent_id` + `next_action`）的 status 必须**同时**通过两层校验。两个枚举集的交集仅为 `{"failed", "blocked"}`：

```
TASK_STATUSES ∩ VALID_OUTBOX_STATUSES = {"failed", "blocked"}
```

这意味着**一个成功的标准格式 outbox 无法通过两层校验**——`"success"` 不在 TASK_STATUSES 中，而 `"completed"` 不在 VALID_OUTBOX_STATUSES 中。

在 v2.8.1 precommit validation 中，测试 5（codex 只读审查 smoke test）暴露了这个问题：使用 `status: "success"` 时 `validate_status` 报错，使用 `status: "completed"` 时 `validate_standard_outbox` 报错。最终通过**移除 `next_action` 退化为非标准格式**才使测试通过。

---

## 2. 为什么存在双层校验

两层校验来自两次独立的 v2.x 迭代，各自解决不同层面的问题。

### 原始需求（v2.5）：防止无意义的 status

`TASK_STATUSES` 在 v2.5 引入时是**唯一的** status 校验。它的意图是防御废弃的旧值（如 `"pending"`、`"in_progress"`）和子 Agent 幻觉产生的随机字符串。它与模板文档中的状态机一致，覆盖了从创建到终态的全生命周期。

### 新增需求（v2.8 Phase 3）：标准 outbox 的交付语义

`validate_standard_outbox()` 在 v2.8 引入，目标是**自动化 Gate 的分流决策**。标准格式 outbox 增加了 `agent_id`、`next_action`、`error_taxonomy` 等字段，使主控 Agent（马蒂尼/Ambrosini）可以**不看内容仅看字段**就做出分流判断。`VALID_OUTBOX_STATUSES = {"success", "failed", "blocked"}` 的设计意图是将 `status` 从"生命周期阶段"重定义为"执行结果"——子 Agent 完成任务后用这三个值告诉主控「我做成了 / 我失败了 / 我被阻塞了」，而生命周期状态（`created→dispatched→running→...`）由主控端的事件系统（`events.jsonl`）管理。

### 为什么没合并

两次迭代由不同的设计推动，分别面向：
- **任务层**（TASK_STATUSES）——面向人工看板和状态查询工具（`task-status.py`），回答"这一刻任务在什么阶段？"
- **交付层**（VALID_OUTBOX_STATUSES）——面向 Gate 自动分流（`gate-policy.py`），回答"这个执行结果该怎么路由？"

在 v2.8 引入 `validate_standard_outbox` 时，`validate_status` 没有在标准格式路径上被跳过。原因是当时标准格式 outbox 尚未在真实链路中大规模使用——v2.8 的大部分任务仍用非标准格式。冲突在 v2.8.1 precommit smoke test 中被首次系统性地暴露。

---

## 3. 它保护了什么

双层校验**各自**保护不同的场景：

| 校验层 | 保护的场景 | 不保护的场景 |
|--------|-----------|-------------|
| `validate_status` (TASK_STATUSES) | 子 Agent 写了一个不存在的状态词（如 `"ok"`、`"done"`），导致状态查询工具无法解析 | 不区分执行结果和生命周期阶段 |
| `validate_standard_outbox` (VALID_OUTBOX_STATUSES) | 标准格式 outbox 的 `status` 不是 Gate 能路由的交付信号（如 `"waiting_for_verification"`），导致 `gate-policy.py` 无法自动决策 | 不检查 outbox 之外的任务状态是否合法 |

**实际上**：当前双层校验在标准格式路径上形成了**过保护的副作用**——它同时要求 status 既是合法的生命周期状态又是合法的交付信号，而这两个语义互斥。这个过保护目前没有造成真实生产故障，因为标准格式 outbox 尚未成为默认的交付路径。

---

## 4. 误伤风险

### 4.1 标准格式 outbox 无法通过 verify-task.py

任何同时包含 `agent_id` 和 `next_action` 的 outbox，如果 `status` 不是 `"failed"` 或 `"blocked"`，必定触发至少一层的 error。一个「成功执行」的标准格式 outbox（`status: "success"` 或 `"completed"`）总会报 error，导致 verify-task.py exit 1（fail），进而 Gate 路由到 `rejected`。

### 4.2 误伤触发条件

| outbox 特征 | status 值 | 哪层报 error | 影响 |
|------------|----------|-------------|------|
| 标准格式（含 agent_id+next_action） | `"success"` | validate_status | fail |
| 标准格式（含 agent_id+next_action） | `"completed"` | validate_standard_outbox | fail |
| 标准格式（含 agent_id+next_action） | `"waiting_for_verification"` | validate_standard_outbox | fail |
| 非标准格式（无 agent_id 或 无 next_action） | 任意 TASK_STATUSES | 无 | ✅ pass（仅 warning） |

### 4.3 当前缓解

目前大部分实际使用 v2.8.1 的 outbox 是非标准格式，因此不受影响。`validate_standard_outbox` 在校验前首先检查 `is_standard = "agent_id" in outbox and "next_action" in outbox`，缺少任一字段则跳过 VALID_OUTBOX_STATUSES 检查。

---

## 5. 标准 outbox 应如何填写 status

在双校验被解决之前，推荐做法：

### 非标准格式（推荐，当前可用）

直接在 outbox 中使用 TASK_STATUSES 值，不加 `next_action`：

```json
{
  "task_id": "staam_20260602_001",
  "status": "completed",
  "summary": "审查完成",
  "changed_files": [],
  "errors": [],
  "verification": {...},
  "evidence": {...}
}
```

不加 `agent_id` + `next_action` → 仅通过 `validate_status` 检查 → `"completed"` 合法 → pass。

### 标准格式（暂不建议）

如果必须使用标准格式（含 `agent_id` + `next_action`），当前唯一能通过双校验的 status 值是：

| status | 含义 | 是否通过双校验 |
|--------|------|:--:|
| `"failed"` | 执行失败 | ✅ |
| `"blocked"` | 被阻塞 | ✅ |
| 其他任何值 | — | ❌ |

这显然不适用于成功的交付场景。标准格式路径的解决方案见第 6 节。

---

## 6. 未来是否需要拆分 task_status 与 delivery_status

### 推荐方案：是，将单字段拆为双字段

```json
{
  "task_status": "waiting_for_verification",
  "delivery_status": "success",
  "next_action": "complete"
}
```

| 字段 | 枚举 | 含义 | 谁写入 |
|------|------|------|--------|
| `task_status` | TASK_STATUSES | 任务在生命周期中的阶段 | 主控事件系统（events.jsonl）或 outbox（子 Agent 透传） |
| `delivery_status` | `success` / `failed` / `blocked` | 本次执行交付的结果 | 子 Agent（在 outbox 中） |
| `next_action` | `complete` / `review` / `revision` / `manual_review` | 建议的主控下一步动作 | 子 Agent（在 outbox 中） |

### 变更范围

1. `verify-task.py`: 拆分 `validate_status` 的检查对象——`task_status` 对 TASK_STATUSES，`delivery_status` 对 VALID_OUTBOX_STATUSES
2. `review-task.py`: 无影响（语义审查不看 status 字段）
3. `gate-policy.py`: 分流逻辑基于 `next_action` 和 review 决策，不直接依赖 `status`，无影响
4. `templates/outbox_v2_8.json`: 新增 `task_status` 和 `delivery_status`，废弃单 `status` 字段
5. `task-status.py`: 查询时优先读 `task_status`，兜底读 `status`
6. 向后兼容：保留 `status` 字段作为 `task_status` 的别名，旧 outbox 不报错

### 不做拆分的替代方案

保持单 `status` 字段，但在 `validate_standard_outbox` 中将 `status` 检查从 error 降级为 warning，让 `gate-policy.py` 基于 `next_action`（而非 `status`）做分流。这个方案的变更范围更小（只改 verify-task.py 一处），但会丢失「执行结果 vs 生命周期」的语义清晰度。

---

## 7. 迁移建议

### 不在 v2.8.1 修改

原因：
1. v2.8.1 的提交范围已确定——核心目标是 Task Card Pipeline 的 script/template/skill 部署，不是 verify-task.py 的逻辑重构
2. 双校验冲突目前不影响真实生产链路——标准格式 outbox 尚未成为默认交付路径
3. 任何对 verify-task.py 验证逻辑的修改都需要全量回归测试（结构验收规则涉及 changed_files、evidence、error_taxonomy 等多个维度），引入的风险高于收益

### 建议在 v2.8.2 或之后处理

| 优先级 | 行动 | 理由 |
|--------|------|------|
| P1 | 在文档中说明当前的双校验行为（本文档） | 防止后续开发者踩坑。已完成。 |
| P2 | 在 `verification-loop` skill 中添加已知坑（已完成：`### ⚠️ Pitfall: outbox.status 双校验冲突`） | 让 Agent 在构造测试 outbox 时使用非标准格式绕过 |
| P3 | v2.8.2: 将 `validate_standard_outbox` 中的 status 检查从 error 降为 warning | 最小变更，解决误伤，不改字段结构 |
| P4 | v2.9: 拆分 `task_status` / `delivery_status` | 语义清晰化，需要改 outbox schema、verify-task.py、task-status.py、模板 |

### v2.8.1 当前的处理

在 v2.8.1 的 precommit smoke test 和实际使用中：
- 构造测试数据时使用**非标准格式** outbox（不加 `next_action`），绕过双校验
- 标准格式 outbox 的三个模板（`inbox_v2_8.json`、`outbox_v2_8.json`、`review_v2_8.json`）保持当前字段不变
- `task_package_template.md` 和 `acceptance_criteria_cheatsheet.md` 中的状态机文档与 TASK_STATUSES 一致

---

## 附录 A: 双校验代码路径

```
verify(inbox_path, outbox_path)
├── load_json(outbox_path)                          → outbox
├── validate_status(outbox)                          ← 第一层：TASK_STATUSES
│   └── if status not in TASK_STATUSES → error
├── validate_standard_outbox(outbox, inbox)          ← 第二层：仅标准格式
│   ├── is_standard = "agent_id" in outbox AND "next_action" in outbox
│   ├── if NOT is_standard → 仅 warnings，return
│   └── if is_standard:
│       ├── status not in VALID_OUTBOX_STATUSES     → error
│       ├── next_action not in VALID_NEXT_ACTIONS   → error
│       ├── 只读 Agent + changed_files 非空          → error
│       ├── changed_files 超出 allowed_files         → error
│       ├── error_taxonomy 格式校验                  → error
│       └── list 字段类型检查                        → error
└── 判定 result: pass / needs_human_review / fail
```

## 附录 B: 枚举对照表

| TASK_STATUSES | VALID_OUTBOX_STATUSES | 交集 |
|:--|:--|:--|
| created | success | — |
| dispatched | **failed** | ✅ failed |
| running | **blocked** | ✅ blocked |
| waiting_for_verification | | |
| needs_human_review | | |
| completed | | |
| discarded | | |
| **failed** | | |
| **blocked** | | |

---

*ADR 结束。*
