# Hermes Desktop 状态模型

## 1. 核心数据模型

### Project（项目）

```typescript
interface Project {
  id: string;
  name: string;
  path: string;          // 本地绝对路径
  branch: string;        // 当前 git 分支
  dirty: boolean;        // 是否有未提交变更
  last_active_at: string; // ISO 8601
}
```

### TaskThread（任务线程）

```typescript
type TaskStatus =
  | 'draft'        // 已创建，未提交
  | 'queued'       // 等待执行
  | 'running'      // 正在执行
  | 'needs_review' // 等待人工审核
  | 'done'         // 已完成并接受
  | 'failed'       // 执行失败
  | 'blocked'      // 被外部依赖阻塞
  | 'cancelled';   // 已取消

type TaskSource = 'desktop' | 'feishu' | 'api' | 'cron';

interface TaskThread {
  id: string;
  project_id: string;
  title: string;
  status: TaskStatus;
  source: TaskSource;
  last_run_id: string | null;
  created_at: string;
  updated_at: string;
  // v0.3+ 扩展点
  router_policy?: string;
}
```

`TaskThread.status` 是面向列表和筛选的投影状态，不是 run 生命周期的唯一事实源。运行中的事实源始终是 `AgentRun.status` 和 `RunEvent`；Thread 状态只由 Orchestrator 根据最新 run 归纳更新，UI 不应独立写入。

### AgentRun（智能体运行）

```typescript
type RunStatus =
  | 'created'          // 已创建
  | 'queued'           // 已进入 Orchestrator 队列，等待资源
  | 'starting'         // 正在启动执行器
  | 'running'          // 执行器运行中，事件持续流入
  | 'waiting_review'   // 执行器阻塞在人工 review gate
  | 'completed'        // 成功完成
  | 'failed'           // 失败
  | 'cancelled';       // 已取消

type ExecutorId = string; // v0.1: 'hermes-local'；v0.3 起由 AdapterRegistry/manifest 扩展

interface AgentRun {
  id: string;
  thread_id: string;
  executor_id: ExecutorId;
  status: RunStatus;
  prompt: string;
  started_at: string | null;
  ended_at: string | null;
  external_run_id: string | null; // 具体 executor 返回的运行 id；UI 不直接使用
  error_summary: string | null;
  worktree_path: string | null;   // v0.4 起启用；v0.1/v0.3 为 null
  base_path: string;              // 实际执行目录；v0.4 前等于 Project.path
  // v0.4+ 扩展点
  qa_run_id?: string;
}
```

`RunStatus.waiting_review` 是 review gate 的状态事实源。不要再另设 `review_state = pending` 表示同一件事；是否已经被接受/完成由 `ReviewDecision` 记录。

### RunEvent（运行事件）

```typescript
type RunEventType =
  | 'message'
  | 'reasoning'
  | 'tool_call'
  | 'tool_result'
  | 'log'
  | 'diff'
  | 'approval_needed'
  | 'review_decision'
  | 'completed'
  | 'failed';

interface RunEvent {
  id: string;
  run_id: string;
  seq: number;         // 单次 run 内单调递增
  type: RunEventType;
  payload: unknown;    // 按 type 各有结构，见第 7 节
  created_at: string;
}
```

### ExecutorConfig（执行器配置）

```typescript
interface ExecutorConfig {
  executor_id: ExecutorId;
  model: string;
  env: Record<string, string>;
  extra: Record<string, unknown>; // 执行器私有参数
}
```

### ChangedFile（变更文件）

```typescript
type FileChangeStatus = 'added' | 'modified' | 'deleted';

interface ChangedFile {
  run_id: string;
  path: string;          // 相对于 project.path
  absolute_path: string; // Open in Editor 使用；v0.4 worktree 时指向 worktree 内文件
  additions: number;
  deletions: number;
  status: FileChangeStatus;
  diff_patch: string;    // unified diff 格式
  tool_call_id?: string;
  source_event_id?: string;
}
```

### ReviewDecision（审核决定）

```typescript
type Decision = 'continue' | 'accept' | 'done' | 'reject';

interface ReviewDecision {
  run_id: string;
  decision: Decision;
  comment: string;
  decided_at: string;
}
```

`retry` 不是 review decision，而是创建新 `AgentRun` 的命令。它不应写入 `ReviewDecision`，否则会把“审批当前 run”和“重跑新 run”混成一个状态。

### WorktreeAllocation（v0.4）

```typescript
type WorktreeStatus = 'preparing' | 'ready' | 'failed' | 'cleaning' | 'released';

interface WorktreeAllocation {
  id: string;
  run_id: string;
  project_id: string;
  base_branch: string;
  worktree_path: string;
  status: WorktreeStatus;
  created_at: string;
  released_at: string | null;
}
```

v0.4 并行任务只需要记录每个 run 的执行目录和生命周期，不需要在 v0.1/v0.3 引入完整 runtime 调度系统。

---

## 2. 实体关系图

```
Project
  └─── TaskThread (N)
         ├── source: desktop | feishu | api | cron
         ├── status: TaskStatus
         └── AgentRun (N, last_run_id → 最新)
              ├── executor_id: ExecutorId
              ├── status: RunStatus
              ├── RunEvent (N, seq 有序)
              ├── ChangedFile (N, 由 diff/tool_result/log 聚合)
              ├── ReviewDecision (0..1)
              └── WorktreeAllocation (0..1, v0.4)
```

---

## 3. UI 状态与执行状态的映射

UI 是**只读消费者**，所有状态变更均来自后端事件流，UI 不直接修改运行状态。

| UI 行为 | 允许的写操作 | 对应 API |
|---|---|---|
| 点击"停止" | 发送停止指令 | `POST /v1/runs/{id}/stop` |
| 审核通过/拒绝 | 提交审核决定 | `POST /v1/runs/{id}/approval` |
| 发起 / Retry / Continue | 请求 Orchestrator 创建新 Run | `POST /v1/runs` 或 Orchestrator API |
| 查看事件流 | 订阅只读流 | `GET /v1/runs/{id}/events` (SSE) |
| 其他所有展示 | — | 无写操作 |

UI **禁止**：直接调用具体执行器、直接修改 TaskThread/AgentRun 状态字段、绕过 Orchestrator 发起新 Run。

---

## 4. RunEvent payload 结构

| type | payload 字段 |
|---|---|
| `message` | `{ role, content: string }` |
| `reasoning` | `{ content: string }` |
| `tool_call` | `{ tool_call_id, tool_name, input: object, status?: string }` |
| `tool_result` | `{ tool_call_id, tool_name, output: unknown, error?: string, stdout?: string, stderr?: string }` |
| `log` | `{ level: 'debug'|'info'|'warn'|'error', text: string, tool_call_id?: string }` |
| `diff` | `{ files: ChangedFile[], tool_call_id?: string }` |
| `approval_needed` | `{ reason: string, options: Decision[] }` |
| `review_decision` | `{ decision: Decision, comment?: string }` |
| `completed` | `{ summary?: string }` |
| `failed` | `{ error: string, code?: string }` |

---

## 5. 版本扩展点

| 字段 | 位置 | 用途 |
|---|---|---|
| `router_policy` | `TaskThread` | v0.3 路由策略标识，供 Router 决定分配哪个执行器 |
| `executor_id` | `AgentRun` | v0.3 多执行器扩展点，UI 不直接分支判断 |
| `worktree_path` | `AgentRun` | v0.4 指向独立 git worktree 路径，支持并行任务隔离 |
| `WorktreeAllocation` | 独立实体 | v0.4 记录 worktree 准备/释放状态 |
| `qa_run_id` | `AgentRun` | 关联 QA Agent 的 Run ID，主 Run 完成后自动触发 |

v0.1 只使用 `hermes-local`、单 project、单 base path、单活动 run。v0.3 引入多执行器但不引入 worktree；v0.4 再引入 worktree 和并行任务。

---

## v1.0 模型补充（2026-06-04 收口）

以下模型在 v0.5–v0.8 阶段新增，现合并到本权威状态模型文档：

### AgentRun 新增字段

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `run_seq` | number | P1-3 | 同一 thread 内单调递增，由 Orchestrator 分配 |
| `run_type` | `'main' \| 'review' \| 'qa'` | v0.7 | 运行类型 |
| `user_prompt` | string | v0.6 | 用户原始输入，不含注入内容 |
| `prompt_snapshot` | string? | v0.6 | 实际发送给 executor 的完整 prompt |
| `context_include_flags` | Record<string, boolean> | v0.6 | 本次 run 的上下文字段 include 开关快照 |
| `parent_run_id` | string? | v0.7 | review/qa run 指向 main run |
| `review_run_id` | string? | v0.7 | main run 的 review run ID |
| `qa_run_id` | string? | v0.7 | main run 的 qa run ID |
| `review_status` | ReviewStatus? | v0.7 | review 状态 |
| `qa_status` | QaStatus? | v0.7 | qa 状态 |

### ExecutorConfig 新增字段

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `disabled_tools` | string[] | P1-2 | review/qa run 禁用写文件工具 `['write_file','edit_file','create_file']` |

### TaskSource / InboxSource（统一枚举）

```
TaskSource = 'desktop' | 'cli' | 'feishu' | 'discord' | 'api' | 'scheduler'
```

`InboxSource` 与 `TaskSource` 共用同一枚举（v0.8 → P0-2 统一）。

### Review / QA 模型

| 模型 | 说明 | 来源 |
|---|---|---|
| `ReviewFinding` | 单个 review 发现项（severity, category, file_path, title, description, suggestion） | v0.7 |
| `ReviewReport` | review run 汇总（severity 计数 + findings 列表） | v0.7 |
| `ReviewStatus` | `not_started \| running \| completed \| passed \| failed` | v0.7 |
| `QaReport` | QA run 结果（test_passed/failed/skipped, risks[], coverage_delta） | v0.7 |
| `QaRisk` | 单个 QA 风险项 | v0.7 |
| `QaStatus` | `not_started \| running \| completed \| failed` | v0.7 |

### WorkspaceContext

定义在 `workspace-context-injection.md`（v0.6），存放在 `<project_root>/.hermes/context.yaml`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `project_overview` | string | 项目一句话描述 |
| `architecture_notes` | string | 技术栈、模块划分 |
| `adr_summaries` | AdrSummary[] | 关键架构决策 |
| `current_sprint` | string | 当前迭代目标 |
| `common_commands` | CommandEntry[] | 常用命令 |
| `test_commands` | CommandEntry[] | 测试命令 |
| `forbidden_areas` | string[] | 禁止修改的路径 |
| `coding_conventions` | string | 代码约定 |
| `recent_tasks` | RecentTask[] | 最近完成的任务（自动维护，上限 10） |
| `context_injection_enabled` | boolean | 全局注入开关 |

`recent_tasks.summary` 来源（P1-5 明确）：优先取 `AgentRun.error_summary`（failed 时）或 `ReviewDecision.comment`（done 时），若两者为空则为 null。不依赖 agent 生成。

### InboxItem

定义在 `external-inbox.md`（v0.8），存放在 `<project_root>/.hermes/inbox.json`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一 ID |
| `source` | InboxSource | desktop / cli / feishu / discord / scheduler |
| `raw_payload` | object | 原始消息，只读 |
| `draft` | TaskDraft | 系统提取的结构化草稿 |
| `status` | InboxStatus | pending / confirmed / rejected / archived / expired |
| `linked_task_id` | string? | 转化后的 Task Thread ID |
