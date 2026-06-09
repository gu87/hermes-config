# Hermes Desktop Codex-like Agent Workbench — PRD

版本：0.1-draft
日期：2026-06-03

---

## 一、产品定位

Hermes Desktop 是一个 **Agent Coding Workbench**，不是聊天客户端，不是运维控制台。

用户的工作单元是"任务"，不是"对话"。Hermes 负责把一个任务从发起、执行、观察、决策，到完成，组织成一条可追踪的轨迹。

参照体验：Codex.app。核心差异：Hermes 有更强的 review gate、managed agents、多入口绑定能力，这些是产品优势，不应在改造中削减。

---

## 二、目标用户

独立开发者或小型团队中、需要让 AI agent 执行真实代码任务、并保持人工审查控制权的工程师。

核心需求：
- 知道 agent 在做什么（可观察）
- 能在关键节点介入（可审查）
- 任务历史可回溯（可追踪）
- 不丢失对代码库的控制权（可撤销）

---

## 三、产品主链路

```
Project
  └── Task Thread
        └── Agent Run
              ├── Timeline（message / reasoning / tool call / tool result / log / diff）
              ├── Changed Files（本次 run 修改过的文件）
              └── Review Checkpoint
                    └── Continue / Retry / Accept / Done
```

这条链路是 v0.1 到 v1.0 的骨干，所有功能围绕它扩展，不替换它。

主链路约束：
- 打开应用后最多两步进入正在运行或等待 review 的任务。
- 发起 run 后不跳页；timeline、diff、changed files、review action 都在同一工作台内完成。
- 配置、模型、Gateway、日志诊断都是辅助层，不进入主链路。
- 用户的下一步动作必须始终明确：Stop、Continue、Retry、Accept、Done。

---

## 四、核心对象定义

### Project
最小定义：workspace path + name + git branch。
不是复杂数据库，不需要团队/权限/标签。v0.1 支持单 project（当前 cwd），v0.5 扩展到多 project。

### Task Thread
用户想完成的一件事。来自 Desktop 输入、Feishu、API、cron。
一个 Task Thread 可以有多次 Agent Run（重试、继续、分支）。
数据来源：当前 Hermes kanban task，加 `source` / `last_run_id` 字段。

### Agent Run
一次实际执行。状态：`running` / `completed` / `failed` / `interrupted` / `waiting_review`。
后端：`/v1/runs/{run_id}`（已有）。

一个 Task Thread 下必须保留 run history。v0.1 最小实现只要求显示最近 runs 的状态、时间、耗时和失败原因摘要，并支持对 failed/interrupted run 发起 Retry，对 completed/waiting_review 后的同一 thread 发起 Continue。

### Run Event
Run 内的单条轨迹项。类型：
- `message`：用户或 assistant 的文本
- `reasoning`：thinking block，默认折叠
- `tool_call`：工具调用，带 id、name、args、status、duration
- `tool_result`：工具结果，带 stdout/stderr/error/diff
- `log`：系统日志，关联 run/tool
- `diff`：文件变更，绑定 tool_call_id
- `approval_needed`：review checkpoint，阻塞后续执行
- `completed` / `failed`：run 终态

后端：`/v1/runs/{run_id}/events` SSE（已有）。

### Review Decision
`continue` / `accept` / `done` / `reject`，附可选 comment。
后端：`/v1/runs/{run_id}/approval`（已有）。

语义约束：
- `Continue`：把用户补充意见交回当前 Task Thread，继续执行。
- `Retry`：基于同一 Task Thread 和同一 prompt/context 重新发起新的 Agent Run。
- `Accept`：用户接受当前修改结果，但任务未必关闭。
- `Done`：用户确认任务完成，Task Thread 进入 done/completed。
- `Reject`：保留为 v0.2；v0.1 可以只显示 disabled 或放入后续范围，避免造成“能拒绝但不会回滚”的误解。

---

## 五、v0.1 最小闭环范围

v0.1 目标：用户能在 desktop 中走完一次完整的 agent run，从发起到 review 决策。

### 必须有

| 功能 | 说明 |
|---|---|
| 当前 Project 显示 | workspace path、git branch、gateway 状态 |
| Task Thread 列表 | 来自 kanban task，显示 title、status、last run 时间 |
| 发起 Run | 输入 prompt，POST /v1/runs |
| Run Timeline | 消费 SSE events，渲染 message/reasoning/tool/log/diff |
| Tool Call 展示 | 至少：名称、状态、摘要；可展开 args/result |
| Diff 展示 | unified diff，绑定 tool call |
| Changed Files | 显示本次 run 修改过的文件、增删统计、打开 diff |
| Open in Editor | 从 Changed Files 打开本地编辑器定位文件 |
| Run History | 当前 Task Thread 最近 runs，显示状态、耗时、失败原因 |
| Review Bar | waiting_review 时显示，提供 Continue/Accept/Done |
| Retry / Continue | failed/interrupted 可 Retry；completed/waiting_review 后可 Continue |
| Stop Run | 随时可停 |
| Gateway 状态 | 底部 status bar，复用 /api/status |

### 明确不做（v0.1）

- 全自动多 Agent 调度
- 自动 commit / push / PR
- Feishu / Discord 自动执行（外部入口只读显示来源）
- 复杂 Scheduler / cron
- 长期记忆管理
- 多 project 切换
- Agent spawn tree / fleet 视图
- Diff accept/reject/partial apply
- Command Center 搜索
- Preview / web / screenshot repair loop
- 文件树完整浏览（v0.1 只做 changed files，不做完整 IDE 文件管理）
- 自动回滚 / stash / commit

---

## 六、v0.5 扩展范围

在 v0.1 单 run 闭环稳定后：

- Tool Call 三层展示（compact / expanded / raw）
- Diff panel：文件级 diff，按 run 分组
- 历史 Task Thread 深度重建（从本地 DB 恢复完整 timeline；v0.1 只要求 run history 摘要）
- 多 task 切换（不离开 workbench）
- Workspace context 显示（文件树、最近修改）
- Session Binding：显示任务来源（Feishu/API/Desktop/cron）
- Open in editor 支持行号、diff hunk 定位
- Reject / needs changes：把用户反馈作为下一次 Continue 的结构化输入

---

## 七、v1.0 扩展范围

- 多 Project / workspace 管理
- 多执行器：切换 Codex runtime / standard agent / custom executor
- worktree 支持：并行任务跑在独立 git worktree
- 并行任务：多个 run 同时进行，Agent Fleet 视图
- 半自动 router：任务自动分配执行器，人工确认前不执行
- Workspace context 深度集成：文件树、terminal、artifact preview
- Review / QA agent：run 完成后自动触发 review agent，结果供人工确认
- Feishu / Discord / CLI 外部入口：任务从外部发起，在 desktop 中 review
- Command Center：搜索 task/run/log/artifact
- 成本 / token / 耗时可观测性
- Run compare：比较同一 Task Thread 下多次 run 的 diff、工具和结果

---

## 八、用户旅程（v0.1）

```
1. 打开 desktop → 看到当前 project + task 列表
2. 选择或新建一个 task
3. 输入 prompt，发起 run
4. 实时看到 timeline：assistant thinking → tool calls → file changes
5. run 到达 review checkpoint → ReviewBar 出现，run 暂停
6. 用户审查 diff、changed files 和 tool 输出
7. 必要时点击 Open in Editor 查看真实文件
8. 点击 Continue（补充要求继续）/ Retry（失败重跑）/ Accept（接受修改）/ Done（完成）
9. run 继续、重试或结束
10. 任务状态更新为 completed / done，run history 保留本次结果
```

---

## 九、非功能要求

- v0.1 timeline 渲染延迟 < 500ms（SSE 到 UI 显示）
- Review bar 在 `approval_needed` event 后 < 1s 出现
- gateway 离线时 status bar 明确提示，不静默失败
- 历史 task/run 在 gateway 重启后可恢复（来自本地 DB，不依赖 runtime state）
- Changed Files 为空时必须明确显示“本次未修改文件”，避免用户误以为 diff 丢失
