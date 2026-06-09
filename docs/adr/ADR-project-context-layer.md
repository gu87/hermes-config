# ADR: Project Context Layer — PROJECT.md 最小设计

**状态**: Accepted
**日期**: 2026-06-08
**作者**: Gu + Hermes
**作用域**: 项目上下文恢复 → PROJECT.md 最小机制

---

## 背景

Hermes 当前的项目上下文恢复依赖以下信息源的临时组合：

| 信息源 | 存什么 | 问题 |
|--------|-------|------|
| MEMORY.md | always-on 稳定事实和指针 | 不放项目特定状态（by design），无法回答「上次做到哪了」 |
| OpenChronicle | 完整会话日志 | 需要知道搜什么关键词，且可能已被剪枝 |
| session_search | 近期会话摘要 | 会话超时后上下文丢失，用户说「继续 XX」时无匹配 |
| Obsidian Wiki | 长文档、参考材料 | 不是为快速状态恢复设计的结构 |
| ADR | 架构决策 | 只有决策，没有运行态（部署在哪、当前分支、活跃风险） |

**痛点场景**：用户隔天/一周后说「继续 hermes-desktop 项目」，Hermes 需要从零散信息源中拼凑当前状态。这个过程不稳定——有时能拼出来，有时关键信息已过期或分散在多个文件中。

**根因**：缺少一个单一、结构化、可快速读取的「项目当前状态」文件。Zep/Graphiti 在 LongMemEval benchmark 中的结果表明，结构化 temporal context（含时间窗口的状态管理）在复杂时序推理任务上显著优于全量对话日志的上下文恢复（来源：Zep Blog, "State of the Art in Agent Memory", 2025-01-22, 对应论文 arXiv 2501.13956）。

---

## 决策

### 1. 引入 PROJECT.md

每个 Hermes 管理的项目维护一个 `PROJECT.md`，作为该项目的「当前状态快照」。它不是日志，不是 Wiki，不是 ADR——它是 Hermes 在接续项目时**第一个读取的文件**。

### 2. 文件位置

```
~/.hermes/docs/projects/<project-slug>/PROJECT.md
```

每个项目一个子目录，为后续扩展留空间（如项目专属 ADR、design notes 可同目录存放）。

选择 `docs/projects/` 而非项目仓库根目录的原因：

- **跨 repo 统一索引**：Hermes 可以在不进入项目目录的情况下列出所有活跃项目
- **与源码解耦**：项目目录可能被删除、移动、或不在当前机器上
- **与其他设计文档同目录**：ADR、design、research 都在 `docs/` 下，PROJECT.md 与它们形成互补

MEMORY.md 中保留一条指针：
```yaml
- id: MEM-XXX
  text: "项目上下文文件在 ~/.hermes/docs/projects/<slug>/PROJECT.md，每个活跃项目一个子目录"
  status: current
  source: ADR-project-context-layer
  last_confirmed: 2026-06-08
```

### 3. 最小字段

v1 只包含以下字段。不做 14 字段的完整 MEMORY schema，不做 PROJECT.md 自动更新。

#### 3.1 项目身份（必填，创建时填写，低频变更）

```yaml
project:
  slug: hermes-desktop           # 唯一标识，用于文件名和引用
  name: Hermes Desktop           # 可读名称
  repo: /Users/gu/.hermes        # 本地仓库路径（可空，如果是纯远程项目）
  description: "Hermes 桌面客户端 — Codex-like Agent Coding Workbench"
```

#### 3.2 当前状态（必填，高频变更）

```yaml
state:
  - key: git.branch
    value: main
    source: cli:git-branch
    last_confirmed: 2026-06-08
    status: current

  - key: git.last_commit
    value: c084eb3
    source: cli:git-log
    last_confirmed: 2026-06-08
    status: current

  - key: deployment.target
    value: local-only
    source: ADR-codex-like-agent-workbench
    last_confirmed: 2026-06-03
    status: current

  - key: phase.active
    value: "v0.1 — 最小闭环"
    source: ADR-codex-like-agent-workbench
    last_confirmed: 2026-06-03
    status: current
```

状态条目规则：
- `key` 使用点分隔的命名空间（`git.branch`、`deployment.target`、`phase.active`）
- `source` 标注信息来源（CLI 命令、ADR、session）
- `status: current | superseded | deprecated`，遵循 ADD-only 理念——旧状态标记而非删除
- 状态变更时：旧条目 `status → superseded`，新条目 ADD

#### 3.3 活跃决策（可选，引用 ADR）

```yaml
active_decisions:
  - adr: ADR-codex-like-agent-workbench
    title: "Hermes Desktop 定位为 Codex-like Agent Coding Workbench"
    status: current

  - adr: ADR-closeout-memory-check
    title: "Closeout Memory Check — ADD-only + Provenance"
    status: current
```

不复制 ADR 内容，仅做索引引用。`status` 跟踪该决策在当前项目中是否仍然 relevant。

#### 3.4 最近活动（必填，每次 closeout 更新）

```yaml
recent:
  last_session: 2026-06-08
  last_task: "实现 Closeout Memory Check v1 最小版"
  last_outcome: "完成 — verification-loop + orchestration-closeout 已更新"
  source: session-2026-06-08/closeout
```

**recent 是快照区，非完整历史**。最多保留最近 3 条。旧条目从 recent 中移除时不标记 superseded——直接移除即可，因为完整历史以 session/OpenChronicle/Obsidian 为准。recent 的滚动维护不与 ADD-only 原则冲突：recent 是易失的上下文窗口，不是长期记忆条目。类比：OpenChronicle 是完整日志，session_search 是索引，PROJECT.md 的 recent 是缓存——缓存淘汰不需要 provenance 追踪。

#### 3.5 开放风险（可选，有则填）

```yaml
risks:
  - id: RISK-001
    description: "v0.1 尚未接入真实 API，用 fixture 驱动"
    severity: medium
    source: ADR-codex-like-agent-workbench
    status: active
```

### 4. source / last_confirmed / status 规则

与 ADR-closeout-memory-check 保持一致：

| 字段 | 必填 | 说明 | 示例 |
|------|:--:|------|------|
| `source` | ✅ | 信息来源标识 | `cli:git-branch`、`session-2026-06-08/closeout`、`ADR-xxx` |
| `last_confirmed` | ✅ | 最后确认日期 | `2026-06-08` |
| `status` | ✅ | 生命周期 | `current` / `superseded` / `deprecated` |

**source 命名约定**：
- `cli:<command>` — 从终端命令获取（如 `cli:git-branch`、`cli:which-python`）
- `session:<date>/<phase>` — 从会话中确认（如 `session-2026-06-08/closeout`）
- `ADR-<slug>` — 来自架构决策记录
- `user:<date>` — 用户直接告知
- `file:<path>` — 从配置文件读取

**状态变更规则（ADD-only 轻量版）**：
- 同一个 `key` 的新值 → 旧条目 `status: superseded`，新条目 ADD
- 同一个 `key` 的值不再有意义 → `status: deprecated`
- 不允许 DELETE 或覆盖旧值

### 5. 「继续某项目」加载流程

当用户说「继续 hermes-desktop」或类似表述时：

```
Step 1: 匹配项目
  ├── 扫描 ~/.hermes/docs/projects/*/PROJECT.md
  ├── 按 slug / name / repo 关键词匹配
  └── 匹配到 → 读取 PROJECT.md

Step 2: 组装上下文（按优先级）
  ├── [project-context] PROJECT.md recent 段 → 上次做到哪了
  ├── [project-context] PROJECT.md state 段 → 当前分支、部署目标、活跃阶段
  ├── [project-context] PROJECT.md active_decisions → 关联的 ADR 指针
  ├── [memory] MEMORY.md → always-on 稳定事实和指针
  ├── [user] USER.md → 用户偏好（如果项目与用户偏好相关）
  ├── [openchronicle] session_search(project=<slug>, limit=3) → 最近会话摘要
  └── [project-context] PROJECT.md risks → 已知风险

Step 3: 呈现上下文摘要
  ├── 一句话说明项目当前状态
  ├── 上次做到哪了
  ├── 活跃决策列表
  └── 如有开放风险，提醒用户

Step 4: 等待用户指令
  └── 用户确认上下文正确后，开始执行任务
```

**关键设计**：PROJECT.md 是上下文组装的**第一个入口**，不是唯一信息源。它提供足够的信息让 Hermes 「知道自己在哪」，然后根据需要加载其他信息源（ADR、OpenChronicle、Obsidian）。

### 6. 与现有信息源的关系

| 信息源 | 与 PROJECT.md 的关系 | 分工 |
|--------|---------------------|------|
| **MEMORY.md** | MEMORY.md 存 PROJECT.md 的索引指针 | MEMORY: "项目上下文文件在 docs/projects/" → PROJECT: 具体状态 |
| **ADR** | PROJECT.md 引用 ADR，不复制内容 | ADR: 决策的完整论证 → PROJECT: 决策在当前项目中的 relevance |
| **OpenChronicle** | PROJECT.md 的 `recent` 是 OpenChronicle 的 curated 摘要 | OpenChronicle: 完整日志 → PROJECT: 最近 3 条的摘要 |
| **session_search** | 同类信息源，PROJECT.md 更快更结构化 | session_search: 会话间线索 → PROJECT: 稳定基线 |
| **Obsidian Wiki** | PROJECT.md 是 Obsidian 中项目文档的索引入口 | Obsidian: 长文档、参考资料 → PROJECT: 当前状态快照 |
| **hermes-authority-map.md** | PROJECT.md 作为一个新的信息源层级加入 | authority-map: 信息源优先级 → PROJECT: Level 2 注入记忆的一部分 |

**信息源优先级更新**（hermes-authority-map.md 后续更新，v1 不做）：

```
Level 2（注入记忆）新增：
  - [project-context] — 来自 PROJECT.md 的项目当前状态
```

### 7. v1 明确不做的事

| 不做 | 原因 |
|------|------|
| PROJECT.md 自动更新（Agent 直接写入） | 违反人-in-the-loop 原则。状态变更应在 closeout 时提案，人确认后写入 |
| 14 字段完整 MEMORY schema 用于 PROJECT.md | 过度设计。v1 只需 5 个段（project/state/decisions/recent/risks） |
| 多项目自动发现（扫描所有 git repo） | 项目注册应该显式。自动发现会引入噪音 |
| PROJECT.md 与 git 仓库同步 | 不属于源码的一部分。项目状态不应进 git history |
| PROJECT.md 迁移/导入工具 | v1 手动创建即可 |
| hermes-authority-map.md 更新 | v1 不做，待 PROJECT.md 稳定后再补 |
| 跨项目状态聚合面板 | v1 只做单项目上下文恢复，不做 dashboard |
| `hermes project init` CLI 命令 | v1 手动创建文件 |
| PROJECT.md schema 校验脚本 | v1 文件少，人工检查即可 |
| 子 Agent 可写 PROJECT.md | 与 MEMORY.md 一样，子 Agent 只提案不写入 |

---

## 替代方案

### 方案 A：在 MEMORY.md 中放项目状态

- ❌ MEMORY.md 的设计原则是「每次注入的 always-on 稳定事实」，项目状态是 volatile 的
- ❌ 多个项目会让 MEMORY.md 膨胀，违反「精简、稳定」原则
- ❌ 没有解决跨项目索引的问题

### 方案 B：全部靠 session_search + OpenChronicle 恢复

- ❌ 会话超时后上下文不可靠
- ❌ 需要用户提供足够关键词才能搜到
- ❌ 缺乏结构化状态（分支、部署目标、活跃决策）

### 方案 C：每个项目仓库根目录放 PROJECT.md

- ❌ 与源码耦合，项目目录可能不存在
- ❌ 不便 Hermes 做跨项目索引
- ❌ PROJECT.md 的内容（最近活动、风险）不应进入 git history

### 方案 D：本方案（`docs/projects/<slug>/PROJECT.md`）

- ✅ 统一索引
- ✅ 与源码解耦
- ✅ 最小字段，手动可维护
- ✅ 与现有信息源互补不重叠
- ⚠️ 需要手动创建（v1），后续可加 CLI

**选择方案 D。**

---

## 实施阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 1** (本文档) | ADR 确立 PROJECT.md 设计原则 | 无 |
| **Phase 2** | 创建示例 PROJECT.md（hermes-desktop） | Phase 1 |
| **Phase 3** | 定义「继续项目」上下文组装流程 | Phase 2 |
| **Phase 4** | 更新 hermes-authority-map.md 补充 PROJECT.md 层级 | Phase 2 |
| **Phase 5** | 更新 hermes-knowledge-architecture SKILL.md | Phase 4 |

Phase 2-5 不在此 ADR 范围内。此 ADR 只确立设计原则和最小字段。

---

## 附录 A：完整 PROJECT.md 模板

```markdown
# Hermes Desktop — Project Context

<!-- 
  PROJECT.md — Hermes 项目上下文文件
  这是 Hermes 接续项目时第一个读取的文件。
  保持精简。当前状态进 state，决策引用进 active_decisions，详情进 ADR/Wiki。
  
  状态变更规则（ADD-only 轻量版）：
  - 同一 key 的新值 → 旧条目 status: superseded，新条目 ADD
  - 不做 DELETE 或覆盖
-->

## Project

- **slug**: hermes-desktop
- **name**: Hermes Desktop
- **repo**: /Users/gu/.hermes
- **description**: Hermes 桌面客户端 — Codex-like Agent Coding Workbench

## Current State

| key | value | source | last_confirmed | status |
|-----|-------|--------|:--:|:--:|
| git.branch | main | cli:git-branch | 2026-06-08 | current |
| git.last_commit | c084eb3 | cli:git-log | 2026-06-08 | current |
| deployment.target | local-only | ADR-codex-like-agent-workbench | 2026-06-03 | current |
| phase.active | v0.1 — 最小闭环 | ADR-codex-like-agent-workbench | 2026-06-03 | current |

## Active Decisions

| ADR | Title | Status |
|-----|-------|:--:|
| ADR-codex-like-agent-workbench | Hermes Desktop 定位为 Codex-like Agent Coding Workbench | current |
| ADR-closeout-memory-check | Closeout Memory Check — ADD-only + Provenance | current |

## Recent Activity

| Date | Task | Outcome | Source |
|------|------|---------|--------|
| 2026-06-08 | 实现 Closeout Memory Check v1 最小版 | 完成 — verification-loop + orchestration-closeout 已更新 | session-2026-06-08/closeout |

## Open Risks

| ID | Description | Severity | Source | Status |
|----|-------------|:--:|--------|:--:|
| RISK-001 | v0.1 尚未接入真实 API，用 fixture 驱动 | medium | ADR-codex-like-agent-workbench | active |
```

---

*ADR 结束。*
