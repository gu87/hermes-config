# Hermes Desktop v1.0 最终架构 Review

日期：2026-06-04
范围：全部 8 份架构文档 + PRD + IA + ADR
工具链（当前）：Codex CLI、Claude Code CLI、opencode、DeepSeek TUI、Trae（本地 UI 调试）

---

## 一、总体判断

主链路 `Task Thread → Agent Run → Artifact/Diff → Review → Done` 在所有文档中保持一致，未被任何功能模块替换或绕过。Codex.app 已从"主执行工具"降级为"产品体验参考"，executor 列表已正确反映当前实际工具链。核心架构思路是正确的。

主要问题集中在：**各阶段新增的数据模型从未回写到 `hermes-desktop-state-model.md`**，导致权威状态定义分散在 8 份不同文档中，进入实现时会产生歧义。

---

## 二、P0 必须修

### P0-1：状态模型分散，缺乏单一权威来源

**问题**：`hermes-desktop-state-model.md` 是 v0.1/v0.2 时期写的，此后在各阶段文档中陆续新增的模型从未合并回去：

| 新增模型 | 定义位置 | state-model.md 中 |
|---|---|---|
| `WorkspaceContext` | workspace-context-injection.md | ❌ 缺失 |
| `AgentRun.user_prompt` / `prompt_snapshot` / `context_include_flags` | workspace-context-injection.md | ❌ 缺失 |
| `AgentRun.run_type` / `parent_run_id` / `review_status` / `qa_status` | review-qa-agent-chain.md | ❌ 缺失（只有 `qa_run_id` 扩展点） |
| `ReviewFinding` | review-qa-agent-chain.md | ❌ 缺失 |
| `QaResult` / `QaRisk` | review-qa-agent-chain.md | ❌ 缺失 |
| `InboxItem` / `TaskDraft` / `InboxResultCallback` | external-inbox.md | ❌ 缺失 |
| `ReviewStatus` / `QaStatus` enum | review-qa-agent-chain.md | ❌ 缺失 |
| `AgentRun.review_run_id` | review-qa-agent-chain.md | ❌ 缺失（只有 `qa_run_id`） |

**后果**：实现时以哪份文档为准？不同开发者读不同文档，会出现字段名冲突（如 `review_run_id` vs `qa_run_id` 命名不对称）。

**修复**：在 Phase 1 实现开始前，将上述所有模型合并到 `hermes-desktop-state-model.md` 第二版，各阶段文档引用 state-model.md，不独立定义新字段。

### P0-2：`TaskSource` 与 `InboxSource` 枚举不一致

**问题**：
- `hermes-desktop-state-model.md` 中 `TaskSource = 'desktop' | 'feishu' | 'api' | 'cron'`
- `external-inbox.md` 中 `InboxSource = 'manual' | 'cli' | 'feishu' | 'discord' | 'scheduler'`

两者不对齐：
- `cron` vs `scheduler`：同一概念两个名字
- `api` vs `cli`：含义相近但不等同（api 可以是任意 HTTP 调用，cli 是特定的 hermes CLI）
- `discord` 在 InboxSource 中存在，在 TaskSource 中缺失
- `manual` 在 InboxSource 中存在，在 TaskSource 中对应 `desktop`

**后果**：Task Thread 创建后 `source` 字段无法从 InboxItem 自然映射过来，要么转换逻辑复杂，要么字段含义模糊。

**修复**：统一枚举，建议：
```
TaskSource = 'desktop' | 'cli' | 'feishu' | 'discord' | 'api' | 'scheduler'
```
`InboxSource` 与 `TaskSource` 共用同一枚举，`manual` → `desktop`，`cron` → `scheduler`。

### P0-3：`streamEvents` 终止契约尚未在 state-model 或 orchestrator 文档中落实

**问题**：`multi-executor-adapter-design.md` 中 P0-1 已指出「streamEvents 必须以 failed event 结束，不能静默结束」，但 `agent-adapter-layer.md` 接口定义中**仍未写入此约束**（本次 review 读取的版本中该约定不在接口注释里）。

**后果**：实现 ClaudeCodeAdapter / CodexCliAdapter 时开发者可能不知道此约束，子进程崩溃后 UI timeline 静默停止。

**修复**：在 `AgentExecutorAdapter.streamEvents` 的接口注释中明确写入：
> 必须以 `{type: "failed"}` event 结束（非正常退出时），不允许静默结束迭代。

---

## 三、P1 应该修

### P1-1：`Trae` 在工具链中出现，但架构文档中完全没有定义其角色

**问题**：任务背景中提到 `Trae：本地 UI 调试`，但 8 份架构文档中没有任何对 Trae 的说明——它是 executor 吗？是开发工具？是 UI 框架？是 Electron 替代方案？

**后果**：如果 Trae 是技术栈选择（如替代 Electron 的 desktop UI 框架），那它影响 Electron typed bridge、IPC 设计等所有工程层面的决策，但这些决策在文档中是空白。

**修复**：在 ADR 中补充技术栈决策（B1 问题，Phase 0 review 时已标注为"Phase 1 开始前必须确认"，至今未定），明确：
- Trae 是什么（UI 调试工具 / IDE / desktop 框架）
- 它在架构中的位置（开发辅助 vs 运行时依赖）
- 是否影响 Electron typed bridge 设计

### P1-2：Review / QA Run 的"禁止写文件"约束只在文字中，没有在 ExecutorConfig 中定义字段

**问题**：`review-qa-agent-chain.md` 规定「executor config 禁用 write_file / edit_file 工具，或 Orchestrator 拦截」，但 `hermes-desktop-state-model.md` 中的 `ExecutorConfig` 没有 `disabled_tools` 字段，`run-orchestrator.md` 没有拦截逻辑说明。

**后果**：实现时没有字段可写，约束只存在于 review 文档的文字里，容易被遗漏。

**修复**：`ExecutorConfig` 增加 `disabled_tools?: string[]` 字段；`Orchestrator.createRun` 文档说明 `run_type = 'review' | 'qa'` 时自动填入 `['write_file', 'edit_file', 'create_file']`。

### P1-3：Worktree branch 命名规则与 `AgentRun.run_seq` 字段不对称

**问题**：`worktree-parallel-runs.md` 定义 branch 命名为 `hermes/<thread_id_short>/<run_seq>`，其中 `run_seq` 是「该 thread 下的 run 序号」。但 `hermes-desktop-state-model.md` 的 `AgentRun` 字段列表中**没有 `run_seq` 字段**。

**后果**：branch 命名依赖的 `run_seq` 从哪里来？是 `AgentRun` 的 DB 自增序号？还是 Orchestrator 计算？不清楚，实现时会出现命名冲突风险。

**修复**：`AgentRun` 增加 `run_seq: number`（在同一 thread 内单调递增，由 Orchestrator 分配），明确 branch 命名依赖此字段。

### P1-4：Router 规则引擎中 `hermes-local` 的优先级说明与 semi-auto-executor-router.md 标题不一致

**问题**：`semi-auto-executor-router.md` 规则匹配顺序第 1 条：「精确匹配 Hermes 内部关键词 → hermes-local（最高优先级）」。但第 5 条的任务类型描述是「Hermes 内部流程 / adapter / scheduler」，而关键词列表包含 `scheduler`——这与 `InboxSource.scheduler` 重叠，可能导致调度任务被路由到 `hermes-local` 而不是让用户在 Inbox 确认。

**修复**：`scheduler` 从 Router 关键词列表中移除（Scheduler 来源的任务通过 Inbox 流程，不走 Router 推荐），或在 Router 中增加：「来源为 `scheduler` 的 InboxItem 转化为 Task Thread 后，由用户在 Convert 对话框中选择 executor，不走 Router 自动推荐」。

### P1-5：`workspace-context-injection.md` 中 `recent_tasks` 与 `InboxItem` 未打通

**问题**：`WorkspaceContext.recent_tasks` 由「Orchestrator 在 task done 时自动追加」，内容包括 `thread_id`、`title`、`executor`、`status`、`completed_at`、`summary`。

但 External Inbox 的 result callback 也有 `summary` 字段。两者的 `summary` 是同一个字段吗？`recent_tasks.summary` 从哪里来——是 run 的 `error_summary`，还是 result callback 的 `summary`，还是需要 agent 主动生成？

**修复**：明确 `recent_tasks.summary` 的来源：优先取 `AgentRun.error_summary`（failed 时）或 `ReviewDecision.comment`（done 时），若两者为空则为 null。不依赖 agent 生成，不消耗 token。

---

## 四、P2 后续修

### P2-1：`WorkspaceContext` 没有版本/变更历史

`context.yaml` 纳入 git，但若用户修改了 `architecture_notes`，已完成的 run 的 `prompt_snapshot` 中记录的是旧版 context。Review/QA 时如果读取最新 context，与 run 实际执行时的 context 不一致，可能误判。

**建议**：`AgentRun.context_snapshot` 存储本次 run 时 `context.yaml` 的 git blob hash，方便复现时对比。

### P2-2：`InboxItem.expires_at` 过期后的清理策略未定义

`external-inbox.md` 定义了 `expires_at` 和 `status = 'expired'`，但没有说明：过期检测是轮询还是 event-driven？过期 item 何时从 DB 删除？过期通知是否回写给来源（如通知 Feishu 消息已过期）？

**建议**：明确 Orchestrator 在 `createRun` 或应用启动时做一次过期扫描，不做后台轮询；过期 item 保留 30 天后归档，不立即删除；不主动回写给来源（避免 Feishu bot 权限问题）。

### P2-3：`deepseek-tui` 的 `ui_fidelity: low` 在 UI 中的具体降级表现未定义

`multi-executor-adapter-design.md` 提出 `ui_fidelity: 'full' | 'low'`，但没有说明 `low` 时 UI 具体降级什么：ToolCallCard 隐藏？还是只显示 log stream？ReviewBar 是否出现？Changed Files 是否基于 git diff 生成？

**建议**：在 `ExecutorManifest` 文档中补充：`ui_fidelity: low` 时，ToolCallCard 不渲染（只显示 log events），ReviewBar 仍出现（基于 run status），Changed Files 基于 adapter 生成的 diff event（git diff）。

### P2-4：Review / QA run 的 worktree 策略与主 run merge 时序存在竞争条件

`review-qa-agent-chain.md` 规定「review/qa run 复用 main run 的 worktree（只读访问）」。但用户可能在 review run 还在执行时就点击 **Accept（Merge）**，此时 Orchestrator 开始 `git worktree remove`，而 review run 还在读取 worktree 内文件。

**建议**：Orchestrator 在 `merging` 状态时检查是否有 running 状态的 review/qa run；若有，阻止 merge 并提示「等待 review 完成」，或显示 `[强制 merge]` 需二次确认。

### P2-5：Codex.app 降级状态需在 ADR 中正式记录

当前 `agent-adapter-layer.md` 用删除线 `~~codex-app~~` 标注不可用，`semi-auto-executor-router.md` 同样删除线标注。但 ADR（`ADR-codex-like-agent-workbench.md`）的背景和决策部分仍将 Codex.app 描述为参照体验，没有补充「Codex.app 暂不可用，当前以 Codex CLI 替代其 executor 角色，产品体验参考仍然有效」的说明。

**建议**：在 `ADR-codex-like-agent-workbench.md` 末尾追加一段修订记录：
> 2026-06-04 更新：Codex.app 暂不可用。Codex CLI（`codex-cli`）承接其 executor 角色，产品体验参考（三栏 workbench、timeline 聚合、review gate）仍然有效。

---

## 五、确认符合要求的设计点

以下检查项确认通过，无需修改：

| 检查项 | 结论 |
|---|---|
| 主链路一致性 | ✅ 所有 8 份文档的流程终点均为 Done/Reject，无模块替换主链路 |
| UI 不直接耦合 executor | ✅ UI → Orchestrator → AdapterRegistry，executor 细节在 adapter 层封装 |
| 自动执行绕过确认 | ✅ Router 只推荐不执行；Inbox 确认后只创建 draft Task Thread，不自动 createRun；Review/QA 手动触发 |
| 外部入口透明性 | ✅ raw_payload 不直接污染 prompt；suggested_prompt 用户可编辑后才使用；所有入口通过 /v1/inbox，需要 API key |
| Worktree 创建条件 | ✅ 主仓库有未提交变更时拒绝创建，不静默处理 |
| Discard 不可逆保护 | ✅ Discard 前弹出确认对话框，显示将丢弃文件摘要 |
| Review/QA 禁止自动改代码 | ✅ 文字约束明确，P1-2 要求补充到字段定义 |
| Codex.app 降级 | ✅ executor 列表已正确反映当前工具链，codex-app 标注不可用 |
| Trae 作为调试工具 | ⚠️ 未在架构文档中定义（P1-1） |
