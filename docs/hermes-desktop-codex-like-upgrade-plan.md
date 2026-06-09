# Hermes Desktop Codex-like 改造实施方案

版本：v0.3  
目标：把 Hermes 客户端改造成类似 Codex.app 的 Agent Coding Workbench。  
核心原则：先固定产品主链路，再逐步扩展执行器、worktree、router、workspace context、review/QA agent 和外部入口。

---

## 0. 总目标

把当前 Hermes 客户端从：

```text
多 Agent 系统管理面板
```

调整为：

```text
Codex.app-like Agent Coding Workbench
```

核心产品主链路：

```text
Project
  → Task Thread
  → Agent Run
  → Logs / Tool Calls / Diff
  → Review
  → Continue / Accept / Done
```

v0.1 先做最小闭环，但不是最终目标。最小闭环的作用是固定后续所有能力的挂载主线。

后续演进路线：

```text
v0.1 最小闭环
v0.2 体验补齐
v0.3 多执行器
v0.4 Worktree / 并行任务
v0.5 半自动 Router
v0.6 Workspace Context
v0.7 Review / QA Agent
v0.8 外部入口 Inbox
v1.0 Hermes Agent Workbench
```

---

## 1. 产品原则

### 1.1 主链路不可变

后续所有功能都必须服务这条链路：

```text
Task Thread → Agent Run → Artifact / Diff → Review → Done
```

如果一个功能不能增强这条链路，就暂缓。

### 1.2 先产品闭环，后系统复杂度

先做：

```text
项目
任务线程
执行日志
文件 diff
人工 review
任务完成/继续/失败
```

后做：

```text
多执行器
worktree
并行任务
半自动 router
workspace context
review / QA agent
Feishu / Discord / CLI 外部入口
```

### 1.3 桌面端是工作台，不是 Agent Runtime

Hermes Desktop 不应该重新造一个复杂 Agent Runtime。它应该承担：

```text
Project 管理
Task Thread 管理
Run 编排
Logs / Diff / Review 展示
Executor Adapter 接入
用户确认与状态透明化
```

真正执行任务的能力来自：

```text
Codex
Claude Code CLI
DeepSeek TUI
Hermes Local
```

---

## 2. 工具总分工

| 工具 | 角色 | 主要职责 |
|---|---|---|
| Codex.app | 主线推进者 | 产品审计、主分支实现、大任务拆分、主功能开发、diff review |
| Claude Code CLI | 架构把关者 | 架构设计、ADR、状态模型、复杂重构 review、安全边界 review |
| DeepSeek TUI | 快速扫雷者 | 快速代码扫描、明显 bug 检查、低成本第二意见、小范围辅助 |
| Trae | 本地落地者 | Electron/React/UI 本地调试、样式、空状态、交互细节、手工验收 |

不要让四个工具同时修改同一批核心文件。

推荐规则：

```text
Codex.app       = 主分支和主实现
Claude Code CLI = 架构设计与 review
DeepSeek TUI    = 扫描和小修
Trae            = 本地 UI / Electron 调试
```

---

## 3. 全局工程规则

### 3.1 推荐分支

```bash
feature/codex-like-desktop-workbench
```

### 3.2 推荐阶段提交

```text
phase-0-research
phase-1-product-architecture
phase-2-state-model
phase-3-v01-poc
phase-4-v02-experience
phase-5-v03-multi-executor
phase-6-v04-worktree
phase-7-v05-router
phase-8-v06-context
phase-9-v07-review-qa
phase-10-v08-external-inbox
phase-11-v1-release
```

### 3.3 禁止事项

所有阶段默认禁止：

```text
1. 不要一次性重写整个客户端
2. 不要一开始做全自动多 Agent
3. 不要一开始接 Feishu / Discord 自动执行
4. 不要绕过 Diff Review
5. 不要让多个工具同时修改同一块核心代码
6. 不要把外部 Hermes Desktop 仓库代码直接复制进来，除非已经明确许可和改造策略
7. 不要把 unavailable / stub 功能伪装成已完成
```

---

# Phase 0：三方审计与方向确认

## 目标

先搞清楚：

```text
官方 Hermes Desktop 产品设计怎么接近 Codex.app
社区版 fathah/hermes-desktop 哪些工程实现更轻
你自己的 Hermes 当前哪些能力要保留
```

## 审计对象

```text
1. NousResearch/hermes-agent/apps/desktop
2. fathah/hermes-desktop
3. 当前 Hermes 客户端
```

## 分工

| 工具 | 角色 | 是否改代码 |
|---|---|---|
| Codex.app | 主审计 | 否 |
| Claude Code CLI | 复核审计结论 | 否 |
| DeepSeek TUI | 快速扫代码结构 | 否 |
| Trae | 暂不参与 | 否 |

## 产出

```text
docs/research/codex-like-hermes-desktop-audit.md
docs/research/official-hermes-desktop-product-audit.md
docs/research/community-hermes-desktop-implementation-audit.md
docs/research/my-hermes-current-ui-audit.md
docs/roadmap/hermes-desktop-upgrade-roadmap.md
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 0：产品与工程审计。

目标：
我希望把当前 Hermes 客户端改造成类似 Codex.app 的 Agent Coding Workbench。
核心体验不是聊天，而是：

Project → Task Thread → Agent Run → Logs / Tool Calls / Diff → Review → Continue / Accept / Done

请审计三个对象：

1. NousResearch/hermes-agent/apps/desktop
2. fathah/hermes-desktop
3. 当前 Hermes 客户端

要求：
1. 不要修改代码
2. 可以 clone 外部仓库到临时目录，但不要把外部代码复制进当前项目
3. 重点不是比较谁官方，而是比较谁的产品设计更接近 Codex.app
4. 重点分析信息架构、任务流、日志、diff、agent 状态、session/task 组织方式
5. 输出清晰的结论：产品设计参考谁，工程实现参考谁，当前 Hermes 保留什么

请输出以下文档：

1. docs/research/codex-like-hermes-desktop-audit.md
2. docs/research/official-hermes-desktop-product-audit.md
3. docs/research/community-hermes-desktop-implementation-audit.md
4. docs/research/my-hermes-current-ui-audit.md
5. docs/roadmap/hermes-desktop-upgrade-roadmap.md

每份文档都要包含：
- 观察到的产品结构
- 可借鉴点
- 不适合照搬点
- 对 Hermes Codex-like 改造的影响
- v0.1 最小闭环建议
- v1.0 扩展方向

不要修改业务代码。
```

## 给 Claude Code CLI 的提示词

```md
请复核 Codex.app 生成的 Phase 0 审计文档。

读取：

1. docs/research/codex-like-hermes-desktop-audit.md
2. docs/research/official-hermes-desktop-product-audit.md
3. docs/research/community-hermes-desktop-implementation-audit.md
4. docs/research/my-hermes-current-ui-audit.md
5. docs/roadmap/hermes-desktop-upgrade-roadmap.md

请重点检查：

1. 结论是否过度偏向某一个代码库
2. 是否区分了“产品设计基准”和“代码改造底座”
3. 是否正确识别 Codex-like 主链路：
   Project → Task Thread → Agent Run → Logs/Diff → Review
4. 是否遗漏当前 Hermes 已有能力：
   Task Card、Session Binding、Workspace Context、Status Panel、Outbox、Event Log
5. 是否有一上来大改、过早多 Agent 化的风险
6. v0.1 到 v1.0 的扩展路线是否合理

不要修改代码。
只输出：

docs/review/phase-0-architecture-review.md

文档内容包括：
- 同意的结论
- 不同意的结论
- 必须修正的点
- Phase 1 之前必须确认的架构边界
```

## 给 DeepSeek TUI 的提示词

```md
请快速扫描当前 Hermes 客户端代码结构，不要修改代码。

目标：
为 Hermes Desktop Codex-like 改造做快速扫雷。

重点找：

1. 当前 UI 入口文件
2. 当前 Workspace / Session / Task 相关组件
3. 当前状态模型在哪里
4. 当前 API / IPC / adapter 调用在哪里
5. 哪些文件明显会成为改造热点
6. 哪些地方存在强耦合风险
7. 哪些地方适合先不碰

只输出问题清单：

docs/research/current-hermes-code-hotspots.md

不要修改代码。
```

---

# Phase 1：产品 PRD、信息架构、ADR

## 目标

把“想做得像 Codex.app”变成明确产品定义。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | 主设计 |
| Codex.app | 复核并补充产品体验 |
| DeepSeek TUI | 不参与 |
| Trae | 不参与 |

## 产出

```text
docs/product/hermes-desktop-codex-like-prd.md
docs/product/hermes-desktop-information-architecture.md
docs/adr/ADR-codex-like-agent-workbench.md
```

## 给 Claude Code CLI 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 1：产品 PRD、信息架构和 ADR。

输入文档：

1. docs/research/codex-like-hermes-desktop-audit.md
2. docs/review/phase-0-architecture-review.md
3. docs/roadmap/hermes-desktop-upgrade-roadmap.md

目标：
把 Hermes 客户端定义为 Codex.app-like Agent Coding Workbench。

必须明确：

1. 产品主链路：
   Project → Task Thread → Agent Run → Logs / Tool Calls / Diff → Review → Done

2. v0.1 只做最小闭环，但后续会扩展到：
   - 多执行器
   - worktree
   - 并行任务
   - 半自动 router
   - workspace context
   - review / QA agent
   - Feishu / Discord / CLI 外部入口

3. 第一阶段必须后置：
   - 全自动多 Agent
   - 自动 commit / push / PR
   - Feishu / Discord 自动执行
   - 复杂 Scheduler
   - 长期记忆

请输出：

1. docs/product/hermes-desktop-codex-like-prd.md
2. docs/product/hermes-desktop-information-architecture.md
3. docs/adr/ADR-codex-like-agent-workbench.md

ADR 必须包含：
- 背景
- 决策
- 为什么先做最小闭环
- 为什么最小闭环不是最终目标
- 后续扩展路线
- 不做什么
- 风险与规避
- 验收标准

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请 review Claude Code CLI 生成的 Phase 1 文档：

1. docs/product/hermes-desktop-codex-like-prd.md
2. docs/product/hermes-desktop-information-architecture.md
3. docs/adr/ADR-codex-like-agent-workbench.md

请从 Codex.app-like 产品体验角度检查：

1. 主链路是否足够短
2. 是否真的不像普通聊天 UI
3. 是否突出了 Project / Task Thread / Agent Run / Diff Review
4. v0.1 是否足够小
5. v0.2 到 v1.0 是否有清晰扩展路线
6. 是否遗漏 run history、retry、continue、changed files、open in editor 等关键体验
7. 是否有过度工程化倾向

不要修改代码。
可以直接修改文档，但只限以上三份文档。
完成后输出修改摘要。
```

---

# Phase 2：状态模型与 Adapter 架构

## 目标

在动 UI 和功能前，先固定状态模型，避免后续状态打架。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | 主设计 |
| Codex.app | 实现前复核 |
| DeepSeek TUI | 扫重复状态 |
| Trae | 不参与 |

## 产出

```text
docs/architecture/hermes-desktop-state-model.md
docs/architecture/agent-adapter-layer.md
docs/architecture/run-orchestrator.md
```

## 推荐初始状态模型

### TaskStatus

```ts
type TaskStatus =
  | "draft"
  | "queued"
  | "running"
  | "needs_review"
  | "done"
  | "failed"
  | "blocked"
  | "cancelled";
```

### RunStatus

```ts
type RunStatus =
  | "created"
  | "starting"
  | "streaming"
  | "collecting_diff"
  | "completed"
  | "failed"
  | "cancelled";
```

### ExecutorType

```ts
type ExecutorType =
  | "claude-code"
  | "codex"
  | "deepseek-tui"
  | "hermes-local";
```

## 给 Claude Code CLI 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 2：状态模型与 Adapter 架构设计。

输入：

1. docs/product/hermes-desktop-codex-like-prd.md
2. docs/product/hermes-desktop-information-architecture.md
3. docs/adr/ADR-codex-like-agent-workbench.md

目标：
在改代码前，设计最小但可扩展的状态模型和 Adapter Layer。

必须设计：

1. Project model
2. Task Thread model
3. Agent Run model
4. Run Event model
5. Executor model
6. Diff / Artifact model
7. AgentExecutor 接口
8. Run Orchestrator 边界
9. UI 状态与执行状态的关系

建议初始状态：

TaskStatus:
- draft
- queued
- running
- needs_review
- done
- failed
- blocked
- cancelled

RunStatus:
- created
- starting
- streaming
- collecting_diff
- completed
- failed
- cancelled

ExecutorType:
- claude-code
- codex
- deepseek-tui
- hermes-local

请输出：

1. docs/architecture/hermes-desktop-state-model.md
2. docs/architecture/agent-adapter-layer.md
3. docs/architecture/run-orchestrator.md

要求：
- 不要设计复杂多 Agent runtime
- Adapter 只负责启动、传参、收集日志、收集结果
- Orchestrator 负责状态流转
- UI 不直接调用具体 executor
- 后续 worktree / router / review agent 可以扩展进来

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请 review Phase 2 架构文档：

1. docs/architecture/hermes-desktop-state-model.md
2. docs/architecture/agent-adapter-layer.md
3. docs/architecture/run-orchestrator.md

请检查：

1. 状态模型是否支持 v0.1 最小闭环
2. 是否能扩展到 v0.3 多执行器
3. 是否能扩展到 v0.4 worktree / 并行任务
4. 是否避免 UI 直接耦合具体 executor
5. 是否有重复状态或含义重叠
6. 是否过早引入复杂 agent runtime
7. 是否能支撑 Logs / Diff / Review

可以修改文档。
不要改业务代码。
输出 review 摘要。
```

## 给 DeepSeek TUI 的提示词

```md
请快速检查当前代码库里已有的状态模型，并和 Phase 2 文档对比。

输入文档：

1. docs/architecture/hermes-desktop-state-model.md
2. docs/architecture/agent-adapter-layer.md
3. docs/architecture/run-orchestrator.md

检查代码中是否已经存在：

1. task status
2. session status
3. run status
4. binding status
5. executor / agent type
6. event log model

请输出：

docs/review/phase-2-state-model-conflict-scan.md

内容包括：
- 已存在状态模型位置
- 与新模型冲突的地方
- 可以复用的地方
- 不建议改动的地方
- v0.1 实现时需要注意的迁移点

不要修改代码。
```

---

# Phase 3：v0.1 最小闭环实现

## 目标

跑通第一条 Codex-like 主链路：

```text
Project → Task Thread → Claude Code Run → Logs → Git Diff → Review → Done
```

## 分工

| 工具 | 角色 |
|---|---|
| Codex.app | 主实现 |
| Claude Code CLI | 架构 review |
| DeepSeek TUI | bug 扫描 |
| Trae | 本地 Electron/UI 调试 |

## v0.1 范围

必须做：

```text
1. Project 列表
2. 本地 repo path 绑定
3. Task Thread 创建
4. Executor 选择
5. Claude Code CLI 最小 Adapter
6. Run logs 展示
7. Git diff 读取
8. Changed files 展示
9. Task 状态流转
10. Done / Failed / Continue
```

不做：

```text
1. 多执行器
2. 自动 router
3. worktree
4. 自动 commit / push / PR
5. Feishu / Discord
6. Review agent
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 3：v0.1 最小闭环实现。

目标：
实现第一条可用主链路：

Project → Task Thread → Claude Code Run → Logs → Git Diff → Review → Done

请先阅读：

1. docs/product/hermes-desktop-codex-like-prd.md
2. docs/product/hermes-desktop-information-architecture.md
3. docs/adr/ADR-codex-like-agent-workbench.md
4. docs/architecture/hermes-desktop-state-model.md
5. docs/architecture/agent-adapter-layer.md
6. docs/architecture/run-orchestrator.md
7. docs/review/phase-2-state-model-conflict-scan.md

实现范围：

1. Project 列表
   - 支持添加本地 repo path
   - 支持选择当前 project

2. Task Thread
   - 支持创建 task
   - 字段包括 title、goal、status、executor、createdAt、updatedAt

3. Executor 选择
   - v0.1 只需要 claude-code
   - 其他 executor 可以显示 disabled 或暂不支持

4. Claude Code Adapter 最小实现
   - 从 project path 启动命令
   - 传入 task prompt
   - 捕获 stdout / stderr
   - 返回 exit code
   - 不做复杂交互

5. Run Logs
   - 实时或准实时展示 stdout / stderr
   - 支持 running / completed / failed 状态

6. Git Diff
   - run 完成后读取 git status / git diff
   - 展示 changed files
   - 展示 diff 文本或现有 diff viewer

7. Review 状态
   - run 完成后 task 进入 needs_review
   - 用户可以标记 done / failed
   - 用户可以 continue，追加 follow-up prompt

明确不要实现：

1. 多 executor
2. 自动 router
3. worktree
4. 自动 commit / push / PR
5. Feishu / Discord
6. review agent / QA agent

完成后请输出：

1. 修改文件列表
2. 新增文件列表
3. 如何启动
4. 如何手动测试
5. v0.1 已知限制
6. 下一阶段建议

请保持改动小而清晰，不要重写整个客户端。
```

## 给 Claude Code CLI 的提示词

```md
请 review Codex.app 完成的 Phase 3 v0.1 实现。

目标：
检查实现是否符合架构，不直接追求功能更多。

请重点检查：

1. 是否真正跑通：
   Project → Task Thread → Claude Code Run → Logs → Git Diff → Review → Done

2. 是否违反 Phase 2 架构：
   - UI 是否直接耦合 Claude Code 细节
   - Adapter 边界是否清楚
   - Run Orchestrator 是否承担状态流转
   - 状态模型是否重复

3. 是否有 Electron / IPC 风险
4. 是否有路径安全问题
5. 是否有 stdout/stderr 卡死风险
6. 是否有 child process 清理问题
7. Git diff 读取是否可靠
8. 失败状态是否可见
9. 用户是否能理解 agent 做了什么

不要直接大改。
请输出：

docs/review/phase-3-v01-architecture-review.md

如果发现必须修复的问题，请列成：
- P0 必须修
- P1 应该修
- P2 后续修
```

## 给 DeepSeek TUI 的提示词

```md
请快速扫描 Phase 3 v0.1 改动，不要大改代码。

重点检查：

1. TypeScript 类型错误
2. React state 明显错误
3. Electron IPC 明显问题
4. child_process 使用问题
5. git diff 命令错误
6. 日志流可能卡住的问题
7. 组件过大或重复逻辑
8. 状态命名不一致
9. 空状态 / 错误状态遗漏

请输出：

docs/review/phase-3-v01-bug-scan.md

只给问题清单和建议。
除非是非常小的 typo 或类型错误，否则不要修改代码。
```

## 给 Trae 的提示词

```md
请在本地运行 Hermes Desktop v0.1 PoC，并做小范围 UI / Electron 调试。

目标：
验证用户是否能完成：

打开客户端
→ 选择 Project
→ 创建 Task Thread
→ 选择 Claude Code executor
→ 启动 Run
→ 查看 Logs
→ 查看 Git Diff
→ 标记 Done / Failed / Continue

请检查：

1. Electron 是否能启动
2. 页面是否有明显白屏/崩溃
3. Project 选择是否清晰
4. Task Thread 创建是否顺畅
5. Logs 是否可滚动
6. running / failed / needs_review 状态是否明显
7. Diff 面板是否可读
8. 空状态是否清晰
9. 按钮 loading / disabled 状态是否正确
10. 窗口缩放是否崩布局

允许修改：
- 小范围 React UI
- Tailwind / CSS
- 空状态文案
- loading / disabled 状态
- 明显本地启动问题

不要修改：
- 状态模型
- Adapter 架构
- Run Orchestrator 架构
- 大范围目录结构

完成后输出：
1. 修复了什么
2. 还存在什么体验问题
3. 如何手动验证
```

---

# Phase 4：v0.2 体验补齐

## 目标

让 v0.1 从“能跑”变成“舒服”。

## 分工

| 工具 | 角色 |
|---|---|
| Codex.app | 主实现 |
| Claude Code CLI | 状态/体验 review |
| DeepSeek TUI | 快速检查 |
| Trae | UI 调整 |

## 新增能力

```text
1. Task Thread 历史
2. Run Summary
3. Retry
4. Continue prompt
5. Commands run
6. Changed files list 优化
7. Open in editor
8. Copy follow-up prompt
9. Archive task
10. Clear failed run / retry from failed
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 4：v0.2 体验补齐。

前提：
v0.1 已经跑通：
Project → Task Thread → Claude Code Run → Logs → Git Diff → Review → Done

目标：
让它从“能跑”变成“好用”，但仍然不引入多执行器、不引入 worktree、不引入自动 router。

请实现：

1. Task Thread 历史
   - 每个 task 可以有多个 run
   - 展示 run 时间、executor、状态、摘要

2. Run Summary
   - run 结束后可以记录 summary
   - 如果 adapter 无法生成 summary，先允许用户手动填或显示 placeholder

3. Retry
   - failed run 可以 retry
   - retry 创建新的 run，不覆盖旧 run

4. Continue
   - needs_review / done 前可以追加 follow-up prompt
   - continue 创建新的 run
   - 保留历史 run

5. Commands run
   - 展示本次 run 执行过的关键命令
   - v0.2 可以先记录系统实际调用的命令

6. Changed files list 优化
   - 文件列表与 diff 分离
   - 点击文件切换 diff

7. Open in editor
   - 支持打开 project path 或 changed file
   - 如果暂时无法实现，保留按钮但明确 disabled 原因

8. Copy follow-up prompt
   - 一键复制继续修改的 prompt

9. Archive task
   - done / cancelled / failed task 可以归档
   - 默认列表隐藏 archived

不要实现：
1. 多执行器
2. worktree
3. 自动 router
4. 自动 commit / push / PR
5. 外部入口

完成后输出：
1. 修改文件列表
2. 新增交互说明
3. 手动测试步骤
4. 已知限制
```

## 给 Claude Code CLI 的提示词

```md
请 review Phase 4 v0.2 体验补齐实现。

重点检查：

1. Task 和 Run 的关系是否清晰
2. Retry 是否创建新 run，而不是覆盖旧 run
3. Continue 是否保留上下文
4. Run history 是否会无限膨胀但不可管理
5. Archive 是否只是 UI 隐藏，还是错误删除数据
6. Changed files 和 Diff 的状态是否清晰
7. Open in editor 是否存在路径安全问题
8. 体验增强是否没有破坏 v0.1 主链路

请输出：

docs/review/phase-4-v02-experience-review.md

按 P0 / P1 / P2 分类问题。
不要直接大改代码。
```

## 给 Trae 的提示词

```md
请本地调试 Phase 4 v0.2 的 UI 体验。

重点检查：

1. Run history 是否容易理解
2. Retry / Continue 按钮位置是否合理
3. Logs 和 Diff 切换是否顺滑
4. Changed files 点击体验是否清晰
5. 空状态是否不让用户困惑
6. Archive 后任务是否还能找到
7. 小窗口下布局是否可用
8. Open in editor / Copy follow-up prompt 是否有明确反馈

允许做小范围 UI 修复。
不要改状态模型和 adapter 架构。

输出：
- UI 修复摘要
- 仍然不舒服的交互点
- 建议下一阶段处理的问题
```

---

# Phase 5：v0.3 多执行器接入

## 目标

接入你的工具组合，但仍然手动选择，不自动路由。

## 执行器顺序

```text
1. Claude Code CLI
2. Codex
3. DeepSeek TUI
4. Hermes Local
```

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | Adapter 接口复核 |
| Codex.app | 主实现 |
| DeepSeek TUI | DeepSeek Adapter 辅助验证 |
| Trae | 本地调试 |

## 给 Claude Code CLI 的提示词

```md
请在实现多执行器前，复核 AgentExecutor 接口是否足够支持：

1. Claude Code CLI
2. Codex
3. DeepSeek TUI
4. Hermes Local

输入：

1. docs/architecture/agent-adapter-layer.md
2. 当前 v0.2 实现代码

请检查：

1. AgentExecutor 接口是否过度绑定 Claude Code
2. startRun / stopRun / readEvents / collectResult 是否足够通用
3. 不同 executor 的日志格式如何统一为 RunEvent
4. 不同 executor 的失败状态如何统一
5. 不同 executor 是否都能收集 git diff
6. 是否需要 executor health check
7. 是否需要 executor capability 描述

请输出：

docs/architecture/multi-executor-adapter-design.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 5：v0.3 多执行器接入。

目标：
在 v0.2 基础上接入多个 executor，但仍然由用户手动选择，不做自动 router。

请先阅读：

1. docs/architecture/agent-adapter-layer.md
2. docs/architecture/multi-executor-adapter-design.md
3. 当前 v0.2 实现

请实现：

1. Executor Registry
   - 注册 claude-code
   - 注册 codex
   - 注册 deepseek-tui
   - 注册 hermes-local

2. Executor Health
   - 检查命令是否存在
   - 检查 project path 是否可用
   - UI 显示 available / unavailable / unknown

3. Executor Selector
   - 创建 task 时可以选择 executor
   - 不可用 executor disabled，并显示原因

4. Codex Adapter 最小实现
   - 只实现命令启动、日志收集、退出状态
   - 不要求实现 cloud 特性
   - 如果当前环境不可用，必须优雅显示 unavailable

5. DeepSeek TUI Adapter 最小实现
   - 只实现命令启动、日志收集、退出状态
   - 如果交互式 TUI 不适合直接驱动，先做 adapter stub，并明确限制

6. Hermes Local Adapter
   - 接当前 Hermes 本地能力
   - 如果接口未定，先做 stub
   - UI 要显示“planned / unavailable”，不要假装可用

不要实现：
1. 自动 router
2. worktree
3. 多 agent 协作
4. 自动 commit / push / PR

完成后输出：
1. 修改文件列表
2. 每个 executor 的支持程度
3. 如何配置命令路径
4. 如何手动测试
5. 哪些 adapter 只是 stub
```

## 给 DeepSeek TUI 的提示词

```md
请重点检查 Phase 5 中 DeepSeek TUI Adapter 的设计和实现。

目标：
确认它是否真的适合作为 Hermes Desktop 的 executor。

请检查：

1. DeepSeek TUI 是否支持非交互式调用
2. 是否能通过命令行传入 prompt
3. 是否能稳定输出 stdout / stderr
4. 是否需要 pseudo-terminal
5. 是否会卡在交互输入
6. 是否能在 project path 下执行
7. 是否能通过 git diff 收集结果
8. 如果不能直接作为 executor，应该如何降级为手动辅助工具

请输出：

docs/review/deepseek-tui-adapter-feasibility.md

不要大改代码。
如发现 adapter 当前实现不可行，请明确建议改成 stub，不要硬接。
```

## 给 Trae 的提示词

```md
请本地测试 Phase 5 多执行器 UI。

检查：

1. Executor selector 是否清楚
2. unavailable / disabled 状态是否明显
3. 每个 executor 的配置入口是否容易理解
4. 健康检查失败时是否有清楚原因
5. 切换 executor 是否不会污染 task 状态
6. adapter stub 是否明确显示 planned，而不是误导用户
7. 不同 executor 的 logs 展示是否一致

允许做 UI 小修。
不要改 executor 架构。

输出：
- 本地测试结果
- UI 修复摘要
- 哪些 executor 实测可用
- 哪些 executor 不可用
```

---

# Phase 6：v0.4 Worktree 与并行任务

## 目标

接近 Codex.app 的核心体验：多个任务并行执行，互不污染。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | Worktree 架构设计 |
| Codex.app | 主实现 |
| DeepSeek TUI | Git 风险扫描 |
| Trae | 本地验证 |

## 给 Claude Code CLI 的提示词

```md
请设计 Hermes Desktop v0.4 Worktree / 并行任务架构。

目标：
每个 Task Thread 可以绑定独立 git worktree，使多个 agent run 并行执行时不会互相污染。

请设计：

1. worktree 创建规则
2. branch 命名规则
3. taskId 与 worktreePath 的绑定
4. worktree 状态：
   - not_created
   - creating
   - ready
   - dirty
   - merging
   - merged
   - discarded
   - failed

5. 并行 run 限制
6. merge back 策略
7. discard worktree 策略
8. diff 来源：
   - main repo diff
   - worktree diff

9. UI 应该如何显示：
   - branch
   - worktree path
   - dirty state
   - merge / discard 按钮

请输出：

docs/architecture/worktree-parallel-runs.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 6：v0.4 Worktree 与并行任务。

请先阅读：

1. docs/architecture/worktree-parallel-runs.md
2. 当前 v0.3 多执行器实现

目标：
让每个 Task Thread 可以使用独立 worktree，并允许多个 task 并行执行。

实现范围：

1. Task 创建时可选择：
   - use current working tree
   - create isolated worktree

2. Worktree 创建
   - 自动创建 branch
   - 自动创建 worktree path
   - 与 taskId 绑定

3. Run 执行
   - executor 在 worktreePath 下运行
   - logs / diff 从 worktree 收集

4. UI 展示
   - branch name
   - worktree path
   - worktree status
   - dirty / clean 状态

5. 并行限制
   - 允许多个不同 worktree 的 task 并行
   - 禁止多个 run 同时写同一个 worktree

6. 操作
   - merge back
   - discard worktree
   - open worktree in editor

不要实现：
1. 自动 push / PR
2. 复杂 conflict resolution
3. 全自动 router
4. review agent

完成后输出：
1. 修改文件列表
2. worktree 创建规则
3. 手动测试步骤
4. 已知风险
```

## 给 DeepSeek TUI 的提示词

```md
请快速检查 Phase 6 Worktree 实现的 Git 风险。

重点检查：

1. 是否可能误删用户工作目录
2. 是否可能覆盖 main working tree
3. branch 命名是否安全
4. worktree path 是否安全
5. discard 是否只删除目标 worktree
6. merge back 是否有冲突处理
7. 并行 run 是否可能写同一目录
8. git command 是否缺少错误处理

请输出：

docs/review/phase-6-worktree-risk-scan.md

不要直接修改代码，除非是明显小 bug。
```

## 给 Trae 的提示词

```md
请本地验证 Phase 6 Worktree / 并行任务体验。

手动测试：

1. 创建 Project
2. 创建 Task A，使用 worktree A
3. 创建 Task B，使用 worktree B
4. 同时运行两个 task
5. 检查两个 task 的 logs 是否独立
6. 检查两个 task 的 diff 是否独立
7. 测试 merge back
8. 测试 discard worktree
9. 测试打开 worktree in editor
10. 测试异常情况：worktree 创建失败、branch 已存在、merge conflict

允许做 UI 小修和错误提示优化。
不要改 worktree 架构。

输出：
- 本地验证结果
- 发现的问题
- 修复了什么
- 仍需 Codex/Claude 处理的问题
```

---

# Phase 7：v0.5 半自动 Router

## 目标

Hermes 可以推荐执行器，但用户仍然确认。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | Router 规则设计 |
| Codex.app | 主实现 |
| DeepSeek TUI | 分类规则补充 |
| Trae | UI 调试 |

## 初始推荐规则

```text
架构设计 / 方案评审 → Claude Code
复杂实现 / 大范围重构 → Codex
快速 bug scan / 小修 → DeepSeek TUI
Hermes 系统内部任务 → Hermes Local
UI 调试 / 本地体验 → Trae 手动处理，不作为 executor 自动运行
```

## 给 Claude Code CLI 的提示词

```md
请设计 Hermes Desktop v0.5 半自动 Executor Router。

目标：
用户创建 task 后，Hermes 根据任务类型推荐 executor，但不自动执行，必须由用户确认。

初始规则建议：

1. 架构设计 / 方案评审 → Claude Code
2. 复杂实现 / 大范围重构 → Codex
3. 快速 bug scan / 小修 → DeepSeek TUI
4. Hermes 系统内部任务 → Hermes Local
5. UI 调试 / 本地体验 → Trae 手动处理，不作为 executor 自动运行

请设计：

1. Router 输入字段
   - task title
   - task goal
   - project type
   - changed files
   - user selected preference
   - executor health

2. Router 输出
   - recommendedExecutor
   - confidence
   - reason
   - alternatives

3. UI 展示方式
   - 推荐执行器
   - 推荐理由
   - 一键接受
   - 手动更换

4. 禁止事项
   - 不自动执行
   - 不绕过用户确认
   - 不覆盖用户选择

请输出：

docs/architecture/semi-auto-executor-router.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 7：v0.5 半自动 Executor Router。

请先阅读：

1. docs/architecture/semi-auto-executor-router.md
2. 当前 v0.4 worktree 实现

目标：
创建 task 时，系统可以推荐 executor，但用户必须确认。

实现：

1. Router Service
   - 输入 task title / goal / project / executor health
   - 输出 recommendedExecutor / confidence / reason / alternatives

2. 初始规则
   - 架构设计 / ADR / review → claude-code
   - 复杂实现 / refactor → codex
   - 快速 bug scan / small fix → deepseek-tui
   - Hermes 内部流程 / adapter / scheduler → hermes-local

3. UI
   - 创建 task 时显示推荐 executor
   - 显示推荐理由
   - 用户可以接受
   - 用户可以手动改 executor
   - 用户选择优先级高于系统推荐

4. 记录
   - task 中记录 router recommendation
   - run 中记录实际 executor

不要实现：
1. 全自动执行
2. 多 Agent 自动协作
3. 动态学习复杂策略

完成后输出：
1. 修改文件列表
2. Router 规则说明
3. 手动测试步骤
4. 已知限制
```

## 给 DeepSeek TUI 的提示词

```md
请检查 Phase 7 Router 初始规则是否合理。

重点检查：

1. 是否有明显错误分类
2. 是否应该把某些任务推荐给 DeepSeek TUI
3. 是否有过度依赖 Codex 的情况
4. 是否有过度依赖 Claude Code 的情况
5. 是否应该增加“不要自动推荐”的低置信度情况
6. 推荐理由是否足够透明

请输出：

docs/review/phase-7-router-rule-review.md

不要修改代码。
```

---

# Phase 8：v0.6 Workspace Context

## 目标

接回你自己的 Hermes 优势：项目上下文、ADR、当前 Sprint、架构约束。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | Context 架构设计 |
| Codex.app | 主实现 |
| DeepSeek TUI | prompt 注入风险扫描 |
| Trae | UI 调试 |

## 给 Claude Code CLI 的提示词

```md
请设计 Hermes Desktop v0.6 Workspace Context 架构。

目标：
每个 Project 可以维护结构化上下文，创建 task / run 时自动注入给 executor。

请设计：

1. Workspace Context 内容
   - project overview
   - architecture notes
   - ADR summaries
   - current sprint
   - common commands
   - test commands
   - forbidden areas
   - coding conventions
   - recent tasks

2. Context 注入策略
   - task prompt 前附加哪些内容
   - 哪些内容按 executor 不同裁剪
   - 如何避免 prompt 太长
   - 如何让用户看到注入了什么

3. UI
   - Project Context 页面
   - Context Preview
   - Include / exclude toggles

4. 安全边界
   - 不自动注入 secrets
   - 不注入隐藏敏感配置
   - 用户可以关闭 context injection

请输出：

docs/architecture/workspace-context-injection.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 8：v0.6 Workspace Context。

请先阅读：

1. docs/architecture/workspace-context-injection.md
2. 当前 v0.5 router 实现

目标：
为 Project 增加 Workspace Context，并在创建 Agent Run 时注入结构化上下文。

实现：

1. Project Context 数据
   - overview
   - architecture notes
   - current sprint
   - ADR summaries
   - common commands
   - test commands
   - forbidden areas
   - coding conventions

2. UI
   - Project Context 编辑页面
   - Context Preview
   - 创建 task 时显示将注入的上下文摘要
   - 用户可关闭 context injection

3. Run Prompt Builder
   - 将 task goal + workspace context 组合成 executor prompt
   - 保存最终 prompt snapshot 到 run
   - run detail 中可以查看 prompt snapshot

4. 安全
   - 不读取 .env
   - 不自动注入 secrets
   - 不隐藏注入内容

不要实现：
1. 复杂长期记忆
2. 自动从所有文件中抽取上下文
3. 远程同步 memory
4. 多 Agent 共享记忆

完成后输出：
1. 修改文件列表
2. Context 数据结构说明
3. Prompt Builder 说明
4. 手动测试步骤
```

## 给 DeepSeek TUI 的提示词

```md
请检查 Phase 8 Workspace Context / Prompt Builder 的风险。

重点检查：

1. 是否可能注入 secrets
2. 是否读取了 .env / private key / token
3. prompt snapshot 是否存储了敏感内容
4. context 是否过长
5. 用户是否能看到实际注入内容
6. 是否有办法关闭 context injection
7. executor prompt 是否结构清晰
8. 不同 executor 是否需要不同 prompt 格式

请输出：

docs/review/phase-8-context-risk-scan.md

不要直接修改代码。
```

---

# Phase 9：v0.7 Review / QA Agent

## 目标

引入真正的多 Agent，但不是群聊，而是审查链路：

```text
Executor 完成
  → Review Agent 检查 diff
  → QA Agent 检查测试/风险
  → Hermes 汇总
  → 用户决定
```

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | Review / QA 架构设计 |
| Codex.app | 主实现 |
| DeepSeek TUI | QA scan 执行器候选 |
| Trae | UI 调试 |

## 给 Claude Code CLI 的提示词

```md
请设计 Hermes Desktop v0.7 Review / QA Agent 架构。

目标：
在主 executor 完成后，允许用户触发 review / QA 检查，但不自动接受或合并改动。

请设计：

1. Review Run
   - 输入：diff、changed files、task goal、workspace context
   - 输出：review findings
   - executor 建议：Claude Code

2. QA Run
   - 输入：diff、test commands、changed files
   - 输出：test result、risk list
   - executor 建议：DeepSeek TUI 或 Hermes Local

3. 状态模型
   - main run
   - review run
   - qa run
   - review status
   - qa status

4. UI
   - Review tab
   - QA tab
   - findings list
   - risk severity
   - user final decision

5. 禁止事项
   - Review / QA 不自动改代码
   - Review / QA 不自动 merge
   - 用户最终确认仍然必要

请输出：

docs/architecture/review-qa-agent-chain.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 9：v0.7 Review / QA Agent。

请先阅读：

1. docs/architecture/review-qa-agent-chain.md
2. 当前 v0.6 Workspace Context 实现

目标：
在 main run 完成后，用户可以触发 Review / QA 检查。

实现：

1. Review Run
   - 从 main run 的 diff / changed files / task goal 构建 review prompt
   - 默认推荐 claude-code
   - 输出 review findings
   - 不自动修改代码

2. QA Run
   - 从 changed files / test commands 构建 QA prompt
   - 默认推荐 deepseek-tui 或 hermes-local
   - 输出 test result / risk list
   - 不自动修改代码

3. UI
   - Run Detail 增加 Review tab
   - Run Detail 增加 QA tab
   - 显示 findings severity
   - 显示检查时间和 executor
   - 用户可以重新运行 Review / QA

4. 状态
   - main run 状态不被 review / QA 覆盖
   - review / QA 有独立状态
   - 最终 done 仍由用户点击

不要实现：
1. 自动修复 review findings
2. 自动 merge
3. 自动 PR

完成后输出：
1. 修改文件列表
2. Review / QA 流程说明
3. 手动测试步骤
4. 已知限制
```

## 给 DeepSeek TUI 的提示词

```md
请评估 DeepSeek TUI 是否适合作为 QA scan executor。

检查：

1. 是否适合快速检查 diff
2. 是否适合跑测试命令
3. 是否适合输出结构化 risk list
4. 是否会卡在交互式输入
5. 是否应该只作为人工辅助工具，而不是自动 QA executor

请输出：

docs/review/deepseek-qa-executor-feasibility.md

不要修改代码。
```

---

# Phase 10：v0.8 外部入口 Inbox

## 目标

接回 Feishu / Discord / CLI / Scheduler，但只作为任务入口，不绕过 Desktop 审查。

正确路径：

```text
Feishu / Discord / CLI
  → Hermes Desktop Inbox
  → 用户确认
  → Task Thread
  → Agent Run
  → Logs / Diff / Review
  → Result 回写
```

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | 外部入口架构设计 |
| Codex.app | 主实现 |
| DeepSeek TUI | 边界扫描 |
| Trae | 本地 UI 调试 |

## 给 Claude Code CLI 的提示词

```md
请设计 Hermes Desktop v0.8 External Inbox 架构。

目标：
恢复 Feishu / Discord / CLI / Scheduler 作为任务入口，但不能绕过 Desktop 的状态系统和 review 流程。

请设计：

1. External Inbox model
   - source
   - raw payload
   - normalized task draft
   - status
   - createdAt
   - linkedTaskId

2. Source 类型
   - feishu
   - discord
   - cli
   - scheduler
   - manual

3. 流程
   External message → Inbox item → User confirm → Task Thread → Run

4. UI
   - Inbox 页面
   - source filter
   - convert to task
   - reject / archive
   - linked task

5. 安全边界
   - 外部入口不能直接执行代码
   - 外部入口不能自动确认
   - 外部入口不能绕过 Permission Gate
   - 结果回写必须绑定 task/run

请输出：

docs/architecture/external-inbox.md

不要修改代码。
```

## 给 Codex.app 的提示词

```md
请执行 Hermes Desktop Codex-like 改造 Phase 10：v0.8 External Inbox。

请先阅读：

1. docs/architecture/external-inbox.md
2. 当前 v0.7 Review / QA 实现

目标：
实现外部任务入口 Inbox，但不做外部消息自动执行。

实现：

1. Inbox 数据模型
   - source
   - title
   - content
   - rawPayload
   - status
   - linkedTaskId

2. Manual / CLI stub
   - 先支持手动创建 inbox item
   - CLI / Feishu / Discord 可以先做 stub

3. Inbox UI
   - 列表
   - 详情
   - convert to task
   - reject
   - archive
   - linked task

4. Convert to Task
   - 用户点击后创建 Task Thread
   - 继承 title / content
   - 用户仍然可以编辑
   - 不自动 run

5. Result 回写 stub
   - task done 后显示可以回写 source
   - Feishu / Discord 未接通时显示 unavailable

不要实现：
1. 外部消息直接执行
2. 自动 Feishu 回写
3. 自动 Discord 回写
4. Scheduler 自动跑代码

完成后输出：
1. 修改文件列表
2. Inbox 流程说明
3. 手动测试步骤
4. 哪些 source 是 stub
```

## 给 DeepSeek TUI 的提示词

```md
请检查 Phase 10 External Inbox 的安全边界。

重点检查：

1. 外部 inbox item 是否会自动执行
2. 是否绕过 task review
3. 是否绕过 permission gate
4. raw payload 是否可能污染 prompt
5. source 字段是否可信
6. convert to task 是否允许用户编辑
7. result 回写是否绑定具体 task/run
8. stub 是否清楚显示 unavailable

请输出：

docs/review/phase-10-external-inbox-risk-scan.md

不要修改代码。
```

---

# Phase 11：v1.0 收口与发布

## 目标

把前面功能收束成一个稳定版本。

## 分工

| 工具 | 角色 |
|---|---|
| Claude Code CLI | 最终架构 review |
| Codex.app | 修复和收口 |
| DeepSeek TUI | 回归扫描 |
| Trae | 本地验收 |

## 给 Claude Code CLI 的提示词

```md
请执行 Hermes Desktop Codex-like v1.0 最终架构 review。

检查范围：

1. Project
2. Task Thread
3. Agent Run
4. Logs
5. Diff Review
6. Multi Executor
7. Worktree
8. Router
9. Workspace Context
10. Review / QA Agent
11. External Inbox
12. Event Log / Permission Gate / Outbox 相关状态

请重点检查：

1. 是否所有功能都围绕主链路：
   Task Thread → Agent Run → Artifact/Diff → Review → Done

2. 是否出现重复状态模型
3. 是否 UI 直接耦合具体 executor
4. 是否有自动执行绕过用户确认
5. 是否有不透明的外部入口
6. 是否有 worktree/git 风险
7. 是否有 Electron/IPC 安全风险
8. 是否有未标明的 stub / unavailable 功能
9. 是否文档和实际行为一致

请输出：

docs/review/v1-final-architecture-review.md

按 P0 / P1 / P2 分类。
不要直接大改代码。
```

## 给 Codex.app 的提示词

```md
请根据 docs/review/v1-final-architecture-review.md 执行 v1.0 收口修复。

要求：

1. 只修 P0 / P1 问题
2. 不新增大功能
3. 不改变产品主链路
4. 不引入新的 executor
5. 不引入新的外部入口
6. 所有 unavailable / stub 功能必须明确显示
7. 更新相关文档

完成后输出：

1. 修改文件列表
2. 修复了哪些 P0
3. 修复了哪些 P1
4. 未修复的 P2
5. 手动验收步骤
6. 发布说明草稿

请生成：

docs/releases/hermes-desktop-codex-like-v1.0.md
```

## 给 DeepSeek TUI 的提示词

```md
请执行 v1.0 回归扫描，不要大改代码。

检查：

1. TypeScript 错误
2. React 组件明显 bug
3. IPC / child_process 风险
4. git worktree 命令风险
5. executor unavailable 状态
6. task/run 状态不一致
7. UI 空状态遗漏
8. 文档与实现不一致
9. TODO / FIXME 是否影响发布

输出：

docs/review/v1-regression-scan.md

除非是极小 typo，否则不要修改代码。
```

## 给 Trae 的提示词

```md
请执行 v1.0 本地验收。

完整手动测试：

1. 创建 Project
2. 配置 Workspace Context
3. 创建 Task Thread
4. 查看 Router 推荐 executor
5. 手动选择 executor
6. 创建 worktree
7. 启动 run
8. 查看 logs
9. 查看 changed files
10. 查看 diff
11. Continue 一次
12. Retry 一次失败任务
13. 触发 Review
14. 触发 QA
15. 标记 done
16. Archive task
17. 创建 Inbox item
18. Convert to task
19. 测试 unavailable executor
20. 测试小窗口布局

允许修改：
- UI 小问题
- 文案
- loading / disabled
- 空状态
- 本地启动脚本小问题

不要修改：
- 架构
- 状态模型
- adapter 设计
- router 规则

输出：
1. 本地验收结果
2. 修复摘要
3. 仍然存在的问题
4. 是否建议进入 v1.0 release
```

---

# 4. 总执行顺序

推荐按这个顺序推进：

```text
1. Codex.app 跑 Phase 0 审计
2. Claude Code CLI 复核 Phase 0
3. DeepSeek TUI 扫当前代码热点
4. Claude Code CLI 设计 Phase 1 PRD / IA / ADR
5. Codex.app review Phase 1 文档
6. Claude Code CLI 设计 Phase 2 状态模型 / Adapter / Orchestrator
7. Codex.app review Phase 2 文档
8. DeepSeek TUI 扫状态模型冲突
9. Codex.app 实现 Phase 3 v0.1 最小闭环
10. Claude Code CLI review v0.1 架构
11. DeepSeek TUI 扫 v0.1 bug
12. Trae 本地跑通 v0.1
13. Codex.app 实现 Phase 4 v0.2 体验补齐
14. Claude Code CLI review v0.2 体验和状态
15. Trae 本地调 UI
16. Claude Code CLI 复核多执行器接口
17. Codex.app 实现 Phase 5 v0.3 多执行器
18. DeepSeek TUI 验证 DeepSeek Adapter 可行性
19. Trae 本地测试多执行器 UI
20. Claude Code CLI 设计 worktree 架构
21. Codex.app 实现 Phase 6 v0.4 worktree / 并行任务
22. DeepSeek TUI 扫 Git 风险
23. Trae 本地验证 worktree
24. Claude Code CLI 设计半自动 router
25. Codex.app 实现 Phase 7 v0.5 router
26. DeepSeek TUI review router 规则
27. Claude Code CLI 设计 workspace context
28. Codex.app 实现 Phase 8 v0.6 context
29. DeepSeek TUI 扫 prompt/context 风险
30. Claude Code CLI 设计 review / QA agent
31. Codex.app 实现 Phase 9 v0.7 review / QA
32. DeepSeek TUI 评估 QA executor
33. Claude Code CLI 设计 external inbox
34. Codex.app 实现 Phase 10 v0.8 inbox
35. DeepSeek TUI 扫 external inbox 安全边界
36. Claude Code CLI 做 v1.0 最终架构 review
37. Codex.app 修 P0/P1 并生成 release 文档
38. DeepSeek TUI 回归扫描
39. Trae 最终本地验收
```

---

# 5. 每阶段验收标准

## Phase 0 验收

```text
能清楚回答：
1. 产品设计参考谁
2. 工程实现参考谁
3. 当前 Hermes 保留什么
4. v0.1 做什么
5. v1.0 扩展到哪里
```

## Phase 1 验收

```text
PRD / 信息架构 / ADR 说清楚：
1. 主链路是什么
2. 为什么先最小闭环
3. 为什么最小闭环不是终点
4. 哪些功能后置
5. 后续版本如何扩展
```

## Phase 2 验收

```text
状态模型支持：
1. Project
2. Task Thread
3. Agent Run
4. Run Event
5. Executor
6. Diff / Artifact
7. Review
8. 后续 worktree / router / review agent 扩展
```

## Phase 3 验收

```text
用户可以完成：
打开 Hermes Desktop
→ 选择 Project
→ 创建 Task
→ 选择 Claude Code
→ 启动 Run
→ 查看 Logs
→ 查看 Git Diff
→ 标记 Done / Failed / Continue
```

## Phase 4 验收

```text
用户能舒服地：
1. 查看 run history
2. retry failed run
3. continue follow-up
4. 查看 changed files
5. 打开 diff
6. archive task
```

## Phase 5 验收

```text
用户能清楚看到：
1. 哪些 executor 可用
2. 哪些 executor 不可用
3. 不可用原因是什么
4. stub 功能没有伪装成已完成
5. 不同 executor 的 logs 展示一致
```

## Phase 6 验收

```text
可以同时跑多个任务：
1. 每个任务有独立 worktree
2. diff 独立
3. logs 独立
4. 可以 merge back
5. 可以 discard
6. 不会误伤 main working tree
```

## Phase 7 验收

```text
Router 只推荐，不自动执行：
1. 推荐理由可见
2. confidence 可见
3. 用户可以接受
4. 用户可以改 executor
5. 用户选择优先于系统推荐
```

## Phase 8 验收

```text
Workspace Context 可见、可控、可关闭：
1. 用户知道注入了什么
2. prompt snapshot 可查看
3. 不自动注入 secrets
4. 不读取 .env
5. 不做隐藏记忆
```

## Phase 9 验收

```text
Review / QA 独立于 main run：
1. Review 不自动改代码
2. QA 不自动 merge
3. findings 可见
4. severity 可见
5. 最终 done 仍由用户确认
```

## Phase 10 验收

```text
外部入口只进 Inbox：
1. 不直接执行代码
2. 不绕过 review
3. convert to task 需要用户确认
4. result 回写绑定 task/run
5. stub 状态清楚
```

## Phase 11 验收

```text
v1.0 可发布：
1. P0 全修
2. P1 尽量修
3. P2 记录
4. 文档和实现一致
5. unavailable / stub 功能清楚
6. 主链路完整可用
```

---

# 6. 最终目标形态

v1.0 时，Hermes Desktop 应该是：

```text
Hermes Desktop
├─ Projects
├─ Task Threads
├─ Agent Runs
├─ Logs
├─ Tool Calls
├─ Diff Review
├─ Multi Executor
│  ├─ Claude Code CLI
│  ├─ Codex
│  ├─ DeepSeek TUI
│  └─ Hermes Local
├─ Worktrees
├─ Semi-auto Router
├─ Workspace Context
├─ Review Agent
├─ QA Agent
├─ External Inbox
├─ Event Log
├─ Permission Gate
└─ Outbox
```

但所有能力都必须围绕这条主链路：

```text
Task Thread → Agent Run → Artifact / Diff → Review → Done
```

最终产品不是功能堆满的 Hermes，而是：

```text
一个像 Codex.app 一样顺手，
但能接 Codex / Claude Code / DeepSeek / 你自己的 Hermes 的桌面 Agent 工作台。
```
