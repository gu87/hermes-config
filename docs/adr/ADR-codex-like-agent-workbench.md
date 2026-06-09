# ADR: Hermes Desktop 定位为 Codex-like Agent Coding Workbench

状态：已接受
日期：2026-06-03
作者：Gu

---

## 背景

当前 Hermes 客户端是一个运维 dashboard（Gateway Status、Live Log、Config Editor），而后端已具备完整的 agent run 控制面：`/v1/runs`、events SSE、approval gate、managed agents、session binding、kanban/task/run、Feishu 多入口。

UI 与后端能力严重不匹配：后端可以运行、观察、审查 agent 任务，前端只能管理配置。

同期，Codex.app 证明了"Agent Coding Workbench"的产品形态：用户的工作单元是任务，不是对话；界面围绕一次 agent run 的轨迹（工具调用、文件变更、决策节点）组织，而不是聊天泡泡列表。

---

## 决策

**将 Hermes Desktop 改造为 Codex-like Agent Coding Workbench。**

产品骨干：
```
Project → Task Thread → Agent Run → Timeline（message/tool/diff/log） → Changed Files → Review → Continue / Retry / Accept / Done
```

技术策略：
- 信息架构参考 NousResearch hermes-agent/apps/desktop（三栏 workbench + status bar）
- 工程分层参考 fathah/hermes-desktop（Electron typed bridge + session 历史重建）
- 数据模型和 event contract 以当前 Hermes 后端为权威，不照搬外部仓库
- v0.1 后端 API 全部复用已有端点，不新建
- v0.1 必须包含 run history 摘要、Retry、Continue、Changed Files、Open in Editor，否则会退化成“带 SSE 的聊天 UI”

---

## 为什么先做最小闭环（v0.1）

**可验证性**：主链路（发起 → 观察 → 决策）能跑通，产品假设才能被验证。过早加功能会掩盖主链路是否真的可用。

**风险控制**：Hermes 后端 event schema 尚未完全稳定。v0.1 先用 fixture 驱动开发，再接真实 API，避免 UI 与后端 schema 同时变动。

**已有资产保护**：当前 Hermes kanban/task/run/review_gate/session_binding 是真实后端资产，v0.1 的目标是把它们通过新 UI 展示出来，而不是重建。工作量比"重写桌面端"小得多。

**防止范围蔓延**：多 agent fleet、自动 commit/push、Feishu 自动执行每一项都有明确价值，但加入 v0.1 会让验收标准模糊，延长交付周期，且在主链路未稳定时引入不可控依赖。

---

## 为什么最小闭环不是最终目标

v0.1 只能处理单 project、单 run、人工触发的场景。Hermes 的真实优势在于：

- **多入口**：Feishu、Discord、CLI、API、cron 都能发起任务，在 desktop 中统一 review
- **多执行器**：Codex runtime、standard agent、自定义 executor 可以按任务类型路由
- **worktree 并行**：多个 task 跑在独立 git worktree，互不干扰
- **review agent**：run 完成后自动触发 QA agent，结果供人工确认，减少人工 review 负担
- **半自动 router**：任务根据规则自动分配执行器，人工只做异常介入

这些能力把 Hermes 从"手动触发的 Codex.app"升级为"有监督的自动化编码系统"。v0.1 的架构设计必须为这些扩展留好接口，而不是把它们堵死。

---

## 后续扩展路线

### v0.5（单 run 产品化）
- Tool Call 三层展示（compact / expanded / raw）
- Diff panel 文件级展示，按 run 分组
- 历史 Task Thread 从本地 DB 重建完整 timeline（v0.1 只保留 run history 摘要）
- 多 task 切换（不离开 workbench）
- Session Binding：显示任务来源（Feishu / API / Desktop / cron）
- Open in Editor 支持行号和 diff hunk 定位
- Reject / needs changes 进入结构化 review 流程

### v1.0（多 project + 自动化基础）
- 多 Project / workspace 管理
- 多执行器切换（Codex runtime / standard agent）
- worktree 支持：并行任务在独立 git worktree 运行
- 并行任务 + Agent Fleet 视图（queued / running / failed）
- 半自动 router：任务自动分配执行器，人工确认前不执行
- Review / QA agent（run 完成后触发，结果供人工确认）
- Feishu / Discord / CLI 外部入口：任务在 desktop 中 review
- Command Center：跨 task/run/log 搜索
- Run compare：同一 Task Thread 下多次 run 的 diff、工具、耗时和结果对比

### v1.x（全自动化，需独立决策）
以下能力有价值，但引入时机和安全边界需要单独讨论：
- 自动 commit / push / PR（需要明确 review 豁免条件）
- Feishu / Discord 自动执行（无人工 review，需要策略控制）
- 复杂 Scheduler（长期任务、周期任务、依赖链）
- 长期记忆管理（跨 session 上下文持久化）

---

## 不做什么

以下在本 ADR 范围内明确排除：

| 排除项 | 原因 |
|---|---|
| 全自动多 Agent 调度（v0.1） | 主链路未稳定，自动调度失败无法被用户感知和干预 |
| 自动 commit / push / PR | 需要独立的 review 豁免策略，不在 workbench 基础范围内 |
| Feishu / Discord 自动执行 | 无人工节点的自动化需要独立风控设计 |
| 复杂 Scheduler / cron（v0.1） | 调度逻辑与 workbench 主链路独立，优先级低 |
| 长期记忆管理 | 需要独立的 memory schema 设计，不属于 UI 改造范围 |
| 把 task 压缩成 chat session | 退化为聊天客户端，丢失 Hermes 已有的 task/run/review 优势 |
| 复制外部仓库的 gateway event contract | Hermes 有自己的 `/v1/runs/events` schema，不应引入双 schema |
| v0.1 做 Agent Fleet / spawn tree 视图 | 需要稳定的单 run timeline 作为前提 |
| v0.1 做完整文件树/IDE | 只需要 Changed Files + Open in Editor，完整文件管理放到 v0.5+ |
| v0.1 做 partial diff apply | 容易把范围扩成代码 review 工具，先只做观察和人工接受 |

---

## 风险与规避

### R1. RunEvent schema 不稳定导致 UI 重写
**风险**：`/v1/runs/{run_id}/events` 的 event type 枚举在后端迭代中变化，导致 timeline 渲染逻辑频繁调整。

**规避**：Phase 1 用 fixture 驱动开发（定义 mock event stream），UI 层对未知 event type 有 fallback 渲染（显示 raw JSON），不因新 event type 崩溃。event schema 变更时只需更新对应 event renderer，不需要重写 timeline。

### R2. Kanban task schema 与 TaskThread 需求不匹配
**风险**：当前 kanban task 缺少 `source`、`last_run_id` 等字段，Phase 2 接入真实数据时 schema 不匹配需要后端改动。

**规避**：Phase 1 前完成 kanban task schema 审计，明确缺失字段列表。v0.1 的 TaskThread 对象在前端做适配层，不直接把 kanban task 结构暴露给 UI 组件。

### R3. Review Gate 触发机制不明确
**风险**：`review_gate` 是 SSE push 还是需要前端轮询，影响 ReviewBar 实现。

**规避**：Phase 1 实现前确认 `approval_needed` event 是否通过 SSE 推送。如不确定，先实现轮询 `/v1/runs/{run_id}` 检查 `review_state`，后续迁移到 SSE push。

### R4. 过早多 Agent 化的设计压力
**风险**：开发过程中因为"Hermes 支持多 agent"的背景知识，导致 v0.1 实现中不断加入 agent fleet、spawn tree、跨 run 视图等需求，延迟主链路交付。

**规避**：本 ADR 明确：v0.5 前只显示单 run 内的 tool call，不展示 agent spawn tree；Agent Fleet overlay 属于 v1.0。任何多 agent 可视化需求在 v0.5 review 时统一评估。

### R5. v0.1 退化为普通聊天 UI
**风险**：如果中心区域只显示消息与流式文本，右侧没有 changed files/diff，底部没有 review state，用户会把 Hermes Desktop 当作普通聊天客户端。

**规避**：v0.1 验收必须检查四个不可缺项：Run Timeline、Changed Files、ReviewBar、Run History。缺任一项都不能标记为 Codex-like MVP。

### R6. 技术栈选择影响工程边界
**风险**：如果 v0.1 选择增强现有 web dashboard（Python + HTML），后续 Electron 化成本高；如果直接做 Electron，v0.1 启动成本高。

**规避**：本 ADR 不锁定技术栈，但要求 Phase 1 开始前通过单独决策确认（Electron vs web-first），并在该决策中评估 Electron typed bridge 的引入时机。

---

## 验收标准

### v0.1 验收

**用户视角**：
- 打开 desktop，第一屏是当前 project 和 task thread 列表，不是配置面板
- 能选择一个 task，看到它的最近 run 历史（即使只有一条）
- 能输入 prompt 发起新的 agent run
- run 进行中能实时看到 timeline：assistant 输出、工具调用（名称+状态）、日志
- 能看到本次 run 的 changed files；没有文件变更时明确显示空状态
- 能从 changed files 打开 diff，并能 Open in Editor 查看真实文件
- run 到达 review checkpoint 时，UI 明确暂停，ReviewBar 出现
- 能点击 Continue / Accept / Done，run 相应继续或结束
- failed / interrupted run 能 Retry，completed run 能 Continue
- 能随时点击 Stop，run 立即停止
- 底部 status bar 显示 gateway 状态、当前 run 状态、model

**工程验收**：
- timeline 对未知 event type 有 fallback 展示，不崩溃
- gateway 离线时 status bar 红色提示，不影响历史 task 列表读取
- run 完成后刷新页面，task 状态正确显示（completed / failed），不依赖内存状态

### v0.5 验收（附加）
- tool call 可展开查看 args 和 result
- diff 在右侧 panel 显示，与 tool call 关联
- 历史 run 的 timeline 可以从本地 DB 恢复，不需要重新运行

### v1.0 验收（附加）
- 可切换多个 project
- Feishu 发起的 task 在 desktop task 列表中可见，可在 desktop 做 review 决策
- 两个 run 可以并行进行（跑在不同 worktree），status bar 和 task list 分别显示各自状态
