# Run Event / Log / Diff / Review Bridge 设计

版本：v1.0-pre
日期：2026-06-04

---

## 一、后端事件类型（完整 schema）

`/v1/runs/{run_id}/events` SSE 流的事件定义。**当前已实现**标注 ✅，**需扩展**标注 ⚠️，**需新增**标注 ❌。

```typescript
// 所有事件共有字段
interface BaseEvent {
  event: string
  run_id: string
  timestamp: number  // unix epoch float
}

// ✅ 已有
interface MessageDeltaEvent extends BaseEvent {
  event: 'message.delta'
  delta: string
}

// ✅ 已有（只有 tool_name + preview）
// ⚠️ 需扩展：加 args
interface ToolStartedEvent extends BaseEvent {
  event: 'tool.started'
  tool: string
  preview?: string
  args?: unknown      // 新增：tool call 参数
}

// ✅ 已有（只有 tool_name + duration + error）
// ⚠️ 需扩展：加 output/stdout/stderr
interface ToolCompletedEvent extends BaseEvent {
  event: 'tool.completed'
  tool: string
  duration: number
  error: boolean
  output?: string     // 新增：工具返回值摘要
  stdout?: string     // 新增：subprocess stdout
  stderr?: string     // 新增：subprocess stderr
}

// ❌ 需新增
interface ToolLogEvent extends BaseEvent {
  event: 'tool.log'
  tool: string
  message: string
  level?: 'info' | 'warn' | 'error'
}

// ❌ 需新增
interface DiffEvent extends BaseEvent {
  event: 'diff'
  patch: string           // unified diff 全文
  base_commit: string     // git_snapshot（run 开始时记录的 HEAD）
  files_changed: number
}

// ✅ 已有
interface ReasoningEvent extends BaseEvent {
  event: 'reasoning.available'
  text: string
}

// ✅ 已有
interface ApprovalRequestEvent extends BaseEvent {
  event: 'approval.request'
  message?: string
}

// ✅ 已有
interface RunCompletedEvent extends BaseEvent {
  event: 'run.completed'
  response_id: string
}

// ✅ 已有
interface RunFailedEvent extends BaseEvent {
  event: 'run.failed'
  error: string
}

// ✅ 已有
interface RunCancelledEvent extends BaseEvent {
  event: 'run.cancelled'
}
```

---

## 二、后端产出 diff 事件的时机

`diff` 事件在 `run.completed` **之前**由 HermesLocalAdapter 插入，步骤：

```
1. POST /v1/runs 时记录 git_snapshot = subprocess("git rev-parse HEAD", cwd=base_path)
2. run 执行完毕，agent 写文件结束
3. patch = subprocess("git diff {git_snapshot}", cwd=base_path)
4. 若 patch 非空，push diff event → patch, base_commit, files_changed
5. push run.completed
```

若 `base_path` 不是 git repo，跳过 diff event（不报错）。
若 patch 超过 200KB，截断并在 patch 末尾追加 `\n[truncated: N bytes omitted]`。

---

## 三、前端 ChangedFiles 聚合

前端从 diff events 聚合出 `ChangedFile[]`，不依赖独立 API 端点。

```typescript
function parseChangedFiles(diffPatch: string, runId: string): ChangedFile[] {
  // 解析 unified diff，每个 diff --git a/... b/... 块作为一个文件
  const files: ChangedFile[] = []
  const fileBlocks = diffPatch.split(/^diff --git /m).slice(1)
  for (const block of fileBlocks) {
    const pathMatch = block.match(/^a\/(.*?) b\//)
    if (!pathMatch) continue
    const path = pathMatch[1]
    const additions = (block.match(/^\+[^+]/mg) || []).length
    const deletions = (block.match(/^-[^-]/mg) || []).length
    const status = additions > 0 && deletions === 0 ? 'added'
                 : additions === 0 ? 'deleted' : 'modified'
    files.push({ run_id: runId, path, additions, deletions, status, diff_patch: block })
  }
  return files
}
```

`getChangedFiles(runId)` IPC handler：
- run 进行中：返回实时聚合的 `ChangedFile[]`（监听 diff events）
- run 结束后：返回持久化在 DB 中的结果（main process 在 `run.completed` 时写入）

---

## 四、LogsTab / DiffTab / ChangedFilesPanel 渲染规则

### LogsTab

数据来源：`tool.log` events，按 tool_name 分组。

```
┌─ Logs ─────────────────────────────────────────┐
│  ⚙ write_file                                   │
│  · [13:24:01] Writing 42 lines to auth.py       │
│  · [13:24:01] File written successfully         │
│                                                 │
│  ⚙ run_tests                                    │
│  · [13:24:03] Running pytest...                 │
│  · [13:24:05] 12 passed, 0 failed               │
└─────────────────────────────────────────────────┘
```

- `tool.completed.stdout` 若非空，作为该 tool 的最后一条 log 展示（level: info）
- `tool.completed.stderr` 若非空，level: warn
- `tool.completed.error = true` 时，最后一条 log 高亮红色

### DiffTab

数据来源：`diff` event 的 `patch` 字段。

```
┌─ Diff ─────────────────────────────────────────┐
│  services/auth.py  +42 -18                      │
│  ─────────────────────────────────────          │
│  @@ -15,6 +15,8 @@                              │
│  - old_code_line()                              │
│  + new_code_line()                              │
│  + another_new_line()                           │
└─────────────────────────────────────────────────┘
```

- 使用标准 unified diff 渲染（`diff2html` 或手写简单渲染）
- 无 diff event 时显示空状态：`本次 run 未产生文件变更`（不显示 loading）
- run 进行中时显示：`run 完成后生成 diff`

### ChangedFilesPanel

数据来源：聚合的 `ChangedFile[]`。

```
┌─ Changed Files ─────────────────────────────────┐
│  M  services/auth.py      +42 −18  [Diff] [Open]│
│  M  tests/test_auth.py    +31 −5   [Diff] [Open]│
│  A  services/auth_errors.py +28 −0  [Diff] [Open]│
└─────────────────────────────────────────────────┘
```

- `[Diff]` 按钮：切换到 DiffTab 并定位到该文件
- `[Open]` 按钮：`shell.openPath(absolute_path)`（Electron main process）
- `absolute_path = path.join(run.worktree_path ?? project.path, file.path)`
- 无文件变更时显示：`本次 run 未修改文件`（明确空状态，不留空白）

---

## 五、Continue / Retry IPC 边界

### Continue（延续同一任务上下文）

```
用户在 Input Bar 输入追加 prompt，提交
       │
       ▼
IPC: window.hermesAPI.continueRun(threadId, newPrompt, previousRunId)
       │
       ▼
main process:
  1. 从 response_store 读取 previousRunId 的 conversation_history
  2. POST /v1/runs { input: newPrompt, conversation_history: [...], session_id: threadId }
       │
       ▼
新 AgentRun 创建，status: created
thread.last_run_id 更新
```

前端 IPC handler（main process）：
```typescript
ipcMain.handle('run:continue', async (_, threadId, prompt, previousRunId) => {
  const history = await db.getRunHistory(previousRunId)  // 从本地 DB 取
  const res = await fetch(`${GATEWAY}/v1/runs`, {
    method: 'POST',
    body: JSON.stringify({ input: prompt, conversation_history: history, session_id: threadId })
  })
  return res.json()  // { run_id }
})
```

### Retry（重新执行，不带历史）

```
用户点击 Retry（failed / interrupted run）
       │
       ▼
IPC: window.hermesAPI.retryRun(threadId, originalPrompt)
       │
       ▼
main process:
  POST /v1/runs { input: originalPrompt, session_id: threadId }
  // 无 conversation_history，无 previous_response_id
       │
       ▼
新 AgentRun 创建，run_seq 递增
```

**关键区别**：Retry 不携带历史，是全新执行；Continue 携带历史，是延续。两者都创建新的 `AgentRun`，不覆盖旧 run。

---

## 六、triggerReview / triggerQA IPC 边界

### triggerReview

```
用户点击 [Trigger Review]（仅在 run.completed 后可见）
       │
       ▼
IPC: window.hermesAPI.triggerReview(mainRunId)
       │
       ▼
main process:
  1. 读取 mainRunId 的 diff patch 和 user_prompt
  2. 构造 review prompt（见 review-qa-agent-chain.md §3.2）
  3. POST /v1/runs { input: reviewPrompt, executor: 'opencode', session_id: reviewSessionId }
       │
       ▼
ReviewRun AgentRun 创建（run_type: 'review'，parent_run_id: mainRunId）
前端订阅 review run 的 events，渲染到 ReviewTab
```

### triggerQA

```
用户点击 [Trigger QA]（仅在 run.completed 且 workspace_context.test_commands 非空时可见）
       │
       ▼
IPC: window.hermesAPI.triggerQA(mainRunId)
       │
       ▼
main process:
  1. 读取 worktree_path 和 test_commands
  2. 构造 QA prompt（见 review-qa-agent-chain.md §4.2）
  3. POST /v1/runs { input: qaPrompt, executor: 'opencode', session_id: qaSessionId }
       │
       ▼
QaRun AgentRun 创建（run_type: 'qa'，parent_run_id: mainRunId）
```

**禁止事项**（在 main process handler 中强制）：
- review/qa run 的 ExecutorConfig 中加 `disabled_tools: ['write_file', 'create_file', 'edit_file']`
- review/qa run 的 `run_type` 不允许再 trigger review/qa（handler 检查 parent_run_id 非空则拒绝）

---

## 七、opencode review/QA adapter 最小实现

v1.0 的 opencode adapter 只需实现 review 场景，QA 场景允许降级到 hermes-local。

### OpenCodeAdapter 最小接口实现

```typescript
class OpenCodeAdapter implements AgentExecutorAdapter {
  async start(run: AgentRun, config: ExecutorConfig): Promise<AdapterStartResult> {
    // git snapshot
    const git_snapshot = execSync('git rev-parse HEAD', { cwd: config.base_path }).toString().trim()
    // 启动 opencode 子进程
    this.proc = spawn('opencode', ['run', '--json', run.prompt], {
      cwd: config.base_path,
      env: { ...process.env, ...config.env }
    })
    this.procs.set(run.id, { proc: this.proc, git_snapshot, base_path: config.base_path })
    return { git_snapshot, base_path: config.base_path }
  }

  async stop(runId: string): Promise<void> {
    this.procs.get(runId)?.proc.kill('SIGTERM')
  }

  async *streamEvents(runId: string): AsyncIterable<RunEvent> {
    const { proc, git_snapshot, base_path } = this.procs.get(runId)
    // 逐行读取 stdout，尝试 JSON parse；失败则作为 tool.log 输出
    for await (const line of readline(proc.stdout)) {
      try {
        const parsed = JSON.parse(line)
        yield normalizeOpencodeEvent(parsed, runId)
      } catch {
        yield { run_id: runId, seq: 0, type: 'log', payload: { message: line } }
      }
    }
    // 追加 diff event
    try {
      const patch = execSync(`git diff ${git_snapshot}`, { cwd: base_path }).toString()
      if (patch) yield { run_id: runId, seq: 0, type: 'diff', payload: { patch, base_commit: git_snapshot } }
    } catch { /* not a git repo, skip */ }
    // 检查 exit code
    const code = await waitForExit(proc)
    if (code !== 0) yield { run_id: runId, seq: 0, type: 'failed', payload: { error_summary: `exit ${code}` } }
    else yield { run_id: runId, seq: 0, type: 'completed', payload: {} }
  }

  async getStatus(runId: string): Promise<RunStatus> {
    const entry = this.procs.get(runId)
    if (!entry) return 'completed'
    return entry.proc.exitCode === null ? 'running' : 'completed'
  }

  async checkHealth(): Promise<ExecutorHealthResult> {
    try {
      const v = execSync('opencode --version').toString().trim()
      return { available: true, version: v }
    } catch {
      return { available: false, error: 'opencode not found in PATH' }
    }
  }
}
```

`normalizeOpencodeEvent`：将 opencode JSON line 映射到 RunEvent。opencode 输出格式未完全稳定，对未知字段一律降级为 `tool.log`。

### v1.0 中 opencode adapter 的 capability 声明

```yaml
id: opencode
label: opencode
ui_fidelity: full          # 支持结构化 tool_call（若 opencode JSON output 足够）
capabilities:
  structured_tool_calls: true   # 按实际格式调整
  native_diff_events: false     # adapter 生成
  reasoning_blocks: false
  review_gate: false            # review/qa run 不支持 approval gate
  streaming: line-buffered
```

---

## 八、与现有后端的集成约束

| 约束 | 说明 |
|---|---|
| 不新建后端 API 端点 | v1.0 只扩展现有 `/v1/runs` 的事件 payload，不新增路由 |
| `tool.completed` 扩展向后兼容 | 新字段 `output/stdout/stderr` 为可选，现有消费者不受影响 |
| `diff` event 可选 | 前端对无 `diff` event 的 run 显示"本次未修改文件"，不报错 |
| review/qa run 通过同一 `/v1/runs` 端点创建 | `run_type` 字段在请求 body 中传递，后端存储但不改变执行逻辑 |
| `disabled_tools` 强制在 main process 层实现 | 后端不感知 disabled_tools，由 adapter 在构造 prompt 时注入约束（"不要调用 write_file"） |
