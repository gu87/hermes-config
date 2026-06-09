# Phase 12B：Backend Feedback Events + Review/QA IPC 架构定位

日期：2026-06-04
背景：V1.0 RC2 Electron E2E 结论 DO NOT RELEASE。6 PASS / 4 FAIL。失败项：Changed Files（0 events）、DiffTab（0 diff events）、triggerReview() 缺失、triggerQA() 缺失。

---

## 一、两个仓库的真实架构

### hermes-agent（后端）

**数据库**：`~/.hermes/kanban.db`（SQLite）

关键表：

| 表 | 用途 | 写入位置 |
|---|---|---|
| `task_events` | 任务生命周期事件，append-only | `kanban_db._append_event()` |
| `task_runs` | 每次 agent 执行记录 | `kanban_db._end_run()` |
| `tasks` | 任务主表，含 `workspace_path` | `kanban_db.create_task()` |

`task_events` schema：
```sql
id INTEGER PK AUTOINCREMENT
task_id TEXT
run_id INTEGER (NULL 表示不属于某次 run)
kind TEXT          ← 事件类型，当前有: claimed, released, completed, blocked, promoted...
payload TEXT       ← JSON，UI 当前从不渲染，始终为 NULL 或被忽略
created_at INTEGER
```

**当前 kind 列表**（全部在 `kanban_db.py` 的 `_append_event` 调用处）：
`claimed`, `released`, `completed`, `blocked`, `unblocked`, `promoted`, `child_completed`, `reclaimed`, `reassigned`, `hallucination_detected` 等——**没有 `log`、`tool_result`、`diff`、`review_result`、`qa_result`**。

**`workspace_path`**：`tasks` 表已有 `workspace_path TEXT` 字段，`complete_task()` 执行时 conn 可查。这是 git diff 的基础。

**事件写入主路径**：
```
dispatch_once() → claim_task() → worker 执行 → complete_task() / block_task()
                                                      ↓
                                            _end_run() + _append_event(kind='completed')
```

`complete_task()` 在 `kanban_db.py:2619`，是写入 `task_events` 的最后一个调用点，也是插入 diff event 的自然位置。

### hermes-desktop（前端）

**读取路径**：
```
Renderer → window.hermesAPI.kanbanGetTask(taskId, profile)
         → IPC: "kanban-get-task"
         → main/kanban.ts:kanbanGetTask()
         → 调用 hermes CLI: hermes kanban task <id>
         → 解析 stdout JSON → KanbanTaskDetail { task, events, runs, comments }
```

**`KanbanEvent` 接口**（`src/main/kanban.ts:66`）：
```typescript
interface KanbanEvent {
  id: number
  task_id: string
  kind: string
  payload: Record<string, unknown> | null  // ← 已有 payload 字段，但 UI 从不渲染
  created_at: number
  run_id: number | null
}
```

**刷新机制**：轮询，`POLL_INTERVAL_MS = 6000`，列表每 6 秒刷新一次。任务详情面板打开时读取一次，**不自动 live refresh**。

**triggerReview / triggerQA**：UI 已有 stub 按钮（`disabled`），无 IPC handler，无 preload 定义，无 main process handler。

---

## 二、四个 RC2 失败项的根本原因

| 失败项 | 根本原因 |
|---|---|
| Changed Files：0 events | 后端 `complete_task()` 从未写入 kind=`diff` 的 task_event；前端也没有从 events 中聚合文件列表的逻辑 |
| DiffTab：0 diff events | 同上，后端从未运行 `git diff`，从未写入 patch |
| triggerReview() 缺失 | preload 无此方法，main process 无 IPC handler，后端无对应 CLI/API |
| triggerQA() 缺失 | 同上 |

---

## 三、新增 RunEvent 类型的设计

### 3.1 不需要迁移 events 表

`task_events` 已有 `payload TEXT`（JSON），`kind TEXT` 自由扩展。只需约定新的 kind 名称和 payload schema，不需要 ALTER TABLE。

### 3.2 新增 kind 定义

```
kind='log'
payload: { "message": str, "level": "info"|"warn"|"error", "tool": str|null }
写入时机: agent 执行中，逐行写（由 plugin_api 或 kanban_bridge 中继）

kind='tool_result'
payload: { "tool": str, "output": str|null, "stdout": str|null, "stderr": str|null,
           "error": bool, "duration_ms": int }
写入时机: 每个 tool call 完成后

kind='diff'
payload: { "patch": str, "base_commit": str, "files_changed": int,
           "files": [{"path": str, "additions": int, "deletions": int, "status": "added"|"modified"|"deleted"}] }
写入时机: complete_task() 调用时，在 _end_run() 之前

kind='review_result'
payload: { "executor": str, "findings": [{"severity": str, "category": str,
           "file": str|null, "title": str, "description": str}] }
写入时机: triggerReview() 对应 run 完成后

kind='qa_result'
payload: { "executor": str, "passed": int, "failed": int, "skipped": int,
           "output": str, "risks": [{"severity": str, "title": str}] }
写入时机: triggerQA() 对应 run 完成后
```

---

## 四、git diff 读取方案

### 写入位置：`kanban_db.complete_task()`（行 2619）

`complete_task()` 已有 `conn`，可查 `tasks.workspace_path`。在 `_end_run()` 调用之后、`_append_event(kind='completed')` 之前插入：

```python
# 读取 workspace_path
row = conn.execute("SELECT workspace_path FROM tasks WHERE id=?", (task_id,)).fetchone()
workspace_path = row["workspace_path"] if row else None

if workspace_path:
    import subprocess, json as _json
    try:
        # 读取当前 HEAD（用于 base_commit）
        base = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=workspace_path, text=True
        ).strip()
        # 读取未提交变更
        patch = subprocess.check_output(
            ["git", "diff", "HEAD"], cwd=workspace_path, text=True
        )
        if not patch:
            # fallback: 读取已暂存变更
            patch = subprocess.check_output(
                ["git", "diff", "--cached", "HEAD"], cwd=workspace_path, text=True
            )
        if patch:
            # 解析文件列表
            files = _parse_diff_files(patch)  # 见下
            _append_event(conn, task_id, "diff", {
                "patch": patch[:200_000],  # 截断防止 DB 膨胀
                "base_commit": base,
                "files_changed": len(files),
                "files": files,
            }, run_id=current_run_id)
    except Exception:
        pass  # 非 git 目录或 git 未安装，静默跳过
```

`_parse_diff_files(patch)` 从 unified diff 解析文件列表（按 `diff --git a/X b/X` 块拆分，统计 `+` / `-` 行数）。实现约 15 行，不依赖第三方库。

---

## 五、前端 ChangedFilesPanel 聚合逻辑

`kanbanGetTask()` 已返回 `events: KanbanEvent[]`，其中包含 `kind='diff'` 的 event。

前端聚合：

```typescript
// kanban.ts 或 renderer
function getChangedFilesFromEvents(events: KanbanEvent[]): ChangedFile[] {
  // 取最后一个 kind='diff' event（最新 run 的 diff）
  const diffEvent = [...events].reverse().find(e => e.kind === 'diff')
  if (!diffEvent?.payload) return []
  const p = diffEvent.payload as { files: ChangedFile[] }
  return p.files ?? []
}
```

不需要新 IPC 端点，直接从现有 `kanbanGetTask()` 返回值中提取。

---

## 六、triggerReview / triggerQA 串联路径

### 6.1 完整调用链

```
Renderer
  window.hermesAPI.triggerReview(taskId, runId)
       ↓ IPC: "kanban-trigger-review"
Main Process (main/index.ts 新增 handler)
  1. 读取 kanbanGetTask(taskId) → 取最后一个 diff event 的 patch
  2. 取 task.title 作为 task_goal
  3. 构造 review_prompt（见 review-qa-agent-chain.md §3.2）
  4. 调用: hermes kanban dispatch <taskId> --step review --prompt <review_prompt>
     或: POST http://localhost:8642/v1/runs { input: review_prompt, session_id: ... }
  5. 返回 { review_run_id }
       ↓
Backend (hermes-agent)
  worker 执行 review run（executor: opencode 或 claude-code）
  完成后调用 complete_task() 或 add_task_event(kind='review_result', payload={findings})
       ↓
Frontend (下次 kanbanGetTask 轮询时)
  events 中出现 kind='review_result' → ReviewTab 渲染 findings
```

### 6.2 preload 新增方法

```typescript
// preload/index.d.ts 新增
triggerReview(taskId: string, runId: number): Promise<{ review_run_id: string }>
triggerQA(taskId: string, runId: number): Promise<{ qa_run_id: string }>
```

### 6.3 main process 新增 IPC handler（main/index.ts）

```typescript
ipcMain.handle('kanban-trigger-review', async (_, taskId, runId) => {
  // 1. 取 diff patch
  const detail = await kanbanGetTask(taskId, undefined)
  const diffEvent = detail.data?.events.reverse().find(e => e.kind === 'diff')
  const patch = (diffEvent?.payload as any)?.patch ?? ''

  // 2. 取 task goal
  const task = detail.data?.task
  const goal = task?.title ?? ''

  // 3. 构造 review prompt
  const prompt = buildReviewPrompt(goal, patch)  // 独立函数，约 20 行

  // 4. 发起 review run（通过 /v1/runs，不通过 kanban dispatch）
  const res = await fetch(`${gatewayUrl}/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ input: prompt, instructions: 'Do not modify any files.' })
  })
  const data = await res.json()

  // 5. review 完成后由 main process 监听 run.completed，写入 task_event
  //    （通过订阅 /v1/runs/{id}/events SSE，run.completed 时解析 findings 写入 kanban DB）
  scheduleReviewEventWrite(taskId, data.run_id)

  return { review_run_id: data.run_id }
})
```

`triggerQA` 同理，区别：prompt 包含 `test_commands`，executor 优先 opencode。

### 6.4 review_result 写回 kanban DB

review run 完成后，main process 调用：

```typescript
// 解析 review run 的 message.delta 聚合为文本，提取 findings
// 然后通过 hermes CLI 写入 task_event
child_process.spawnSync('python3', [
  `${hermesHome}/scripts/kanban-add-event.py`,
  '--task-id', taskId,
  '--kind', 'review_result',
  '--payload', JSON.stringify({ findings, executor: 'opencode', run_id: reviewRunId })
])
```

或直接用 `kanban_db` Python 写入，取决于是否有 CLI 包装。最简路径：新建 `scripts/kanban-add-event.py`（10 行），接受 `--task-id`、`--kind`、`--payload-json` 参数，调用 `_append_event`。

---

## 七、实施步骤优先级

### P0（阻塞 v1.0 release）

**Step 1：hermes-agent `kanban_db.complete_task()` 插入 diff event**
- 文件：`/Users/gu/.hermes/hermes-agent/hermes_cli/kanban_db.py`
- 位置：`complete_task()` 函数，`_end_run()` 调用之后
- 改动：~30 行（git diff 调用 + `_parse_diff_files` + `_append_event`）
- 验证：`hermes kanban task <id>` 返回 JSON 中出现 `kind=diff` event

**Step 2：hermes-desktop 从 events 聚合 ChangedFiles**
- 文件：`/Users/gu/hermes-desktop/src/renderer/src/screens/Kanban/Kanban.tsx`
- 改动：~15 行（`getChangedFilesFromEvents()` + ChangedFilesPanel 渲染）
- 验证：任务详情面板出现文件列表

**Step 3：hermes-desktop DiffTab 渲染 diff patch**
- 文件：同上，从 `kind=diff` event 的 `payload.patch` 渲染 unified diff
- 改动：~20 行（DiffTab 从 events 中取 patch，简单文本渲染）
- 验证：DiffTab 不再空白

**Step 4：triggerReview / triggerQA preload + IPC handler**
- 文件：`preload/index.d.ts` + `preload/index.ts` + `main/index.ts`
- 改动：preload ~10 行，main handler ~40 行
- 验证：点击 Review 按钮后 run 创建，events 轮询后出现 `kind=review_result`

### P1（不阻塞 release，但应在 RC3 前完成）

- `tool_result` event 在 `api_server.py` 的 `tool.completed` 扩展（output/stdout/stderr）
- task 详情面板 live refresh（打开时每 10s 刷新一次 events，不只刷新列表）
- triggerQA 的 opencode adapter 实现

### P2（v1.0 之后）

- `log` event 的流式写入（需 IPC push，不是轮询）
- review findings 的结构化渲染（严重程度着色、文件定位）
- QA coverage delta 展示
