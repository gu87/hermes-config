# Hermes Desktop Codex-like 升级路线图

目标体验：

```text
Project -> Task Thread -> Agent Run -> Logs / Tool Calls / Diff -> Review -> Continue / Accept / Done
```

路线原则：

- 产品设计参考 `NousResearch/hermes-agent/apps/desktop`。
- 工程边界参考 `fathah/hermes-desktop`。
- 后端能力优先复用当前 Hermes。
- v0.1 只做最小闭环，不做完整桌面生态。
- 不复制外部仓库代码，只吸收设计与架构经验。

## 观察到的产品结构

三份审计给出的现状判断：

- 官方 desktop：最像 Codex.app，三栏 workbench + status bar + agent/tool/diff trace。
- 社区 desktop：工程分层成熟，Electron typed bridge、session cache、Kanban、Gateway 管理可借鉴。
- 当前 Hermes：UI 是 ops dashboard，但后端已有 run/event/approval/session/task/managed-agent 基础。

目标结构：

```text
Hermes Desktop Workbench
├── Left Rail: Project / Task Thread
│   ├── workspace groups
│   ├── running tasks
│   ├── waiting review
│   └── done/history
├── Center: Task Thread / Agent Run Timeline
│   ├── prompt
│   ├── assistant output
│   ├── reasoning
│   ├── tool calls
│   ├── tool results
│   ├── logs
│   ├── diff events
│   └── review checkpoints
├── Right Rail: Files / Diff / Logs / Artifacts / Terminal
├── Bottom Status Bar
│   ├── gateway
│   ├── active agent
│   ├── run timer
│   ├── model/context
│   └── review state
└── Overlays: Command Center / Agents / Gateway / Settings
```

## 可借鉴点

### 从官方 desktop 借鉴

- 第一屏就是当前任务 thread。
- cwd/workspace 作为轻量 Project。
- 左侧按 workspace/session/task 分组。
- 中间把 message、reasoning、tool、diff、subagent 统一成 run timeline。
- 右侧固定承载 preview/files/terminal/logs/diff。
- 底部 status bar 处理 gateway、agent、model、context、计时。
- Tool call 产品化，不裸露 raw JSON。
- Agents overlay 展示 spawn tree 与状态。

### 从社区 desktop 借鉴

- Electron main/preload/renderer 分层。
- typed `window.hermesAPI`。
- 主进程读取本地 DB、日志、进程状态。
- renderer 消费结构化数据。
- session cache/search。
- Kanban task/run/event 读取。
- Gateway/Settings 作为 secondary surfaces。

### 从当前 Hermes 保留

- `/v1/runs`、`/events`、approval、stop。
- managed agents。
- workspace/session binding。
- review gate。
- kanban/task/run。
- Feishu/API 多入口。
- Codex runtime transport。
- dashboard ops 能力。

## 不适合照搬点

- 不照搬官方 runtime installer/updater。
- 不照搬官方 gateway event contract。
- 不照搬社区多页面导航 IA。
- 不把 Gateway/Provider/Settings 放在主屏。
- 不在 v0.1 做远程/SSH/安装器。
- 不把 task 压缩成 chat session 或 todo。
- 不把 logs 做成与 run 无关的文本流。

## 对 Hermes Codex-like 改造的影响

改造应分两条线：

1. 产品线：把所有对象围绕 task thread 重排。
2. 工程线：建立 desktop UI 与 Hermes 后端之间的 typed bridge。

建议最小数据契约：

```text
Project
- id
- name
- path
- branch
- dirty_state

TaskThread
- id
- project_id
- title
- status
- source
- last_run_id
- updated_at

AgentRun
- id
- thread_id
- status
- agent
- started_at
- ended_at
- review_state

RunEvent
- id
- run_id
- type
- status
- title
- body
- payload
- created_at

ReviewDecision
- run_id
- decision: continue | accept | done | reject
- comment
```

## v0.1 最小闭环建议

目标：用户可以在 desktop 中完成一次可观察、可决策的 agent run。

### Phase 0：审计与 ADR

产物：

- 产品/工程审计文档。
- 最小信息架构。
- v0.1 数据契约草案。
- ADR：control-plane first，不以 chat 为主。

验收：

- 明确产品参考、工程参考、保留资产。
- 没有修改业务代码。

### Phase 1：只读 Workbench Shell

范围：

- 新建 desktop workbench shell。
- 左侧 Project/TaskThread rail。
- 中间 RunTimeline。
- 右侧 Logs/Diff placeholder。
- 底部 StatusBar。
- 先从 fixture 或现有 run/event API 读取数据。

验收：

- 能打开一个 task thread。
- 能看到 run timeline。
- 能看到 gateway/run 状态。

### Phase 2：接入真实 Run/Event

范围：

- 接 `POST /v1/runs`。
- 接 `GET /v1/runs/{run_id}`。
- 接 `GET /v1/runs/{run_id}/events` SSE。
- 映射 message/reasoning/tool/log/error/completed。
- 支持 stop。

验收：

- 从 UI 发起一次真实 run。
- timeline 随事件更新。
- run 可停止、失败可见、完成可见。

### Phase 3：Review Loop

范围：

- 渲染 waiting_review。
- 接 `/v1/runs/{run_id}/approval`。
- ReviewBar：Continue、Accept、Done。
- 保留 comment 输入。

验收：

- agent run 进入 review 时 UI 明确停住。
- 用户选择后 run 能继续或结束。

### Phase 4：Tool/Diff 产品化

范围：

- ToolCallCard：compact/default expanded/raw 三层。
- DiffPanel：unified diff。
- event 与 tool/diff 绑定。
- LogsPanel 按 run/tool 分组。

验收：

- 用户能看懂每个 tool 在做什么。
- 用户能看到一次 run 的文件修改摘要。

## v1.0 扩展方向

### 1. Project/Workspace 完整化

- 最近 workspace。
- Git branch、dirty state。
- 项目内 task 搜索。
- workspace scoped settings。

### 2. TaskThread 完整化

- Feishu/API/Desktop/cron 多入口统一 thread。
- thread branch/fork/continue。
- task comments 与 run history。
- waiting review 聚合队列。

### 3. Agent Fleet

- queued/running/completed/failed/interrupted。
- subagent spawn tree。
- agent 读写文件、工具数、token/cost。
- 失败重试与人工接管。

### 4. Review 与 Diff

- accept/reject/partial accept。
- 文件级 diff。
- artifact preview。
- apply 后验证状态。
- needs_changes 反馈回 agent。

### 5. Command Center

- 搜索 task/thread/run/log/artifact。
- 快速跳转 settings/gateway/agents。
- 常用命令。
- 系统诊断。

### 6. Preview Repair Loop

- web/app preview。
- console logs。
- screenshot。
- 将错误一键追加到 current thread。

## 里程碑建议

```text
M0: Phase 0 docs 完成
M1: 只读 workbench shell
M2: 真实 run/event streaming
M3: review loop 可用
M4: tool/diff/log 产品化
M5: project/task 多入口统一
M6: v1.0 agent fleet + command center
```

---

## Phase 5：多执行器 Adapter（v0.3）

**背景**：v0.1–0.2 只有 `hermes-local`。Phase 5 引入 Claude Code CLI 和 Codex CLI 作为可选 executor。

范围：
- `ClaudeCodeAdapter`：子进程 stdout JSON lines 归一化为 RunEvent
- `CodexCliAdapter`：子进程 stdout JSON lines 归一化为 RunEvent
- `AdapterStartResult.git_snapshot`：非 hermes-local executor 在 start 前记录 git HEAD
- streamEvents 结束时追加 adapter 生成的 diff event
- `checkHealth()` 实现：检测 CLI 是否已安装

验收：
- 用户可在 UI 中选择 `claude-code` 或 `codex-cli` 运行一次 task
- timeline 显示工具调用和 diff
- executor 未安装时 status bar 给出提示，不静默失败

---

## Phase 6：Worktree / 并行任务（v0.4）

**背景**：多 task thread 并行执行时文件系统互相污染。

范围：
- `git worktree add` 在 `startRun` 前由 Orchestrator 创建
- branch 命名规则：`hermes/<thread_id_short>/<run_seq>`
- `WorktreeAllocation` 状态机：not_created → creating → ready → dirty → merging → merged / discarded / failed
- 跨 thread 并行上限：`max_parallel_runs`（默认 3）
- Review Bar 增加 **Merge** / **Discard** 按钮
- Discard 弹出确认对话框，显示将丢弃的文件变更摘要
- Merge 冲突不自动解决，显示冲突文件列表
- Changed Files panel 显示 worktree diff，merge 后切换为 main repo diff

验收：
- 两个 task thread 可以同时 running，各自在独立 worktree 执行，文件不污染
- Merge 成功后 worktree 自动清理
- Discard 成功后 branch 删除

---

## Phase 7：半自动 Executor Router（v0.5）

**背景**：Codex.app 暂不可用；Codex CLI、opencode 可用。Hermes Desktop 承担 Codex-like 控制台角色，各 CLI 只是 executor。

范围：
- `OpenCodeAdapter`：opencode CLI 子进程，结构化程度中等
- `DeepSeekTuiAdapter`：非结构化 stdout，仅产出 log events，`ui_fidelity: low`
- `ExecutorManifest.capabilities`：声明 structured_tool_calls / native_diff / review_gate / streaming 模式
- `Router.recommend(prompt, context)` → `RouterOutput`（推荐 + confidence + reason + alternatives + unavailableReason）
- 用户确认对话框：推荐 executor 高亮，可切换，确认后才 createRun
- Router 规则引擎（关键词匹配，无 LLM 消耗）
- Router 不自动执行，不绕过 worktree/review gate

工具分工（当前）：

| 任务类型 | 推荐 Executor | 备选 |
|---|---|---|
| 架构设计 / ADR / 方案 review | `claude-code` | `opencode` |
| 复杂实现 / 大范围重构 | `codex-cli` | `claude-code` |
| 开源 agent 验证 / 备选实现 | `opencode` | `claude-code` |
| 快速 bug scan / small fix | `deepseek-tui` | `opencode` |
| Hermes 内部流程 / adapter | `hermes-local` | `claude-code` |

验收：
- 用户输入 prompt 后弹出 executor 推荐对话框
- 推荐理由一句话，备选可切换
- 推荐 executor 不可用时显示 unavailableReason 和 fallback
- 用户可忽略推荐，直接选其他 executor

---

## Phase 8：Feishu / CLI 外部入口（v0.6）

范围：
- Feishu 发起的 task 出现在 desktop task thread 列表（只读显示 source icon）
- 在 desktop 中对 Feishu task 做 review 决策（Continue/Accept/Done）
- CLI `hermes task create --prompt “...”` 创建 task thread，desktop 中可见
- session binding：外部 thread → desktop TaskThread，状态双向同步

验收：
- Feishu 消息触发的 task 在 desktop 中可见并可 review
- CLI 创建的 task 在 desktop 中可见并可发起 run

---

## Phase 9：Command Center + 可观测性（v0.7）

范围：
- Cmd+K 打开 Command Center：搜索 task/run/log/artifact
- 跨 project 搜索
- run 详情：tokens/cost/耗时/工具数/失败原因
- Status Bar 增加 token/cost 展示
- Run compare：同一 thread 多次 run 的 diff / 工具 / 耗时对比

验收：
- 能在 Command Center 搜到任意历史 task
- 能对比同一 thread 的两次 run 结果

---

## Phase 10：Review / QA Agent（v0.8）

范围：
- run completed 后可触发 QA agent run（用户手动触发，不自动）
- QA agent run 产出 review report（结构化问题列表）
- 用户基于 QA report 决定 Continue / Accept / Done
- QA agent 使用独立 worktree，不污染主 run 的 worktree

验收：
- 用户能一键触发 QA review
- QA 结果作为 run event 展示在 timeline 中
- QA 失败不阻塞主 run 的 Accept

---

## Phase 11：全自动化路由（v1.0，需独立决策）

以下能力有价值，但引入时机和安全边界需单独 ADR：

- **自动 commit / push / PR**：需明确 review 豁免条件和 rollback 机制
- **Feishu / Discord 自动执行**：无人工节点，需策略控制和风险限制
- **LLM-backed Router**：用小模型替代关键词规则，处理复杂 prompt
- **团队规则覆盖**：`.hermes/router-policy.yaml` 覆盖默认推荐规则
- **复杂 Scheduler**：长期任务、周期任务、依赖链

---

## 结论

Hermes Desktop 升级不应从”做一个更好看的聊天客户端”开始，而应从”让 agent run 可观察、可审查、可继续”开始。只要 v0.1 跑通 Project -> Task Thread -> Agent Run -> Timeline -> Review，这条路就立住了。

Phase 7 完成后，Hermes Desktop 成为真正的 Codex-like 控制台：Hermes 承担任务调度和 review 控制面，Claude Code CLI / Codex CLI / opencode / DeepSeek TUI 作为可替换的执行后端，用户保持完整的审查和控制权。
