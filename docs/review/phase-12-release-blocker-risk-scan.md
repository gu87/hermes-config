# Phase 12 发布前风险扫描

> 基于 Phase 12（Review/QA + IPC + Diff + Continue/Retry）改动的发布前风险排查。

扫描日期：2026-06-04
扫描范围：
- `executors/review_handler.py` (420 行)
- `executors/review_agent.py` (443 行)
- `executors/ipc.py` (209 行)

---

## 检查项总览

| # | 检查项 | 结论 |
|---|--------|------|
| 1 | log/diff RunEvent 是否会丢失 | ⚠️ 静默丢失 |
| 2 | changed files 聚合是否可靠 | ⚠️ 无去重 + 无路径提取 |
| 3 | DiffTab 是否能处理大 diff | ✅ 有 200KB cap |
| 4 | Continue / Retry 是否会覆盖旧 run | ✅ 创建新 run_id |
| 5 | Review / QA 是否会自动改代码 | ✅ `--pure` 只读模式 |
| 6 | opencode adapter 是否可能卡住 | ⚠️ 超时后不清理子进程 |
| 7 | IPC 是否有路径安全问题 | ⚠️ 默认 "."，低风险 |
| 8 | child_process 是否正确释放 | ⚠️ 超时不 kill |
| 9 | worktree 是否可能被误删 | 🔴 同 Phase 6 P0，未修复 |
| 10 | Electron window.hermesAPI 缺失 | ✅ 有完整接口定义 |

---

## P1：应该修复（3 项）

### P1-1：`emit_diff_event` 静默丢失 diff

**文件**：`review_handler.py` 第 270-272 行

```python
except Exception as e:
    logger.debug("emit_diff_event failed: %s", e)
    return None  # ← 静默丢失
```

所有异常（git 失败、超时、非 git 目录）都返回 `None`。调用方无法区分"无变更"和"读取失败"。

**建议**：返回含 error 字段的结构，或至少 `logger.error` 而非 `logger.debug`。

### P1-2：Timeout 后不清理子进程

**文件**：`review_handler.py` 第 316 行 + `_launch_opencode`（第 294-319 行）+ `emit_diff_event`（第 226-233 行）

```python
except asyncio.TimeoutError:
    raise Exception(f"opencode timed out after {OPencode_TIMEOUT}s")
    # proc 没有 terminate/kill！
```

`asyncio.wait_for` 抛出后子进程仍在运行。多个超时子进程堆积可能导致资源耗尽。

**建议**：每个超时处理加 try/finally 清理：

```python
try:
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
except asyncio.TimeoutError:
    proc.terminate()
    await asyncio.wait_for(proc.wait(), timeout=5.0)
    raise
```

### P1-3：changed files 只计数不提取路径

**文件**：`review_handler.py` 第 243-247 行

```python
files_changed = len([...])  # 只计数
# 不提取文件名、状态、增删行数
```

`GetChangedFilesResponse.files` 需要 `{path, status, additions, deletions, absolute_path}` 结构，但当前只计数。UI 收到的 changed files 列表可能为空或缺失路径。

**建议**：从 `diff --git` 行提取文件路径。

---

## P2：后续修复（2 项）

### P2-1：diff 截断逻辑不一致

`review_agent.py` 第 53 行按行截断（`_MAX_DIFF_LINES = 2000`），`review_handler.py` 第 240 行按字节截断（`200KB`）。字节截断可能切在行中间。

### P2-2：`git diff HEAD` 在空仓库失败

`review_handler.py` 第 224 行：`git diff HEAD` 在首次 commit 前的仓库返回 `fatal: ambiguous argument 'HEAD'`，被 `except Exception` 捕获后返回 `None`。

---

## 遗留：Worktree 路径校验仍未修复 🔴

`worktree.py` `discard()` 的路径安全问题（Phase 6 P0-1）**仍存在**。Review/QA 流程可能在 discard worktree 时被触发。如果 v1.0 包含 worktree 功能，必须在此之前修复。
