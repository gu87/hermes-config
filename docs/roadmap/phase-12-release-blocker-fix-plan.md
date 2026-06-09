# Phase 12 Release Blocker Fix Plan

日期：2026-06-04
前提：Phase 11 v1.0 本地验收未通过。以下为阻塞 v1.0 release 的缺失项和修复计划。

---

## 一、当前状态诊断

`desktop_workbench/` 为空，无任何实现代码。后端 `/v1/runs` SSE 已有基础事件（见下），但以下关键事件类型缺失：

**后端已有**：
- `tool.started` / `tool.completed`（仅有 tool_name + duration，无 args/output）
- `reasoning.available`
- `message.delta`
- `approval.request` / `approval.responded`
- `run.completed` / `run.failed` / `run.cancelled`

**后端缺失（release blocker）**：
- `tool.output`：工具执行结果（stdout/stderr/return_value）
- `diff`：文件变更 patch（需 adapter 在 run 结束后生成）
- `log`：结构化日志行

---

## 二、Release Blocker 清单

### B1（P0）：后端不产出 tool output / diff / log 事件

前端无法渲染 LogsTab / DiffTab / ChangedFilesPanel，因为后端从未 emit 这三类事件。

**修复范围**：
- `_make_run_event_callback` 中的 `tool.completed` 扩展：加 `output`、`stdout`、`stderr`、`is_error` 字段
- 新增 `tool.log` 事件类型：工具执行中的日志行
- 在 `run.completed` 前由 adapter 插入 `diff` 事件（`git diff HEAD` 结果）

### B2（P0）：前端 ChangedFiles 无聚合逻辑

没有代码从 `diff` events 聚合出 `ChangedFile[]` 列表，`Open in Editor` 无法工作。

### B3（P0）：Continue / Retry IPC 边界未定义

`previous_response_id`（Continue）和全新 run（Retry）的 IPC 调用路径未实现。

### B4（P0）：Review / QA trigger IPC 未实现

`triggerReview` / `triggerQA` preload API 不存在，opencode adapter 为 stub。

### B5（P0）：无 Electron E2E 验收

没有任何 E2E 测试或手动验收脚本，无法证明主链路可通。

---

## 三、修复计划

### Sprint 1：后端事件扩展（不改架构，只扩展 payload）

**目标**：让 `tool.completed` 携带 output，新增 `tool.log` 和 `diff` 事件。

修改范围（仅 `api_server.py` 的 `_make_run_event_callback`）：

```python
# tool.completed 扩展 payload
elif event_type == "tool.completed":
    _push({
        "event": "tool.completed",
        "run_id": run_id,
        "timestamp": ts,
        "tool": tool_name,
        "duration": round(kwargs.get("duration", 0), 3),
        "error": kwargs.get("is_error", False),
        "output": kwargs.get("output"),       # 新增
        "stdout": kwargs.get("stdout"),       # 新增
        "stderr": kwargs.get("stderr"),       # 新增
    })

# 新增 tool.log 事件
elif event_type == "tool.log":
    _push({
        "event": "tool.log",
        "run_id": run_id,
        "timestamp": ts,
        "tool": tool_name,
        "message": kwargs.get("message", ""),
    })
```

`diff` 事件在 `run.completed` 前由 HermesLocalAdapter 插入：
```python
# run 结束时，若 base_path 是 git repo，生成 diff
diff_patch = subprocess.check_output(
    ["git", "diff", git_snapshot], cwd=base_path, text=True
)
_push({"event": "diff", "run_id": run_id, "patch": diff_patch})
```

**验收**：curl `/v1/runs/{id}/events` 能看到 `tool.completed.output`、`tool.log`、`diff` 三类事件。

---

### Sprint 2：前端 IPC bridge + Timeline 渲染

以社区 fathah desktop 的 Electron typed bridge 为模式，最小 preload API：

```typescript
// preload 暴露的最小接口
interface HermesAPI {
  // Run 生命周期
  createRun(threadId: string, prompt: string, executorType: string): Promise<{run_id: string}>
  stopRun(runId: string): Promise<void>
  continueRun(threadId: string, prompt: string, previousRunId: string): Promise<{run_id: string}>
  retryRun(threadId: string, prompt: string): Promise<{run_id: string}>
  streamRunEvents(runId: string, callback: (event: RawRunEvent) => void): () => void
  // Review
  resolveApproval(runId: string, decision: 'continue'|'accept'|'done'|'reject', comment?: string): Promise<void>
  triggerReview(runId: string): Promise<{review_run_id: string}>
  triggerQA(runId: string): Promise<{qa_run_id: string}>
  // 数据读取
  getTaskThreads(projectId: string): Promise<TaskThread[]>
  getChangedFiles(runId: string): Promise<ChangedFile[]>
  getGatewayStatus(): Promise<{connected: boolean, model: string}>
}
```

**Continue vs Retry 边界**：
- `continueRun`：POST `/v1/runs` 带 `conversation_history`（从上次 run 历史重建）或 `previous_response_id`
- `retryRun`：POST `/v1/runs` 带同一 prompt，不带历史（全新 run）

---

### Sprint 3：前端组件实现（fixture-driven 优先）

先用 fixture event stream 开发，验证渲染后再接真实 API。

组件交付顺序：
1. `RunTimeline`：渲染 message.delta / tool.started / tool.completed / reasoning.available / approval.request
2. `ToolCallCard`：compact（名称+状态+耗时）+ 展开（output/stdout/stderr）
3. `ChangedFilesPanel`：从 diff events 聚合，显示增删统计，点击打开 DiffTab
4. `DiffTab`：unified diff 渲染，来源 `diff` event
5. `LogsTab`：tool.log events，按 tool_name 分组
6. `ReviewBar`：approval.request 触发，Continue/Accept/Done 按钮
7. `StatusBar`：gateway 状态 + run 状态 + 计时

---

### Sprint 4：opencode review/QA adapter 最小实现

见 `run-event-log-diff-review-bridge.md` 第六节。

---

### Sprint 5：Electron E2E 验收

见本文第五节。

---

## 四、保持 stub、不阻塞 v1.0 的功能

以下功能在 v1.0 中保持 stub 或不实现，不作为 release blocker：

| 功能 | 状态 | 理由 |
|---|---|---|
| Agent Fleet / spawn tree 视图 | stub | v1.0 范围外 |
| Diff accept / reject / partial apply | stub（只读展示） | 需独立 git 操作设计 |
| Feishu / Discord Inbox | stub（UI 只显示 source icon） | 外部入口 v0.8 范围 |
| Command Center（Cmd+K 搜索） | stub | v0.7 范围 |
| Workspace Context 编辑页面 | stub | v0.6 范围，context 注入用硬编码 |
| Review / QA Agent（opencode） | 最小实现（仅 trigger + findings 展示） | QA runner 完整实现后续补 |
| worktree merge/rebase conflict 解决 | stub（显示冲突文件，不自动解决） | 防止数据丢失 |
| Run compare（同一 thread 多次 run 对比） | stub | v1.0 后段 |
| Scheduler / cron 触发 | stub | Inbox 流程 v0.8 |
| `deepseek-tui` adapter | stub（注册但 checkHealth 返回 not_implemented） | 非结构化输出未解决 |

---

## 五、Electron E2E 验收方案

### 验收脚本（手动，不用 Playwright，减少依赖）

**场景 1：主链路 happy path**
```
1. 启动 desktop_workbench（npm start）
2. 确认 gateway 已启动（status bar 显示 Connected）
3. 选择 project（当前 cwd）
4. 新建 Task Thread，输入 prompt："在 README.md 末尾追加一行 # TEST"
5. 选择 executor: hermes-local，确认发起 run
6. 观察 timeline 出现 message.delta → tool.started → tool.completed
7. 右侧 ChangedFilesPanel 出现 README.md（1 addition）
8. DiffTab 显示 unified diff
9. ReviewBar 出现（approval.request）→ 点击 Accept
10. run 状态变为 completed，task status 变为 done
```
验收标准：步骤 1–10 全部可执行，无白屏/崩溃/静默卡死。

**场景 2：失败可见性**
```
1. 新建 Task Thread，输入无法执行的 prompt（如"删除根目录"）
2. run 失败后 timeline 出现 run.failed event
3. status badge 显示 failed（红色）
4. 不显示 ReviewBar（失败态不进入 review）
5. Retry 按钮可见，点击后创建新 run
```

**场景 3：Stop**
```
1. 发起一个长 prompt run
2. run 进入 running 态，点击 Stop
3. run 状态变为 cancelled，timeline 显示 run.cancelled
4. 不触发 worktree merge
```

**场景 4：Continue**
```
1. 完成一次 run（completed）
2. 在 Input Bar 输入追加要求，提交
3. 新 run 创建，conversation_history 包含上次 run 的 message
4. timeline 显示连续历史
```

### 非功能验收
- gateway 离线时 status bar 显示红色 Disconnected，不白屏
- 刷新页面后 task thread 列表可恢复（来自 kanban DB，不依赖内存）
- 未知 event type 显示 raw fallback card，不崩溃

---

## 六、v1.0 最终 release gate

以下全部通过才能标记 v1.0 released：

- [ ] 后端 `tool.completed` 携带 output，`diff` 事件在 run 结束前 emit
- [ ] 前端 Timeline 渲染 7 种 event type（message/reasoning/tool/log/diff/approval/completed）
- [ ] ChangedFilesPanel 从 diff events 聚合，显示增删统计
- [ ] ReviewBar 在 approval.request 后出现，3 个按钮可用
- [ ] Continue 带 conversation_history，Retry 不带
- [ ] Stop 立即生效，不进入 review
- [ ] 场景 1–4 手动 E2E 全部通过
- [ ] gateway 离线不白屏
- [ ] 未知 event type 有 fallback 渲染
