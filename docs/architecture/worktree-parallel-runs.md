# Worktree 并行任务架构

版本：v0.4-draft
日期：2026-06-04

---

## 一、设计目标

每个 Task Thread 绑定一个独立 git worktree，使多个 agent run 并行执行时文件系统互不污染。主仓库始终保持干净状态，agent 的所有写操作发生在 worktree 内。

---

## 二、Worktree 创建规则

### 何时创建

- `createRun` 调用时，若 `ExecutorManifest.capabilities.worktree = true` 且 task thread 无活跃 worktree，则 Orchestrator 在 `startRun` 前创建 worktree。
- 若 task thread 已有状态为 `ready` 或 `dirty` 的 worktree，复用该 worktree，不重新创建。
- `hermes-local` executor 在 v0.4 前不使用 worktree（`worktree_path = null`），run 在主仓库执行。

### 创建命令

```
git worktree add <worktree_path> -b <branch_name>
```

- 从主仓库当前 HEAD 创建分支。
- 若主仓库有未提交变更，**拒绝创建**，提示用户先 commit 或 stash。

### 存放路径

```
<project_root>/.hermes/worktrees/<thread_id_short>/
```

- `thread_id_short`：task thread id 后 8 位。
- 路径在 `.gitignore` 中排除（`.hermes/worktrees/`）。

---

## 三、Branch 命名规则

```
hermes/<thread_id_short>/<run_seq>
```

示例：`hermes/a3f8c1b2/3`

- `thread_id_short`：task thread id 后 8 位。
- `run_seq`：该 thread 下的 run 序号（从 1 开始），由 Orchestrator 分配。
- branch 名称在 worktree 创建时生成，不随后续 run 变化（worktree 复用时 branch 名保持不变）。

**不使用 task title 作为 branch 名**，避免特殊字符和中文导致 git 命令失败。

---

## 四、TaskThread 与 WorktreePath 的绑定关系

- 一个 `TaskThread` 最多绑定一个活跃 worktree（`WorktreeAllocation`）。
- 绑定关系通过 `WorktreeAllocation.thread_id` 记录。
- `AgentRun.worktree_path` 在 run 创建时从当前活跃 `WorktreeAllocation.path` 复制，快照绑定，不随后续 worktree 状态变化。
- worktree 释放（`merged` 或 `discarded`）后，下次 `createRun` 会创建新的 worktree。

```
TaskThread (1) ──► WorktreeAllocation (0..1 活跃)
                       │
                       ▼
              AgentRun (n) 各自快照 worktree_path
```

---

## 五、Worktree 状态机

```
                [createRun 触发]
                      │
                      ▼
              ┌─ not_created ─┐
              │  (初始状态)    │
              └───────────────┘
                      │ git worktree add
                      ▼
                  creating
                      │
              ┌───────┴────────┐
              ▼                ▼
            ready           failed ◄── git 命令失败（主仓库有冲突等）
              │
              │ agent 写入文件
              ▼
            dirty
              │
       ┌──────┴──────────────────┐
       │                         │
       ▼                         ▼
   merging                   discarded ◄── 用户主动丢弃 / run failed
       │
  ┌────┴─────┐
  ▼          ▼
merged     failed（merge 冲突）
```

| 状态 | 含义 |
|---|---|
| `not_created` | worktree 尚未创建（task thread 刚建立） |
| `creating` | `git worktree add` 正在执行 |
| `ready` | worktree 已就绪，与主仓库 HEAD 一致，无未提交变更 |
| `dirty` | agent 已写入文件，worktree 有未提交变更 |
| `merging` | 用户触发 merge，`git merge` 正在执行 |
| `merged` | 已合入主仓库，worktree 可释放 |
| `discarded` | 用户主动丢弃，或 run failed 后清理，变更不保留 |
| `failed` | worktree 操作失败（创建失败或 merge 冲突），需人工介入 |

---

## 六、并行 Run 限制

### v0.4 规则

- 单个 Task Thread：同一时刻只允许一个 `running` 状态的 AgentRun。同一 thread 的第二个 run 必须等第一个结束（`completed` / `failed` / `cancelled`）后才能启动。
- 跨 Task Thread：并行数量上限由配置项 `max_parallel_runs`（默认 3）控制。超出时，新建 run 进入 `queued` 状态，等待空位。
- 同一 worktree 不能被两个并行 run 同时写入（通过"单 thread 单活跃 run"约束自然保证）。

### 为什么不允许同一 thread 并行

同一 TaskThread 共享同一 worktree。两个 run 并行写同一 worktree 等同于两个进程并发写同一工作目录，文件冲突不可预测。v1.0 如需同一 thread fork，应创建新 TaskThread（分支任务），不在同一 worktree 并行。

---

## 七、Merge Back 策略

### 触发方式

- 用户在 Review Bar 点击 **Accept** 时触发 merge。
- 仅在 worktree 状态为 `dirty` 且 run 状态为 `completed` 或 `waiting_review` 时可触发。

### Merge 流程

```
1. git -C <project_root> fetch  # 确认主仓库 HEAD 最新
2. git -C <worktree_path> add -A && git commit -m "hermes: <task_title> [run #<seq>]"
   （若 worktree 有未提交变更）
3. git -C <project_root> merge --no-ff <branch_name>
```

### Merge 结果处理

| 结果 | 处理 |
|---|---|
| 成功 | worktree 状态 → `merged`；ReviewDecision 记录 `accept`；UI 提示 merge commit sha |
| 冲突 | worktree 状态 → `failed`；UI 显示冲突文件列表；**不自动解决**，提示用户手动 resolve 后重新触发 |

### Merge 后 worktree 清理

merge 成功后，`git worktree remove <path>` 在后台异步执行。清理失败不阻塞主流程，记录为警告。

---

## 八、Discard Worktree 策略

### 触发条件

- 用户在 Review Bar 点击 **Reject / Discard**。
- run 状态变为 `failed` 且用户确认放弃变更。
- worktree 状态为 `failed`（创建失败）时自动触发清理。

### Discard 流程

```
1. 确认 worktree 状态为 dirty / failed（不是 merging，避免竞争）
2. git worktree remove --force <worktree_path>
3. git branch -D <branch_name>
4. WorktreeAllocation.status → discarded，released_at 记录时间戳
```

**丢弃不可逆**，UI 必须弹出确认对话框，显示将被丢弃的文件变更摘要（`git diff --stat`）。

---

## 九、Diff 来源

### Worktree Diff（v0.4 主路径）

- 来源：`git diff <worktree_path>` 或 `git diff HEAD` 在 worktree 内执行。
- 包含：worktree 内所有未提交变更，即 agent run 的完整修改。
- 时机：每次 `diff` type RunEvent 生成时，或用户打开 Changed Files panel 时实时读取。

### Main Repo Diff（merge 后）

- 来源：`git show <merge_commit_sha>` 或 `git diff <base_commit>..<merge_commit>`。
- 包含：合入主仓库的最终变更（可能与 worktree diff 不同，若 merge 时有 conflict resolution）。
- 时机：merge 成功后，run 的 `ChangedFile` 列表更新为 main repo diff，替换原 worktree diff。

### 无 Worktree 时（v0.1/v0.3 回退路径）

- 来源：`git diff HEAD`（主仓库）或 adapter 生成的 diff patch。
- 适配器负责在 `git_snapshot` 基础上生成，逻辑与 multi-executor-adapter-design.md 中描述一致。

### Diff 读取实现规则

- `ChangedFile.absolute_path` 在 worktree 模式下指向 worktree 内文件路径，不是主仓库路径。
- Open in Editor 使用 `absolute_path`，worktree 模式下打开的是 worktree 副本，用户编辑不影响主仓库。
- merge 后 `absolute_path` 更新为主仓库路径。

---

## 十、UI 展示

### Left Rail — Task Thread Card

```
┌─────────────────────────────────┐
│ ◆ 重构 auth 错误处理             │
│ running  ·  hermes/a3f8c1b2/3   │ ← branch name
│ worktree: .hermes/worktrees/a3f8│ ← worktree path（截断显示）
│ ● dirty  · 3 files changed      │ ← dirty state
└─────────────────────────────────┘
```

- `not_created` / `creating`：不显示 worktree 信息，显示 spinner。
- `ready`：显示 branch，灰色文字"就绪"，无 dirty indicator。
- `dirty`：显示 branch + 橙色 `● dirty` + 变更文件数。
- `merging`：显示 branch + spinner + "合并中..."。
- `merged`：显示 branch + 绿色 `✓ 已合入` + merge commit sha 前 7 位。
- `discarded`：显示 branch + 灰色 `✗ 已丢弃`。
- `failed`：显示 branch + 红色 `✗ 失败` + 点击查看错误详情。

### Thread Header — Worktree 状态条

在 Thread Header 下方显示一行 worktree 状态（仅 v0.4 启用 worktree 时）：

```
⎇ hermes/a3f8c1b2/3  ·  .hermes/worktrees/a3f8c1b2  ·  ● dirty  [Reveal in Finder]
```

### Review Bar — Merge / Discard 按钮

| Run 状态 | Worktree 状态 | 可用按钮 |
|---|---|---|
| `waiting_review` 或 `completed` | `dirty` | **Accept（Merge）** / **Discard** |
| `waiting_review` 或 `completed` | `ready` | **Accept（Merge）** / **Discard**（merge 无 commit，只做 worktree remove） |
| `failed` | `dirty` | **Discard** / **Retry**（新 run，复用同一 worktree） |
| `failed` | `failed` | **清理 Worktree**（只做 worktree remove） |
| 任意 | `merging` | 按钮禁用，显示 spinner |
| 任意 | `merged` | **Done**（关闭 thread 或跳转主仓库 diff） |

**Discard 确认对话框**内容：

```
丢弃此次修改？

将丢弃以下变更（共 3 个文件）：
  M  services/auth.py   +42 -18
  M  tests/test_auth.py +31 -5
  A  services/auth_errors.py

此操作不可撤销。

[取消]  [确认丢弃]
```

### Right Rail — Changed Files（Worktree 模式）

- 文件路径相对于 worktree 根（等同于 project 根），不显示 `.hermes/worktrees/...` 前缀。
- 在面板顶部显示一行 badge：`来自 worktree: hermes/a3f8c1b2/3`。
- merge 后 badge 更新为：`已合入主仓库: abc1234`。

---

## 十一、扩展点（v1.0）

- **Task Thread Fork**：从现有 thread 创建分支 thread，各自创建独立 worktree，对比两个 run 的结果后选一合入。
- **Worktree rebase**：主仓库 HEAD 前进时，可对 worktree branch 执行 `git rebase`，保持与主仓库同步。触发条件：主仓库有新提交 + worktree 状态为 `ready`（无未提交变更）。
- **Run compare**：同一 thread 的多个 run（跑在不同 worktree 快照）的 diff 对比视图。
