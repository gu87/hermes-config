# Phase 6 Worktree Git 风险扫描

> 检查 Desktop v0.4 Worktree 实现中的 Git 安全风险。

扫描日期：2026-06-04
扫描范围：
- `hermes-agent/executors/worktree.py` — WorktreeManager（核心实现）
- `hermes-agent/executors/worktree_cli.py` — CLI 子命令
- `hermes-agent/executors/types.py` — WorktreeStatus + WorktreeAllocation 类型
- `docs/architecture/worktree-parallel-runs.md` — 架构设计文档
- `hermes-agent/tools/delegate_tool.py` — 已有 Hermes Agent 的 worktree 代码（参考）

---

## 风险总览

| # | 风险 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | discard 缺少路径安全校验 | 🔴 高危 | 可能误删用户目录 |
| 2 | short_id 边界条件 | 🔴 高危 | 空 ID 导致路径碰撞 |
| 3 | merge 冲突无法恢复 | 🟡 中危 | worktree 卡死在 FAILED |
| 4 | 纯内存状态管理 | 🟡 中危 | 崩溃后 worktree 成为孤儿 |
| 5 | pre-flight 检查有缩进错误 | 🟡 中危 | 脏仓库可能误通过 |
| 6 | git diff 退路语义偏差 | 🟡 中危 | 文件变更计数不准确 |
| 7 | merge 时 fetch 失败静默继续 | 🟡 中危 | merge 基于过时 HEAD |
| 8 | cleanup_worktree 无脏检查 | 🟢 低危 | merge 后脏 worktree 可能残留 |
| 9 | gitignore 追加空行 | 🟢 低危 | 不影响功能 |
| 10 | 并行安全仅同进程 | 🟢 低危 | 跨进程不保护 |

---

## 风险 1：discard 缺少路径安全校验 🔴 高危

### 位置

`hermes-agent/executors/worktree.py`，`discard()` 方法（第 402-457 行）

### 问题

```python
# Step 1: Remove worktree
r = await _git("worktree", "remove", "--force", str(wt_path), cwd=self._project_root)

# Step 2: Delete branch
r_branch = await _git("branch", "-D", branch, cwd=self._project_root)
```

两处命令**都没有校验 `wt_path` 是否在 project root 的安全范围内**。

### 对比：`delegate_tool.py` 已有保护

```python
if not str(wpath).startswith(str(_get_worktree_base_dir())):
    result["reason"] = "worktree path is not under Hermes managed directory — refusing to delete"
    return result
```

### 触发场景

1. `WorktreeAllocation.worktree_path` 被错误写入
2. 状态恢复时读取了损坏的配置
3. `thread_id` 含特殊字符导致 `_short_id()` 生成意料外的路径

**结果**：`git worktree remove --force /任意/路径` + `git branch -D 任意分支` 可能被无意执行。

### 建议

```python
# 在 wt_path = Path(alloc.worktree_path) 后增加：
if not str(wt_path.resolve()).startswith(str(self._worktrees_dir.resolve())):
    raise ValueError(
        f"Worktree path {wt_path} is not under managed directory "
        f"{self._worktrees_dir}. Refusing to discard."
    )

# git branch -D 也要约束：
if not branch.startswith("hermes/"):
    logger.warning("Refusing to delete non-hermes branch: %s", branch)
    errors.append(f"Branch {branch} does not have hermes/ prefix — skipped")
```

---

## 风险 2：`_short_id` 边界条件 🔴 高危

### 位置

第 109-112 行

```python
@staticmethod
def _short_id(thread_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", thread_id)
    return clean[-8:] if len(clean) >= 8 else clean
```

### 问题

| 输入 | 输出 | 问题 |
|------|------|------|
| `""` | `""` | 分支名 `hermes//1`，双斜杠 |
| `"abc"` | `"abc"` | 分支名 `hermes/abc/1`，较短但可用 |

空 string 最严重：`_branch_name("", 1)` → `"hermes//1"`，git 可能行为异常。

### 建议

```python
clean = re.sub(r"[^a-zA-Z0-9_-]", "", thread_id or "unknown") or "unknown"
```

---

## 风险 3：Merge 冲突后无法恢复 🟡 中危

### 位置

第 372-379 行

```python
if not r_merge.ok:
    alloc.status = WorktreeStatus.FAILED
    alloc.error = f"Merge conflict..."
    return alloc
```

### 问题

merge 冲突后，worktree 设为 FAILED：
- `create()` 不允许从 FAILED 重建（idempotency check 只检查 READY/DIRTY/CREATING）
- 没有从 FAILED 恢复到 DIRTY 的方法
- 用户手动解决冲突后，无法重新触发 merge

### 建议

```python
async def merge(self, thread_id: str) -> WorktreeAllocation:
    alloc = self._allocations.get(thread_id)
    if alloc is None:
        raise ValueError(...)
    # 允许从 FAILED 重试（用户已手动解决冲突）
    if alloc.status == WorktreeStatus.FAILED:
        alloc.status = WorktreeStatus.DIRTY  # 降级重试
    elif alloc.status not in (WorktreeStatus.READY, WorktreeStatus.DIRTY):
        raise ValueError(...)
```

---

## 风险 4：纯内存状态管理 🟡 中危

### 位置

第 90 行

```python
self._allocations: Dict[str, WorktreeAllocation] = {}
```

### 问题

所有分配信息在内存中：
- 进程崩溃 → 所有分配信息丢失
- worktree 文件夹在磁盘上成为孤儿
- 重启后 `create()` 为同一 thread 创建第二个 worktree

### 建议

```python
STATE_FILE = "worktrees_state.json"

def _save_state(self):
    json.dump(
        {tid: asdict(a) for tid, a in self._allocations.items()},
        open(self._worktrees_dir / STATE_FILE, "w")
    )

def _load_state(self):
    path = self._worktrees_dir / STATE_FILE
    if path.exists():
        for tid, d in json.load(open(path)).items():
            self._allocations[tid] = WorktreeAllocation(**d)
```

---

## 风险 5：pre-flight 检查缩进错误 🟡 中危

### 位置

第 141-148 行

```python
if not r.ok:                       # ← 第 139 行
    return f"git status failed: {r.stderr}"
# 以下 4 行与第 139 行的 if 同缩进 —— 这不对！
    dirty = r.stdout.strip().split("\n")
    filtered = [l for l in dirty if ".hermes/" not in l]
    if not filtered:
        return None  # only .hermes/ changes, OK
    dirty_files = filtered[:5]
```

**问题**：第 142-145 行缩进了 4 空格而非 8 空格，导致它们**只在 `r.ok` 为 False 时执行**。意图应该是 `r.ok` 为 True 时过滤 `.hermes/` 变更。这个 bug 导致：
- 有非 `.hermes/` 变更时，`_check_clean_working_tree` 返回 `None`（干净），worktree 在脏仓库上创建
- `git worktree add` 虽然成功，但基于 dirty HEAD 创建

### 建议

在确定有输出后才处理过滤逻辑。

---

## 风险 6：`_count_changed_files` diff 退路语义偏差 🟡 中危

### 位置

第 293-308 行

```python
r = await _git("diff", "--stat", "HEAD", cwd=Path(worktree_path))  # staged + unstaged
if not r.ok or not r.stdout:
    r = await _git("diff", "--stat", cwd=Path(worktree_path))               # 只 unstaged！
```

`git diff --stat HEAD` 失败时退回到 `git diff --stat`（仅 unstaged），计数会偏少。应改为先查 cached（staged）再查 unstaged。

---

## 风险 7：Merge 时 fetch 失败静默继续 🟡 中危

### 位置

第 359-363 行

```python
r_fetch = await _git("fetch", "origin", cwd=self._project_root, timeout=60.0)
if not r_fetch.ok:
    logger.warning("git fetch failed (non-fatal): %s", r_fetch.stderr)
```

`fetch` 失败后 merge 继续。如果 `origin` 有新 commit，本地的 merge commit 推送时会失败。建议区分"无 origin"和"origin 存在但不可达"：

```python
has_origin = await _git("remote", "get-url", "origin", ...)
if r_fetch.ok or not has_origin.ok:  # fetch 成功或没有 origin 都继续
    ...
else:
    logger.warning(...)  # 有 origin 但 fetch 失败，用户需注意
```

---

## 风险 8-10：低风险项 🟢

| # | 风险 | 详细 | 建议 |
|---|------|------|------|
| 8 | `_cleanup_worktree` 无 `--force` | merge 后若 worktree 还有残留变更，移除会失败（保留 worktree） | 当前行为是故意的安全设计，不改变 |
| 9 | `.gitignore` 追加产生空行 | `write()` 前无 strip，但功能正确 | 可忽略 |
| 10 | 并行安全仅同进程 | 内存 dict 无法跨进程 | v0.5 再考虑文件锁 |

---

## 附录：修复优先级

| 优先级 | 修复项 | 涉及文件 | 行数 |
|--------|--------|---------|------|
| **P0** | discard 路径安全校验 | `worktree.py` | +5 |
| **P0** | `_short_id` 空字符串保护 | `worktree.py` | +1 |
| **P0** | `_check_clean_working_tree` 缩进 | `worktree.py` | 调整 6 行 |
| **P1** | merge 冲突恢复路径 | `worktree.py` | +8 |
| **P1** | `_count_changed_files` 退路 | `worktree.py` | +8 |
| **P2** | 状态持久化 | `worktree.py` | +25 |
| **P2** | branch 删除前缀校验 | `worktree.py` | +5 |
| **P3** | fetch 失败区分 | `worktree.py` | +5 |
