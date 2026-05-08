# Hermes 2.8 升级加强任务书

## 任务身份

你现在是 Hermes 项目的高级工程架构师与执行工程师。

你的任务不是简单写方案，而是直接基于当前 Hermes 代码仓库，完成 Hermes 2.8 的工程化升级。

本次升级方向是：

# Harness Engineering

Hermes 2.8 不是单纯增加 Agent 数量，也不是简单优化 Prompt，而是要把 Hermes 升级为一个可执行、可记录、可复盘、可持续演进的智能任务工程系统。

---

# 一、项目背景

Hermes 的目标是成为我的智能秘书型多 Agent 系统。

我并不总是能把任务表达得非常清楚，所以 Hermes 需要承担“秘书型主 Agent”的职责：

1. 理解我不完整、不专业、不结构化的表达；
2. 结合历史上下文判断我的真实意图；
3. 将模糊需求转化为结构化任务；
4. 判断是否需要调用 Agent、模型或 MCP 工具；
5. 把任务分发给最合适的能力模块；
6. 收口不同结果；
7. 进行质量审查；
8. 沉淀阶段总结文档；
9. 记录全过程；
10. 在每个阶段完成后提交 Git。

当前我已经安装：

- firecrawl MCP
- context MCP

请将它们纳入 Hermes 2.8 的 Capability Harness 中。

---

# 二、本次升级总目标

请把 Hermes 2.8 架构为一个完整的 Harness Engineering 系统。

核心链路如下：

```text
User Request
  ↓
Intent Harness
  ↓
Task Harness
  ↓
Capability Harness
  ↓
Execution Harness
  ↓
Review Harness
  ↓
Documentation Harness
  ↓
Git Commit
```

本次升级完成后，Hermes 应该具备以下能力：

```text
用户输入一个模糊任务
→ 系统生成 Intent Card
→ 系统生成 Task Card
→ 系统记录任务事件日志
→ 系统判断是否调用 context MCP / firecrawl MCP / Agent
→ 系统执行任务
→ 系统进入 Review
→ 系统根据验收标准判断是否完成
→ 系统沉淀阶段总结文档
→ 系统提交 Git
```

---

# 三、核心原则

请严格遵守以下原则：

## 1. 不要做一次性大重构

请按 Sprint 分阶段实现。

每个 Sprint 都必须：

- 有明确目标；
- 有新增或修改文件；
- 有验收标准；
- 有阶段总结文档；
- 有 Git commit。

---

## 2. Event Log 必须从 Sprint 1 开始

事件日志不是后置功能。

Task Card 的状态流转必须有地方记录“为什么状态改变”。

所以从 Sprint 1 开始就必须实现 Event Log。

Event Log 至少要记录：

```text
- 任务为什么创建
- 状态为什么变化
- 为什么进入 running
- 为什么进入 reviewing
- 为什么 completed
- 为什么 failed
- 为什么 blocked
- 为什么调用某个 MCP
- 为什么分发给某个 Agent
- 为什么 Review 通过或不通过
```

---

## 3. 每个阶段结束必须沉淀文档

每个 Sprint 完成后，必须生成阶段总结文档。

文档至少包含：

```text
- 当前功能
- 当前架构
- 当前实现细节
- 已知问题
- 下一阶段建议
- Git 提交说明
```

---

## 4. 每个阶段结束必须提交 Git

每个 Sprint 完成后，请执行：

```bash
git status
git add .
git commit -m "<清晰的 commit message>"
```

提交信息必须可读、可追踪。

---

## 5. 主 Agent 是秘书，不是万能执行者

主 Agent 的职责是：

```text
理解意图
拆解任务
选择能力
分发任务
管理状态
收口结果
触发审查
沉淀文档
```

主 Agent 不应该默认什么都自己完成。

---

# 四、目标架构

请围绕以下模块实现 Hermes 2.8。

---

## 1. Intent Harness

### 目标

负责理解用户真实意图，把原始输入转化为 Intent Card。

### 需要实现

```text
- Intent Card schema
- Intent Parser
- Intent Storage
- Intent Event
```

### Intent Card 建议结构

```json
{
  "intent_id": "intent_xxx",
  "created_at": "ISO timestamp",
  "raw_request": "用户原始输入",
  "interpreted_goal": "系统理解后的目标",
  "project_context": [],
  "user_preferences": [],
  "success_criteria": [],
  "ambiguities": [],
  "execution_mode": "direct_answer | research | planning | coding | review | multi_agent",
  "required_capabilities": [],
  "status": "created"
}
```

---

## 2. Task Harness

### 目标

负责把 Intent 转化为可执行任务，并管理任务状态流转。

### 需要实现

```text
- Task Card schema
- Task Manager
- Task Storage
- Task State Machine
- Task Event Log
```

### 状态流转

```text
pending
  ↓
running
  ↓
reviewing
  ↓
completed

异常状态：
failed
blocked
cancelled
```

### Task Card 建议结构

```json
{
  "task_id": "task_xxx",
  "intent_id": "intent_xxx",
  "title": "任务标题",
  "description": "任务描述",
  "status": "pending",
  "priority": "low | medium | high | critical",
  "owner": "main_agent",
  "inputs": [],
  "outputs": [],
  "dependencies": [],
  "acceptance_criteria": [],
  "assigned_capabilities": [],
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

---

## 3. Event Log

### 目标

记录所有关键行为，并说明原因。

### 需要实现

```text
- Event schema
- Event Logger
- JSONL event storage
- Event query helper
```

### Event 建议结构

```json
{
  "event_id": "evt_xxx",
  "timestamp": "ISO timestamp",
  "event_type": "task_created | status_changed | tool_called | agent_delegated | review_started | review_completed | error | document_generated | git_committed",
  "task_id": "task_xxx",
  "intent_id": "intent_xxx",
  "actor": "main_agent | system | mcp | review_agent",
  "from_status": "pending",
  "to_status": "running",
  "reason": "为什么发生这个事件",
  "metadata": {}
}
```

### 注意

Event Log 必须从 Sprint 1 开始实现。

不要把 Event Log 放到 Sprint 4 或更后面。

---

## 4. Capability Harness

### 目标

统一管理 Hermes 可调用的能力。

能力包括：

```text
- Agent
- MCP
- Model
- Internal Tool
```

### 需要实现

```text
- Capability Registry
- Capability Router
- Capability Policy
- Tool Call Event Log
```

### MCP 接入要求

当前已安装：

```text
- firecrawl MCP
- context MCP
```

请实现 MCP registry 和 routing policy。

### firecrawl MCP 使用场景

```text
- 需要抓取网页内容
- 需要研究外部网站
- 需要竞品分析
- 需要公开资料验证
- 需要案例搜索
- 需要行业信息补充
```

### context MCP 使用场景

```text
- 需要读取历史上下文
- 需要继承项目已有资料
- 需要保持方案连续性
- 需要查询用户偏好
- 需要避免重复设计
```

---

## 5. Agent Routing Harness

### 目标

让主 Agent 像秘书一样分发任务，而不是所有任务都自己做。

### 需要实现

```text
- Agent Registry
- Agent Routing Policy
- Delegation Record
- Subtask Card
- Subtask Aggregation
```

### 建议 Agent 角色

```json
{
  "main_secretary_agent": {
    "role": "理解意图、拆解任务、分发任务、收口结果",
    "use_when": ["所有任务入口"]
  },
  "strategy_agent": {
    "role": "策略判断、商业逻辑、品牌方案分析",
    "use_when": ["品牌策略", "商业方案", "传播方案", "营销判断"]
  },
  "writing_agent": {
    "role": "文案优化、结构表达、提案语言",
    "use_when": ["文案", "方案润色", "表达优化"]
  },
  "review_agent": {
    "role": "挑刺、验收、风险识别、质量评估",
    "use_when": ["任务完成前", "方案评审", "质量把关"]
  },
  "code_agent": {
    "role": "代码实现、重构、测试、工程落地",
    "use_when": ["代码任务", "仓库修改", "工程实现"]
  }
}
```

---

## 6. Review Harness

### 目标

所有任务完成前必须进入 reviewing。

Review Harness 根据 acceptance criteria 判断任务是否完成。

### 需要实现

```text
- Review Card schema
- Review Engine
- Acceptance Criteria Checker
- Retry / Failed / Blocked handling
- Review Event Log
```

### Review Card 建议结构

```json
{
  "review_id": "review_xxx",
  "task_id": "task_xxx",
  "reviewer": "review_agent",
  "status": "passed | failed | needs_revision",
  "acceptance_criteria": [],
  "findings": [],
  "risks": [],
  "required_changes": [],
  "decision_reason": "为什么通过或不通过",
  "created_at": "ISO timestamp"
}
```

---

## 7. Documentation Harness

### 目标

每个 Sprint 完成后，自动生成阶段总结文档。

### 需要实现

```text
- Stage Summary Generator
- Current Function Snapshot
- Current Architecture Snapshot
- Implementation Details Snapshot
- Known Issues Recorder
- Next Sprint Recommendation
```

### 每个 Sprint 结束后生成

```text
/docs/stages/sprint-xx/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

### stage-summary.md 模板

```markdown
# Sprint XX 阶段总结

## 1. 本阶段目标

## 2. 本阶段完成内容

## 3. 当前功能

## 4. 当前架构

## 5. 关键实现细节

## 6. 新增/修改文件

## 7. 已知问题

## 8. 下一阶段建议

## 9. 验收结果

## 10. Git 提交说明
```

---

## 8. Git Workflow Harness

### 目标

每个阶段完成后必须提交 Git。

### 需要实现

```text
- Git status check
- Git commit helper
- Commit message convention
- Stage commit record
```

### Commit Message 规范

```text
feat: 新功能
fix: 修复问题
docs: 文档更新
refactor: 重构
test: 测试
chore: 工程杂项
```

### 示例

```bash
git commit -m "feat: add harness foundation schemas and event log"
git commit -m "feat: integrate firecrawl and context mcp"
git commit -m "feat: add agent routing harness"
git commit -m "feat: add review acceptance workflow"
git commit -m "docs: add sprint 01 stage summary"
```

---

# 五、推荐目录结构

请根据当前仓库情况适配，不要机械照搬。

但整体建议如下：

```text
hermes/
  README.md

  docs/
    architecture/
      harness-overview.md
      intent-harness.md
      task-harness.md
      capability-harness.md
      mcp-harness.md
      agent-routing.md
      review-harness.md
      documentation-harness.md

    policies/
      mcp-routing-policy.md
      agent-routing-policy.md
      acceptance-policy.md
      git-commit-policy.md

    schema/
      intent-card.schema.json
      task-card.schema.json
      event-log.schema.json
      review-card.schema.json

    templates/
      stage-summary-template.md
      task-card-template.md
      review-card-template.md

    stages/
      sprint-01/
        01-current-function.md
        02-current-architecture.md
        03-implementation-details.md
        04-known-issues.md
        05-stage-summary.md

  src/
    harness/
      intent_parser.*
      task_manager.*
      event_logger.*
      capability_registry.*
      capability_router.*
      mcp_registry.*
      mcp_router.*
      agent_registry.*
      agent_router.*
      review_engine.*
      doc_generator.*
      git_helper.*

  runtime/
    intents/
      intent-cards.jsonl

    tasks/
      task-cards.jsonl

    reviews/
      review-cards.jsonl

    events/
      task-events.jsonl
      tool-events.jsonl
      agent-events.jsonl
      review-events.jsonl
      system-events.jsonl
```

---

# 六、Sprint 实施计划

请按以下 Sprint 顺序执行。

---

# Sprint 0｜Repository Audit

## 目标

先理解当前 Hermes 仓库，不要直接动手改。

## 需要完成

```text
- 阅读当前项目结构
- 判断技术栈
- 判断已有 Agent 架构
- 判断已有任务系统
- 判断已有日志系统
- 判断已有 MCP 配置
- 判断适合新增代码的位置
```

## 输出文档

```text
/docs/stages/sprint-00/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "docs: add sprint 00 repository audit"
```

## 验收标准

```text
- 已理解当前仓库结构
- 已说明当前系统已有能力
- 已说明当前系统缺口
- 已提出 2.8 改造落点
```

---

# Sprint 1｜Harness Foundation

## 目标

建立 Hermes 2.8 的基础骨架。

## 需要实现

```text
- Intent Card schema
- Task Card schema
- Event Log schema
- Review Card schema 初版
- Event Logger
- Task 状态流转基础能力
- Stage Summary 模板
```

## 重点要求

Event Log 必须在 Sprint 1 实现。

Task 状态变化时，必须写入 Event Log。

## 建议新增文件

```text
/docs/architecture/harness-overview.md
/docs/schema/intent-card.schema.json
/docs/schema/task-card.schema.json
/docs/schema/event-log.schema.json
/docs/schema/review-card.schema.json
/docs/templates/stage-summary-template.md

/src/harness/event_logger.*
/src/harness/task_manager.*
/src/harness/intent_parser.*

/runtime/events/task-events.jsonl
/runtime/intents/intent-cards.jsonl
/runtime/tasks/task-cards.jsonl
```

## 输出文档

```text
/docs/stages/sprint-01/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "feat: add harness foundation schemas and event log"
```

## 验收标准

```text
- 可以创建 Intent Card
- 可以创建 Task Card
- 可以更新 Task 状态
- 状态变化会写入 Event Log
- 事件中包含 reason
- Sprint 1 文档已生成
- Git 已提交
```

---

# Sprint 2｜MCP Integration Harness

## 目标

将 firecrawl MCP 和 context MCP 纳入 Capability Harness。

## 需要实现

```text
- Capability Registry
- MCP Registry
- MCP Router
- MCP Routing Policy
- Tool Call Event Log
```

## 需要明确

```text
- 什么时候调用 firecrawl MCP
- 什么时候调用 context MCP
- 调用前如何记录原因
- 调用后如何把结果加入任务上下文
- 调用失败如何记录
```

## 建议新增文件

```text
/docs/architecture/capability-harness.md
/docs/architecture/mcp-harness.md
/docs/policies/mcp-routing-policy.md

/src/harness/capability_registry.*
/src/harness/capability_router.*
/src/harness/mcp_registry.*
/src/harness/mcp_router.*

/runtime/events/tool-events.jsonl
```

## 输出文档

```text
/docs/stages/sprint-02/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "feat: integrate firecrawl and context mcp into capability harness"
```

## 验收标准

```text
- 系统可以注册 firecrawl MCP
- 系统可以注册 context MCP
- 系统可以根据任务判断是否需要 MCP
- MCP 调用会写入 Tool Event Log
- MCP 调用事件包含 reason
- Sprint 2 文档已生成
- Git 已提交
```

---

# Sprint 3｜Agent Routing Harness

## 目标

建立主 Agent 的秘书式分发机制。

## 需要实现

```text
- Agent Registry
- Agent Router
- Agent Routing Policy
- Subtask Card
- Delegation Event Log
- Subtask Result Aggregation
```

## 主 Agent 角色

主 Agent 不是万能执行者，而是：

```text
- 理解任务
- 拆解任务
- 判断需要哪些能力
- 分发给对应 Agent
- 收集子结果
- 统一收口
```

## 建议新增文件

```text
/docs/architecture/agent-routing.md
/docs/policies/agent-routing-policy.md

/src/harness/agent_registry.*
/src/harness/agent_router.*

/runtime/events/agent-events.jsonl
```

## 输出文档

```text
/docs/stages/sprint-03/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "feat: add agent routing and delegation harness"
```

## 验收标准

```text
- 系统有 Agent Registry
- 系统有 Agent Routing Policy
- 主 Agent 能判断是否需要分发
- 能记录为什么分发给某个 Agent
- 能聚合子任务结果
- Sprint 3 文档已生成
- Git 已提交
```

---

# Sprint 4｜Review & Acceptance Harness

## 目标

建立任务验收机制。

## 需要实现

```text
- Review Engine
- Review Card
- Acceptance Criteria Checker
- failed / blocked / retry 机制
- Review Event Log
```

## 关键规则

```text
- 任务不能从 running 直接 completed
- 必须先进入 reviewing
- Review 通过后才能 completed
- Review 不通过应回到 running 或 failed
- Review 决策必须记录 reason
```

## 建议新增文件

```text
/docs/architecture/review-harness.md
/docs/policies/acceptance-policy.md

/src/harness/review_engine.*

/runtime/reviews/review-cards.jsonl
/runtime/events/review-events.jsonl
```

## 输出文档

```text
/docs/stages/sprint-04/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "feat: add review and acceptance harness"
```

## 验收标准

```text
- Task 可以进入 reviewing
- Review Card 可以生成
- Review 可以 passed / failed / needs_revision
- Review 通过后 Task 才能 completed
- Review 不通过有明确后续状态
- Review Event Log 包含 decision_reason
- Sprint 4 文档已生成
- Git 已提交
```

---

# Sprint 5｜Documentation & Git Workflow Harness

## 目标

每个阶段完成后自动沉淀文档，并形成 Git 提交边界。

## 需要实现

```text
- Stage Summary Generator
- Function Snapshot Generator
- Architecture Snapshot Generator
- Implementation Detail Generator
- Known Issues Generator
- Git Commit Helper
```

## 建议新增文件

```text
/docs/architecture/documentation-harness.md
/docs/policies/git-commit-policy.md

/src/harness/doc_generator.*
/src/harness/git_helper.*
```

## 输出文档

```text
/docs/stages/sprint-05/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

## Git commit

```bash
git add .
git commit -m "feat: add documentation and git workflow harness"
```

## 验收标准

```text
- 能生成 Sprint 总结文档
- 能生成当前功能说明
- 能生成当前架构说明
- 能生成实现细节说明
- 能记录已知问题
- 能给出 Git commit message
- Sprint 5 文档已生成
- Git 已提交
```

---

# Sprint 6｜End-to-End Task Run

## 目标

用真实任务跑通完整 Hermes 2.8 流程。

## 测试任务

请使用以下任务测试：

```text
帮我评估一个蒙牛世界杯整合传播方案，并给出优化建议。
```

## 期望完整流程

```text
用户输入
→ Intent Card
→ Task Card
→ context MCP 判断是否需要读取历史偏好
→ 任务拆解
→ Agent Routing
→ Strategy Agent 分析
→ Writing Agent 优化
→ Review Agent 挑刺
→ Main Agent 收口
→ Review Card
→ Event Log
→ Stage Summary
→ Git Commit
```

## 输出文档

```text
/docs/stages/sprint-06/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
  06-end-to-end-test-report.md
```

## Git commit

```bash
git add .
git commit -m "test: complete end-to-end harness task run"
```

## 验收标准

```text
- 完整任务可以跑通
- 有 Intent Card
- 有 Task Card
- 有 Event Log
- 有 MCP 判断记录
- 有 Agent 分发记录
- 有 Review Card
- 有最终输出
- 有阶段总结文档
- 有 Git 提交
```

---

# 七、重要工程要求

## 1. 请优先适配当前技术栈

不要强行引入不必要的新框架。

先判断当前 Hermes 使用的是：

```text
- Python
- TypeScript
- Node.js
- 其他
```

然后按现有技术栈实现。

---

## 2. Schema 优先

所有核心对象必须先有 schema：

```text
Intent Card
Task Card
Event Log
Review Card
Agent Registry
Capability Registry
```

Schema 是后续稳定演进的基础。

---

## 3. JSONL 优先

运行时记录建议优先使用 JSONL。

原因：

```text
- 简单
- 可追加
- 易调试
- 易被模型读取
- 后续可迁移数据库
```

---

## 4. 文档和代码同步

每个 Sprint 完成后，必须更新文档。

不要只改代码不写文档。

---

## 5. 保持可回滚

每个 Sprint 是一个清晰 Git commit。

不要多个 Sprint 混在一个提交里。

---

# 八、最终交付物

完成 Hermes 2.8 后，应至少包含：

```text
1. Harness 总架构文档
2. Intent Harness 实现
3. Task Harness 实现
4. Event Log 实现
5. Capability Harness 实现
6. firecrawl MCP 接入策略
7. context MCP 接入策略
8. Agent Routing Harness 实现
9. Review Harness 实现
10. Documentation Harness 实现
11. Git Workflow Harness 实现
12. 每个 Sprint 的阶段总结文档
13. End-to-End 测试报告
14. 每个 Sprint 对应 Git commit
```

---

# 九、执行顺序

请严格按以下顺序执行：

```text
1. 先进行 Sprint 0 仓库审计
2. 输出 Sprint 0 阶段总结文档
3. Git commit
4. 再进入 Sprint 1
5. 每完成一个 Sprint，生成文档并提交 Git
6. 不要跳 Sprint
7. 不要把后续 Sprint 的复杂能力提前混入前面 Sprint
```

---

# 十、开始执行

请现在开始。

第一步：

```text
阅读当前 Hermes 代码仓库结构，完成 Sprint 0 Repository Audit。
```

完成 Sprint 0 后，请生成：

```text
/docs/stages/sprint-00/
  01-current-function.md
  02-current-architecture.md
  03-implementation-details.md
  04-known-issues.md
  05-stage-summary.md
```

然后提交：

```bash
git add .
git commit -m "docs: add sprint 00 repository audit"
```

提交完成后，再继续 Sprint 1。

---

# 十一、Claude Code 使用补充指令

如果希望严格阶段推进，请在 Claude Code 中补充：

```text
请不要一次性做完所有 Sprint，严格从 Sprint 0 开始。
每完成一个 Sprint，先给我汇报本阶段完成内容、生成的文档、Git commit hash，再继续下一个 Sprint。
```

如果希望自动连续执行，请补充：

```text
请按任务书自动连续执行 Sprint 0 到 Sprint 6。
每个 Sprint 完成后必须生成文档并提交 Git。
如果遇到阻塞，不要跳过，请记录 blocked reason，并给出最小修复方案。
```
