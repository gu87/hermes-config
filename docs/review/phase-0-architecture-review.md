# Phase 0 架构复核报告

复核日期：2026-06-03
复核对象：docs/research/ 四份审计 + docs/roadmap/hermes-desktop-upgrade-roadmap.md

---

## 一、同意的结论

### 1. 产品参考 vs 工程参考的分工是对的

官方 desktop（NousResearch）作为产品设计参考，社区 desktop（fathah）作为工程实现参考，这个分工准确。两者混用会导致决策混乱——前者的 IA 优秀但工程细节不适合直接复制，后者反之。

### 2. 当前 Hermes 的核心价值在后端，不在 Dashboard UI

`/v1/runs`、`/events`、approval、managed agents、session binding、review gate、Kanban bridge、codex runtime transport 这些后端资产的判断是准确的。Dashboard 作为 ops console 保留，而不是作为主 IA，这是正确决策。

### 3. v0.1 主链路定义是对的

```
Project → Task Thread → Agent Run → Logs/Tool Calls/Diff → Review → Continue/Accept/Done
```

这条链路清楚，有终点，可以验收。

### 4. Codex-like 核心不是 UI 皮肤，而是信息聚合

工具调用产品化（ToolCallCard 三层展示）、diff 绑定 tool call 而非独立页面、timeline 聚合所有 run 事件——这些判断都是对的，也是与普通聊天客户端的本质区别。

### 5. 不把 task 压缩成 chat session 或 todo 工具

Hermes 已有 kanban/task/run 模型，保留并升级而不是退化为 OpenAI-compatible chat 流，这个方向是正确的。

---

## 二、不同意的结论

### 1. 对官方 desktop 的参考价值略有高估

审计文档把官方 desktop 的架构几乎全盘接受为"Codex-like 的正确答案"。但官方 desktop 是为独立发行设计的——它的 session/workspace 模型、event contract、subagent overlay 都深度绑定了它自己的 gateway JSON-RPC 协议。

Hermes 的核心模型（managed agents、review gate、session binding）比官方 desktop 的 session+message 模型更复杂、更正确。直接映射官方 desktop 的对象（stored session → TaskThread）有压扁 Hermes 优势的风险。

**修正建议**：官方 desktop 只参考信息架构（三栏 + status bar + timeline 聚合），不参考其对象模型和 event contract。

### 2. 社区 desktop 的工程参考价值被低估了一个关键点

审计文档主要推荐社区 desktop 的 Electron typed bridge，但遗漏了它最有实际价值的一点：**`sessions.ts` 的历史重建模式**——从本地 DB 重建 reasoning/tool_call/tool_result 为 timeline item。

Hermes 没有现成的 desktop timeline 历史恢复机制，这个模式对 v0.1 的 Phase 1（只读 workbench shell）有直接落地价值，应该更明确地列为工程借鉴优先项。

### 3. v0.1 → v1.0 的 Agent Fleet 路径跳跃过大

roadmap 的 v1.0 扩展方向直接包含了"Agent Fleet（queued/running/failed/interrupted/spawn tree/跨 run 历史）"。这相当于在 v0.1 还没有稳定的单 run timeline 的情况下，v1.0 就需要跨 run 的多 agent 管理控制面。

中间缺少一个明确的 v0.5 层次：单 run 内的 tool call/diff 产品化稳定之后，才引入 agent fleet 视图。否则 v1.0 范围会过早膨胀。

---

## 三、必须修正的点

### M1. 明确区分"产品设计基准"和"代码改造底座"

当前审计文档在同一段落内混用两个概念。建议在进入 Phase 1 之前，用一张表显式声明：

| 决策类型 | 参考来源 | 不参考来源 |
|---|---|---|
| 信息架构（三栏、timeline、status bar） | 官方 desktop | 社区 desktop |
| 工程分层（Electron bridge、typed API） | 社区 desktop | 官方 desktop |
| 数据模型（Task/Run/Event/Review） | 当前 Hermes 后端 | 两个外部仓库 |
| Event contract | 当前 `/v1/runs/events` | 官方 gateway JSON-RPC |

这张表不存在于任何一份审计文档中，但它是 Phase 1 实现时最容易产生分歧的地方。

### M2. 补充当前 Hermes 已有能力的完整清单，并在 v0.1 中明确利用

以下能力在 my-hermes-current-ui-audit.md 中提到，但在 roadmap 中没有明确说明 v0.1 如何利用：

- **Task Card**：Kanban 的 task/detail UI 已有，应作为左侧 TaskThread 列表的数据来源，而不是重新设计
- **Session Binding**：多入口（Feishu/API/Desktop）已有绑定机制，v0.1 应至少 wire 进来，即使只读
- **Workspace Context**：当前 session 带 cwd，workspace context 读取已存在
- **Status Panel（Dashboard）**：Gateway status、health、model 已有，v0.1 status bar 可直接复用 `/api/status`
- **Outbox / Event Log**：event_log 模块已存在，v0.1 timeline 的数据来源应优先消费它，不应从头设计
- **Review Gate**：approval endpoint 已有，v0.1 ReviewBar 的后端已经存在，不需要新建

这些已有能力在 roadmap 的 Phase 1-4 里被当成"需要新建"处理，实际上 v0.1 的工作量比文档描述的要小。

### M3. 给"Codex-like 主链路"的每个节点标注后端 API 映射

roadmap 定义了主链路，但没有在 Phase 1 验收里标注每个节点用哪个现有 API 承接：

```
Project         → workspace path（已有 session cwd）
Task Thread     → kanban task + latest run（已有 /kanban/tasks）
Agent Run       → /v1/runs/{run_id}（已有）
Logs/Tool/Diff  → /v1/runs/{run_id}/events SSE（已有）
Review          → /v1/runs/{run_id}/approval（已有）
Continue/Accept/Done → approval decision 枚举（已有）
```

不标注这个映射，Phase 1 实现时会出现"要不要新建 API"的争议，实际上不需要新建。

### M4. 修正 v0.1 到 v1.0 的扩展路径

建议插入一个 v0.5 阶段，明确边界：

```
v0.1  单 run 可观察、可决策闭环（主链路）
v0.5  Tool/Diff 产品化 + 历史 thread 重建 + 多 task 切换
v1.0  多 project + Agent Fleet + 多入口 + Command Center
```

当前 roadmap 把 Phase 4（Tool/Diff 产品化）放在 v0.1 范围内，这与"v0.1 只做最小闭环"的原则矛盾。Tool/Diff 产品化应属于 v0.5。

---

## 四、Phase 1 之前必须确认的架构边界

以下问题必须在 Phase 1 开始实现之前得到明确答案，否则会导致实现中途返工：

### B1. Desktop 是 Electron 还是 Web？

当前仓库有 dashboard（纯 web + Python server）和一个潜在的 Electron 路径（社区 desktop 借鉴）。**Phase 1 用哪个技术栈必须先定**。如果是 Electron，typed preload bridge 必须在 Phase 1 建立；如果是增强现有 web dashboard，则 bridge 层设计不同。

### B2. RunEvent schema 的权威定义在哪里？

当前 `/v1/runs/{run_id}/events` 的 SSE 事件类型是否已经稳定？Phase 1 timeline 渲染依赖这个 schema。如果 event schema 不稳定，应先做 fixture-driven 开发，而不是直接接真实 API（roadmap 的 Phase 1 建议也是这样，但需要明确哪些 event type 已经稳定）。

### B3. TaskThread 的数据来源是 Kanban task 还是新建对象？

roadmap 建议 TaskThread 来自 kanban task，但没有明确当前 kanban 的 task schema 是否覆盖 `source`（desktop/feishu/api/cron）、`last_run_id`、`status` 这些字段。Phase 1 之前需要对齐，避免 Phase 1 完成后 Phase 2 接入真实数据时 schema 不匹配。

### B4. Review Gate 的触发条件是前端轮询还是 SSE push？

当前 `review_gate` 是通过 SSE event 推送 `waiting_review` 状态，还是 Phase 1 需要轮询 `/v1/runs/{run_id}` 来感知？这影响 ReviewBar 组件的实现方式。

### B5. 多 Agent 可视化的时机边界

审计文档把 subagent overlay 列为参考点，但 Phase 1-4 没有明确"多 agent 视图从哪个 phase 开始"。建议明确：Phase 1-v0.5 只显示单 run 内的 tool call，不展示 agent spawn tree；v1.0 才引入 Agent Fleet overlay。否则 Phase 1 会有过早多 Agent 化的设计压力。
