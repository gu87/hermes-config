# Review / QA Agent 链架构

版本：v0.7-draft
日期：2026-06-04

---

## 一、设计目标

在 main run 完成后，用户可手动触发 review run 或 qa run，对变更进行代码 review 或测试执行。Review/QA run 不自动修改代码，不自动 merge，不覆盖 main run 状态。用户基于 review findings 和 qa result 做最终决策（Accept / Reject / Continue）。

---

## 二、状态模型扩展

### 2.1 AgentRun 新增字段

```typescript
interface AgentRun {
  // ... 现有字段
  parent_run_id?: string      // 若本 run 是 review/qa run，指向 main run
  run_type: RunType           // 'main' | 'review' | 'qa'
  review_run_id?: string      // main run 的 review run ID（若已触发）
  qa_run_id?: string          // main run 的 qa run ID（若已触发，已有扩展点）
  review_status?: ReviewStatus
  qa_status?: QaStatus
}

type RunType = 'main' | 'review' | 'qa'

type ReviewStatus = 
  | 'not_started'
  | 'running'
  | 'completed'      // 有 findings
  | 'passed'         // 无 findings
  | 'failed'         // review run 本身失败

type QaStatus = 
  | 'not_started'
  | 'running'
  | 'completed'      // 测试完成，有结果
  | 'failed'         // qa run 本身失败
```

### 2.2 ReviewFinding（Review 发现项）

```typescript
interface ReviewFinding {
  id: string
  run_id: string           // review run ID
  severity: Severity
  category: FindingCategory
  file_path?: string       // 受影响的文件
  line_range?: [number, number]
  title: string            // 一句话
  description: string
  suggestion?: string      // 修复建议（可选）
  dismissed: boolean       // 用户是否忽略
}

type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

type FindingCategory = 
  | 'correctness'
  | 'security'
  | 'performance'
  | 'maintainability'
  | 'style'
  | 'test_coverage'
```

### 2.3 QaResult（QA 测试结果）

```typescript
interface QaResult {
  id: string
  run_id: string           // qa run ID
  test_passed: number
  test_failed: number
  test_skipped: number
  test_output: string      // stdout/stderr 摘要
  risk_list: QaRisk[]
  coverage_delta?: number  // 覆盖率变化（可选）
}

interface QaRisk {
  severity: Severity
  title: string
  description: string
  affected_areas: string[] // 受影响的模块/文件
}
```

---

## 三、Review Run 设计

### 3.1 触发条件

- main run 状态为 `completed` 或 `waiting_review`
- worktree 状态为 `dirty`（有变更）
- 用户手动点击 **Trigger Review** 按钮

### 3.2 输入（注入到 review prompt）

```
--- Review Context ---
Task Goal: <main run 的 user_prompt>
Main Run Executor: <main run 的 executor_type>
Workspace Context: <裁剪版 workspace context，只含 architecture_notes + coding_conventions>

Changed Files:
  M  services/auth.py   +42 -18
  M  tests/test_auth.py +31 -5
  A  services/auth_errors.py

Diff:
<unified diff，最多 2000 行，超出截断>

Main Run Prompt Snapshot:
<main run 的 prompt_snapshot>
--- End Review Context ---

请 review 此次变更，关注：
1. 正确性（逻辑错误、边界条件）
2. 安全性（SQL 注入、XSS、敏感信息泄露）
3. 性能（N+1 查询、死锁风险）
4. 可维护性（命名、结构、重复代码）
5. 测试覆盖（新增代码是否有测试）

对每个发现项输出：
- severity: critical|high|medium|low|info
- category: correctness|security|performance|maintainability|style|test_coverage
- file_path + line_range（如有）
- title（一句话）
- description
- suggestion（修复建议，可选）
```

### 3.3 推荐 Executor

| 优先级 | Executor | 理由 |
|---|---|---|
| 1 | `claude-code` | 架构/review 类任务最适合，上下文处理能力强 |
| 2 | `opencode` | 本地开源 agent，可作为备选 review executor |
| 3 | `hermes-local` | 若 claude-code 不可用 |

不推荐：`codex-cli`（实现导向，不适合 review）、`deepseek-tui`（无结构化输出）。

### 3.4 Review Run 的 worktree 策略

- review run **复用** main run 的 worktree（只读访问，不写入）。
- `AgentRun.worktree_path` 指向同一个 worktree。
- review run 的 `base_path` 与 main run 一致。
- review run 结束后不清理 worktree（由 main run merge/discard 时统一清理）。

### 3.5 输出解析

Review run 的 timeline 中产出 `ReviewFinding[]`，存入 `run_events` 中 `type: 'review_finding'` event，或在 run 完成后通过 `tool_result` 提取并存入独立表。

UI 从 `ReviewFinding` 表读取，不直接解析 timeline。

---

## 四、QA Run 设计

### 4.1 触发条件

- main run 状态为 `completed` 或 `waiting_review`
- worktree 状态为 `dirty`
- workspace context 包含 `test_commands`（否则无法运行测试）
- 用户手动点击 **Trigger QA** 按钮

### 4.2 输入（注入到 qa prompt）

```
--- QA Context ---
Task Goal: <main run 的 user_prompt>
Changed Files: <changed files 列表>
Test Commands: <workspace_context.test_commands>
Worktree Path: <worktree_path>
--- End QA Context ---

请在 worktree 中执行以下测试：
<test_commands 列表>

输出：
1. 测试结果统计（passed / failed / skipped）
2. 失败测试的详细输出（最多 500 行）
3. 风险列表（severity、title、description、affected_areas）
4. 覆盖率变化（如有）

不要修改任何代码。
```

### 4.3 推荐 Executor

| 优先级 | Executor | 理由 |
|---|---|---|
| 1 | `opencode` | 适合本地环境测试执行，无 token 消耗 |
| 2 | `deepseek-tui` | 快速扫描，适合 small fix 的 smoke test |
| 3 | `claude-code` | 若 opencode 不可用 |

不推荐：`codex-cli`（网络请求，测试执行本地更合适）、`hermes-local`（重量级，不适合测试任务）。

### 4.4 QA Run 的 worktree 策略

- qa run **复用** main run 的 worktree（只读访问，但允许执行测试命令）。
- executor 在 worktree 内执行 `test_commands`，stdout/stderr 收集为 `test_output`。
- qa run 不允许调用 `write_file` / `edit_file` 工具（executor config 中禁用，或 Orchestrator 拦截）。

### 4.5 输出解析

QA run 结束后生成 `QaResult`，存入独立表。`risk_list` 提取自 qa run 的 timeline 或 tool result。

---

## 五、状态流转

```
Main Run (completed)
       │
       ├──► [Trigger Review] ──► Review Run (running) ──► Review Run (completed)
       │                                                        │
       │                                                        ▼
       │                                                   ReviewFinding[]
       │
       └──► [Trigger QA] ──► QA Run (running) ──► QA Run (completed)
                                                        │
                                                        ▼
                                                    QaResult

用户基于 ReviewFinding + QaResult 做最终决策：
  - Accept（merge main run worktree）
  - Reject（discard worktree）
  - Continue（追加 prompt 修复 review findings，创建新 main run）
```

Review run 和 QA run 均不修改 main run 的状态。main run 保持 `completed` 或 `waiting_review`，直到用户做最终决策。

---

## 六、UI 设计

### 6.1 Review Tab（Right Rail）

在 Right Rail 新增 **Review** tab，与 Diff / Changed Files / Logs 平级。

```
┌─ Review ────────────────────────────────────────┐
│  Review Status: ● completed  [Rerun Review]     │
│  Executor: claude-code  ·  2m 15s               │
│                                                 │
│  Findings (3 critical, 2 high, 5 medium):       │
│                                                 │
│  ● CRITICAL  ·  Correctness                     │
│  SQL injection risk in auth.py:42               │
│  [展开] [Dismiss]                                │
│                                                 │
│  ● CRITICAL  ·  Security                        │
│  Hardcoded secret in auth.py:58                 │
│  [展开] [Dismiss]                                │
│                                                 │
│  ● HIGH  ·  Test Coverage                       │
│  New function lacks unit test                   │
│  [展开] [Dismiss]                                │
│                                                 │
│  ...                                            │
│                                                 │
│  [Export Report]                                │
└─────────────────────────────────────────────────┘
```

### 6.2 QA Tab（Right Rail）

```
┌─ QA ────────────────────────────────────────────┐
│  QA Status: ● completed  [Rerun QA]             │
│  Executor: opencode  ·  1m 32s                  │
│                                                 │
│  Test Result:                                   │
│  ✓ 12 passed  ✗ 2 failed  ⊘ 0 skipped          │
│                                                 │
│  Failed Tests:                                  │
│  ✗ test_auth_invalid_token                     │
│  ✗ test_error_handling_edge_case               │
│  [展开详情]                                      │
│                                                 │
│  Risk List (1 high, 2 medium):                  │
│                                                 │
│  ● HIGH  ·  Regression Risk                     │
│  auth module 未覆盖 edge case                    │
│  [展开]                                          │
│                                                 │
│  Coverage Delta: +3.2%                          │
│                                                 │
│  [Export Report]                                │
└─────────────────────────────────────────────────┘
```

### 6.3 Thread Header 增强（Review/QA 状态 Badge）

```
⎇ hermes/a3f8c1b2/3  ·  ● dirty  ·  Review: ✓ passed  ·  QA: ✗ 2 failed
```

- Review badge：`✓ passed`（无 findings）、`⚠ 3 issues`（有 findings）、`—`（未触发）
- QA badge：`✓ passed`（全过）、`✗ N failed`（有失败）、`—`（未触发）

### 6.4 Review Bar 增强（包含 Review/QA 决策）

```
┌─ Review Bar ───────────────────────────────────────────┐
│  Main Run: ● completed  ·  3m 42s                      │
│  Review: ⚠ 3 critical issues  [查看 →]                 │
│  QA: ✗ 2 tests failed  [查看 →]                        │
│                                                        │
│  [Continue (修复 findings)]  [Accept (忽略 findings)]  │
│  [Reject (丢弃变更)]                                    │
└────────────────────────────────────────────────────────┘
```

- **Continue**：基于 review findings 追加修复 prompt，创建新 main run（在同一 worktree 继续）
- **Accept**：忽略 review findings 和 qa failures，merge worktree
- **Reject**：丢弃 worktree（需确认对话框）

### 6.5 Trigger Review / QA 按钮位置

在 Thread Header 右侧：

```
⎇ hermes/a3f8c1b2/3  [Trigger Review]  [Trigger QA]  [Stop]
```

- 仅在 main run `completed` 或 `waiting_review` 时可见。
- 若 review run 已触发且未完成，按钮变为 `[Review running...]`（禁用）。
- 若 review run 已完成，按钮变为 `[Rerun Review]`。

---

## 七、禁止事项（硬约束）

| 禁止事项 | 实现位置 |
|---|---|
| Review/QA run 不自动修改代码 | executor config 禁用 `write_file` / `edit_file` 工具；Orchestrator 拦截 |
| Review/QA run 不自动 merge | `ReviewDecision.decision` 只能由用户触发，不能由 review/qa run 产出 |
| Review/QA run 不覆盖 main run 状态 | main run 的 `status` 和 `review_state` 不受 review/qa run 影响 |
| 用户最终确认仍然必要 | Review Bar 始终显示，Accept/Reject/Continue 按钮始终需要用户点击 |
| Review/QA run 不能触发新的 review/qa | `run_type = 'review'` 或 `'qa'` 的 run 的 Trigger Review/QA 按钮禁用 |

Orchestrator 在 `createRun(threadId, prompt, executorType, runType)` 时检查 `runType`：
- 若 `runType = 'review'` 或 `'qa'`，禁用写文件工具。
- 若 `runType = 'review'` 或 `'qa'`，不允许再触发 review/qa（防止递归）。

---

## 八、扩展点（v1.0+）

- **Auto-review 规则**：用户配置"critical findings > 0 时自动阻止 Accept"，但仍需显式点击 Continue/Reject。
- **Review findings 修复建议应用**：review run 产出的 `suggestion` 可一键应用（创建新 run，prompt 为 suggestion）。
- **QA coverage gate**：用户配置"覆盖率下降超过 5% 时阻止 Accept"。
- **多轮 review**：Continue 后创建新 main run，可再次 Trigger Review，形成迭代链。
- **Review template**：用户自定义 review prompt 模板（替换默认的 5 点检查清单）。
