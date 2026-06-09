# Phase 12B — Precommit Risk Scan

审查范围：`hermes_cli/kanban.py` 修改 + `hermes_cli/kanban_feedback.py` 新增 + `executors/` IPC 协议 + `tests/hermes_cli/test_kanban_cli.py` 修改。

Commit branch：`codex/merge-8787-capabilities-into-9119`
Base commit：`6e9a1e35d`

---

## 变更摘要

| 文件 | 状态 | 行数变化 |
|------|------|----------|
| `hermes_cli/kanban.py` | 已修改 | +36 |
| `tests/hermes_cli/test_kanban_cli.py` | 已修改 | +35 |
| `hermes_cli/kanban_feedback.py` | 未跟踪 (??) | 348 行新增 |
| `executors/` (整个目录) | 未跟踪 (??) | ~25 文件, ~300K |
| 4 个 PNG 图片文件 | 未跟踪 (??) | — |

---

## P0 — 必须修复后方可合并

### P0-1: `kanban.py` 导入 `kanban_feedback` 但该文件未跟踪

**风险描述：** `kanban.py` 第 27 行添加了 `from hermes_cli import kanban_feedback as kfb`。如果 merge 时不将 `kanban_feedback.py` 纳入版本控制，任何使用 `kanban` 模块的入口（CLI / gateway）都会在导入时立即抛出 `ModuleNotFoundError`。

**位置：** `hermes_cli/kanban.py:27`

**建议：** 必须 `git add hermes_cli/kanban_feedback.py` 再提交。如果该文件不应合入，则需移除 import 及所有 `kfb.*` 调用。

---

### P0-2: `kanban_feedback.py` 依赖 `kanban_db._append_event`（私有 API）

**风险描述：** `kanban_feedback.py:298` 调用了 `kb._append_event(...)`。该函数前置下划线，属于包内私有约定。若后续重构 `_append_event` 的签名（如修改参数顺序），`kanban_feedback.py` 的 `TypeError` fallback（第 299 行）虽能兜底写入事件，但会丢失 `run_id` 字段。

**位置：** `hermes_cli/kanban_feedback.py:297-307`

**建议：** 将 `_append_event` 的公共接口提升为非私有函数（如 `append_event`），或在 `kanban_db.py` 中显式导出公共包装器。

---

### P0-3: `executors/` 整个目录未跟踪 — 不应意外进入本次提交

**风险描述：** `git status` 显示 `executors/` 为 `??`，含 ~25 个文件、约 300KB 代码。这些是 Desktop IPC 基础设施，不属于本次 kanban CLI 改动范围。

**位置：** `executors/`

**建议：** 提交时只 stage 确定的三文件：
- `hermes_cli/kanban.py`
- `tests/hermes_cli/test_kanban_cli.py`
- `hermes_cli/kanban_feedback.py`

使用 `git add hermes_cli/kanban.py hermes_cli/kanban_feedback.py tests/hermes_cli/test_kanban_cli.py`。

---

### P0-4: 4 个 PNG 图片文件不应进入本次提交

**风险描述：** `git status` 显示 4 个 untracked PNG（`hermes-dashboard-chat.png` 等）。这些是演示素材，与代码变更无关。

**建议：** 确认 `.gitignore` 中是否需要添加 `*.png` 或具体条目。提交时不 stage 这些文件。

---

## P1 — 应修复或确认后合入

### P1-1: `review_result` / `qa_result` event payload schema 不统一

**风险描述：** payload 字段随 executor 路径变化：

| 路径 | payload keys |
|------|-------------|
| opencode 成功 | `executor`, `exit_code`, `raw_output`, `stderr` |
| opencode 超时 | `executor`, `error: "timeout"` |
| opencode 异常 | `executor`, `error: <msg>` |
| stub fallback | `executor`, `findings`, `note` (review) |
| stub fallback | `executor`, `test_passed`, `test_failed`, `test_skipped`, `note` (QA) |

消费者必须处理多种 payload 形状。当前没有字段用于区分路径，只能通过 key 存在性推断。

**位置：** `hermes_cli/kanban_feedback.py:197-278`

**建议：** 统一添加 `"executor_status": "completed" | "timeout" | "error" | "stub"` 字段。用结构化字段取代自由文本 note。

---

### P1-2: `_cmd_dispatch` 中 diff event 的语义和时机

**风险描述：** `kanban.py:1721-1723` 在 dispatch spawn 后立即调用 `emit_diff_event()`，此时 worker 尚未开始执行。因此 diff 捕获的是 spawn 时刻的 HEAD 快照，而非 worker 完成后的变更。如果消费者期待的是 worker 执行结果，语义不符。

**位置：** `hermes_cli/kanban.py:1721-1723`

**建议：** 确认这个语义（"基线 diff"）是预期行为。如果需要 worker 完成后的 diff，应在 task outcome 回调中触发。

---

### P1-3: Preload 接口签名与 Python handler 不匹配

**风险描述：** `executors/ipc.py` 文档显示：

```python
async def triggerReview(self, main_run_id: str) -> dict: ...
```

但 `executors/review_handler.py` 实际 handler：

```python
async def trigger_review(
    main_run_id: str,
    diff_patch: str,
    changed_files: List[str],
    task_goal: str,
    ...) -> ReviewReport: ...
```

**位置：** `executors/ipc.py:184` vs `executors/review_handler.py:49`

**建议：** 确认 Electron 侧的调用链。若 preload 的 `triggerReview` 通过 `TriggerReviewRequest` 完整对象调用，则不匹配无害；否则需在 handler 侧添加合理默认值。

---

### P1-4: 两套独立的 Review/QA 实现

**风险描述：** Kanban CLI 和 Desktop IPC 各有一套实现：

| 维度 | `kanban_feedback.py` | `review_handler.py` |
|------|---------------------|---------------------|
| 同步/异步 | `subprocess.run` (同步) | `asyncio.create_subprocess_exec` (异步) |
| prompt 构建 | `_build_review_prompt` | `ReviewAgent.build_prompt` |
| stub 逻辑 | `_stub_review_findings` | `stub_review_report` |

核心 opencode 命令和超时一致，但两套代码独立演化，修复需同步修改两处。

**位置：** `hermes_cli/kanban_feedback.py` vs `executors/review_handler.py`

**建议：** 短期确认两套 prompt 都包含 `"Do NOT modify any code."`（已确认）。中长期考虑将 `kanban_feedback.py` 的 review/QA 委派给 `executors/review_handler.py`。

---

## P2 — 关注/可暂缓

### P2-1: 缺少 Electron Desktop 端到端测试

**风险描述：** `desktop/` 仅含 `sessions.json`，无 preload 或 main 脚本。`bridge_cli.py` 是 CLI 替代路径而非 Electron IPC 路径。无法验证通道名绑定、contextBridge 映射、事件流路由是否正常。

**位置：** `desktop/`, `executors/bridge_cli.py`

**建议：** 在在本次提交中添加注释说明 Desktop IPC 集成尚未落地。为 `executors/review_handler.py` 添加单元测试覆盖三条路径（stub / opencode / error）。

---

### P2-2: QA executor 仅靠 prompt 约束只读行为

**风险描述：** prompt 末尾包含 `"Do NOT modify any code."`，但 opencode 作为通用 AI agent 仍可执行写入操作。无沙箱或只读挂载强制防护。

**位置：** `hermes_cli/kanban_feedback.py:335`

**建议：** 为 opencode review/QA 添加 `--readonly` 标志（如果支持）或在 worktree 上创建快照。

---

### P2-3: `kanban_feedback` 未在 `hermes_cli/__init__.py` 中显式导出

**风险描述：** `kanban.py` 通过 `from hermes_cli import kanban_feedback` 直接导入，绕过包导出检查。Python 允许这样做，但 lint 规则可能触发警告。

**位置：** `hermes_cli/__init__.py`, `hermes_cli/kanban.py:27`

**建议：** 将 `"kanban_feedback"` 添加到 `hermes_cli/__init__.py` 的 `__all__` 中。

---

### P2-4: IPC 通道名与 Preload 方法名映射待确认

**风险描述：** Electron side 的 preload 脚本不在本仓库中。如果 preload 映射错误（如用错通道名或参数），review/QA IPC 将静默失败。

**位置：** `executors/ipc.py:184-185, 204-205`

**建议：** 在 `ipc.py` 中添加注释说明预期的 preload 映射关系，例如 `triggerReview()` → `ipcRenderer.invoke('review:trigger', request)`。

---

## 分级汇总

| 级别 | 数量 | 关键要点 |
|------|------|----------|
| **P0** | 4 | `kanban_feedback.py` 必须 stage；依赖私有 API；`executors/` 和 PNG 不要误提交 |
| **P1** | 4 | event schema 不统一；diff 语义需确认；preload/handler 签名差异；两套重复实现 |
| **P2** | 4 | 缺少 Electron 端到端测试；QA 仅靠 prompt 约束只读；未显式导出；通道名映射待确认 |

---

## 提交建议

```bash
# 仅 stage Phase 12B 的三文件
git add hermes_cli/kanban.py hermes_cli/kanban_feedback.py tests/hermes_cli/test_kanban_cli.py

# 确认没有多余文件
git status

# 提交
git commit -m "feat(kanban): add review/qa CLI subcommands and feedback events

- Add kanban review <task_id> and kanban qa <task_id> subcommands
- Emit diff events on dispatch spawn
- Emit structured review_result and qa_result events
- Tests cover diff event schema and review/qa result recording

See docs/review/phase-12b-precommit-risk-scan.md for P1 items
that require post-merge follow-up."
```

---

*扫描时间：2026-06-04*
*扫描范围：`hermes_cli/kanban.py`, `hermes_cli/kanban_feedback.py`, `executors/ipc.py`, `executors/review_handler.py`, `tests/hermes_cli/test_kanban_cli.py`*
*未自动修改代码或添加未跟踪文件。*
