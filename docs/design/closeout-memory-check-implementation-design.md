# Closeout Memory Check — Implementation Design

> 基于 ADR-closeout-memory-check (2026-06-08)
> 本文档定义 Closeout Memory Check 的判断标准、字段 schema 和写入分层规则
> 不包含代码实现，仅设计规范

---

## 1. Closeout Memory Check 判断标准

### 1.1 值得记入长期记忆（MEMORY.md）

满足以下**任意一条**，即值得提案写入：

| # | 类别 | 判断标准 | 示例 |
|---|------|---------|------|
| M1 | **架构决策** | 涉及系统结构、技术选型、不可逆选择的决策 | "Hermes 确认不使用向量数据库，所有记忆基于文件级 Markdown" |
| M2 | **项目状态变更** | 项目当前运行状态的关键信息变更 | "deployment target 从 Vercel 变更为自有服务器" |
| M3 | **可复用经验教训** | 包含「为什么」和「如何应用」的经验 | "递归总结在 benchmark 中准确率仅 35.3%，Hermes 采用 ADD-only 而非自动总结" |
| M4 | **新实体/概念引入** | 新引入的系统组件、术语、外部服务 | "引入 Closeout Memory Check 作为 hermes-orchestration-closeout 的新阶段" |
| M5 | **已验证有效的模式** | 被实际执行验证有效的操作模式/工作流 | "ADD-only+linked_memory_ids 模式在去重场景下比 UPDATE/DELETE 更安全" |
| M6 | **跨项目通用知识** | 不限于当前项目的通用规则或方法 | "bi-temporal 标记 (valid_from/superseded_at) 适用于所有需要历史追踪的状态字段" |

### 1.2 不值得记入长期记忆

以下情况**不应**提案写入：

| # | 类别 | 判断标准 | 为什么不记 |
|---|------|---------|-----------|
| X1 | **语义等价条目** | 与已有记忆对比，内容语义等价且无实质性新信息 | 去重——避免记忆膨胀 |
| X2 | **仅当次会话上下文** | 只对当前会话有意义，下次会话不再需要 | 会话过期后无价值 |
| X3 | **通用寒暄/过程对话** | "好的"、"明白了"、Agent 的确认性回复 | 无信息量 |
| X4 | **未被确认的推测** | Agent 推测但用户未明确确认的信息 | 可能错误，污染记忆 |
| X5 | **一次性任务执行细节** | 某次任务的具体执行步骤（除非有教训） | OpenChronicle 已记录，不需要进入 MEMORY.md |
| X6 | **可从 git/project 推导的信息** | 代码已记录的事实（如"某文件存在"） | 冗余——保持 MEMORY.md 精简 |
| X7 | **按日期标注的事件日志** | "2026-06-08: 完成了 XX" | 一周后过期，违反 MEMORY.md 「不存临时进展」规则 |
| X8 | **与 SOUL.md 重复的内容** | Agent 编制、操作规则、工具路由等 SOUL 已覆盖的 | MEMORY.md 与 SOUL.md 双写漂移——SOUL 覆盖的从 MEMORY 删除 |

### 1.3 需要人工判断的灰色地带

| # | 场景 | 处理方式 |
|---|------|---------|
| G1 | 部分正确的信息 | 先修正再提案，不要直接写入半真半假的内容 |
| G2 | 可能很快过时的信息 | 提案时标注 `expires_after` 建议（如 "2 周后复核"） |
| G3 | 包含敏感信息 | 脱敏后再提案（如 API key → "已配置"） |
| G4 | 不确定是否值得记 | 列出利弊，交由人判断 |

---

## 2. Closeout Memory Check 去重检查流程

在提案任何新记忆前，必须执行以下检查：

### 2.1 检查顺序

```
1. 同 session 内去重
   ├── 检查本 session 内 Closeout Memory Check 是否已提案过相同内容
   └── 如果是 → 跳过

2. MEMORY.md 语义去重
   ├── 读取当前 MEMORY.md 所有条目
   ├── 逐条对比：新记忆与已有条目是否语义等价？
   │   ├── 完全等价 + 无新信息 → 跳过（X1）
   │   ├── 部分重叠 + 有新增信息 → ADD + linked_to 已有条目
   │   └── 冲突（新信息取代旧结论） → ADD + supersedes 旧条目，旧条目 status → superseded
   └── 关系字段留空当无关联

3. SOUL.md 去重
   ├── 检查新记忆是否被 SOUL.md 的某章完全覆盖
   └── 如果是 → 跳过（X8），不在 MEMORY.md 留镜像

4. 信息源验证
   ├── 新记忆是否可从 git log / config.yaml / agent-registry.json 等文件直接推导？
   └── 如果是 → 跳过（X6）

5. 临时性检查
   ├── 新记忆是否是一个按日期标注的事件日志？
   └── 如果是 → 跳过（X7），建议写入 Obsidian 或仅保留在 session
```

### 2.2 去重判断矩阵

| 新记忆与已有记忆的关系 | 操作 | 关系字段 |
|----------------------|------|---------|
| 语义等价，无新信息 | **跳过** | — |
| 语义等价但表述更精确 | **跳过**（不上报，除非精度提升显著影响决策） | — |
| 部分重叠，有新增信息 | **ADD** | `linked_to: [旧条目ID]` |
| 新信息取代旧结论 | **ADD** + 旧条目 `status → superseded` | `supersedes: [旧条目ID]`, 旧条目 `superseded_by: [新条目ID]` |
| 完全无关 | **ADD** | 无关系字段 |

---

## 3. 记忆条目字段 Schema

### 3.1 MEMORY.md 条目 Schema

```yaml
# 每条记忆条目（YAML frontmatter 或 YAML block）
- id: MEM-XXX           # 唯一标识符，格式 MEM-<序号>
  text: "..."           # 记忆内容（一句话或短段落）
  status: current       # current | superseded | deprecated
  source: "..."         # 来源标识（必填）
  last_confirmed: YYYY-MM-DD  # 最后确认日期（必填）
  # 以下为可选字段
  category: "..."       # 分类标签（decision | state | lesson | entity | pattern）
  confirmed_by: "..."   # 确认者（user-gu / agent-hermes/proposal）
  valid_from: YYYY-MM-DD     # 生效日期
  supersedes: [MEM-XXX]      # 被此条目取代的旧条目 ID 列表
  superseded_by: MEM-XXX     # 取代此条目的新条目 ID
  linked_to: [MEM-XXX]       # 关联但不取代的其他条目 ID 列表
  expires_after: YYYY-MM-DD  # 建议复核日期
  notes: "..."          # 补充说明
```

### 3.2 PROJECT.md 状态条目 Schema

```yaml
# 项目状态条目
state:
  - key: "deployment.target"           # 状态键
    value: "vercel"                    # 当前值
    source: session-2026-06-01/turn-045  # 来源
    last_confirmed: 2026-06-01         # 最后确认
    status: current                    # current | superseded | deprecated

  - key: "api.version"
    value: "v2.8.1"
    source: ADR-verify-task-dual-status-validation
    last_confirmed: 2026-06-02
    status: current

decisions:
  - id: DEC-001
    title: "使用文件级记忆而非向量数据库"
    source: ADR-closeout-memory-check
    valid_from: 2026-06-08
    status: current
    confirmed_by: user-gu

risks:
  - id: RISK-001
    description: "子 Agent 自动写入导致记忆污染"
    severity: high
    mitigation: "Closeout Memory Check 需人工确认，Agent 只提案不写入"
    source: session-2026-06-08/turn-012
    status: active
```

### 3.3 字段来源对照

| Schema 字段 | 来源借鉴 | 说明 |
|------------|---------|------|
| `status: current \| superseded \| deprecated` | Graphiti 的 bi-temporal (valid_at/invalid_at) | 轻量版：不删旧状态，标记生命周期 |
| `source` | Graphiti 的 Episode provenance | 每条 fact 必须追溯到产生它的原始数据 |
| `last_confirmed` | mem0 的 observation_date | 区分「很久以前确认的」和「最近刚确认的」 |
| `supersedes` / `superseded_by` | mem0 的 linked_memory_ids | ADD-only 下唯一允许的「覆盖」方式 |
| `category` | Letta 的 memory block labels | 给记忆打标签，便于分层检索 |
| `valid_from` | Graphiti 的 valid_at | 事实生效时间 |
| `confirmed_by` | Hermes 自己的人-in-the-loop 模型 | 确认可追溯到具体的人或 Agent |

---

## 4. 记忆分层写入规则

### 4.1 七层架构

```
Layer 1: session (OpenChronicle)
  ├── 写入方式: 自动
  ├── 写入者: 系统
  ├── 内容: 完整会话日志
  ├── 生命周期: 永久存档，但不在上下文窗口
  └── 权限: 不需要 Closeout Memory Check

Layer 2: MEMORY.md
  ├── 写入方式: Closeout 提案 → 人确认 → 写入
  ├── 写入者: 人（Agent 提案）
  ├── 内容: 跨项目通用经验、教训、模式、always-on 稳定事实
  ├── 策略: ADD-only + linked_to/supersedes
  └── 权限: Agent 只提案，不直接写

Layer 3: USER.md
  ├── 写入方式: 仅人直接编辑
  ├── 写入者: 仅人
  ├── 内容: 用户偏好、习惯、个人上下文
  └── 权限: Agent 不可提案，不可写

Layer 4: PROJECT.md
  ├── 写入方式: Closeout 提案 → 状态字段自动执行 / 决策字段人确认
  ├── 写入者: Agent（状态）+ 人（决策）
  ├── 内容: 项目当前状态、活跃决策、风险
  └── 每字段: source + last_confirmed + status

Layer 5: ADR
  ├── 写入方式: 独立审批流程
  ├── 写入者: 仅人
  ├── 内容: 架构决策记录
  └── 权限: Agent 可起草，不可直接写入

Layer 6: Obsidian Wiki
  ├── 写入方式: 仅人
  ├── 写入者: 仅人
  ├── 内容: 结构化知识、参考资料、长文档
  └── 权限: Agent 完全不写

Layer 7: Skill
  ├── 写入方式: 版本化开发流程
  ├── 写入者: 仅人
  ├── 内容: 可复用的能力模块
  └── 权限: 有测试要求
```

### 4.2 分层决策矩阵

Closeout Memory Check 对每条候选信息，按以下矩阵决策写入目标：

| 信息特征 | 写入层 | 判断关键词 |
|---------|--------|-----------|
| 仅本次任务相关，无复用价值 | **Layer 1 (session)** | 一次性、临时、仅此任务 |
| 跨项目通用、经验教训、稳定事实 | **Layer 2 (MEMORY.md)** | 每次注入、跨项目、教训 |
| 用户个人偏好 | **Layer 3 (USER.md)** | 偏好、习惯、风格 |
| 项目当前状态、活跃决策 | **Layer 4 (PROJECT.md)** | 状态、版本、部署目标、风险 |
| 架构级决策、不可逆选择 | **Layer 5 (ADR)** | 技术选型、架构变更 |
| 参考资料、工具配置、长文档 | **Layer 6 (Obsidian Wiki)** | 参考、配置手册、笔记 |
| 可执行工作流、操作手册 | **Layer 7 (Skill)** | 步骤、流程、checklist |

### 4.3 优先级（当一条信息匹配多个层时）

```
ADR > Skill > PROJECT.md > MEMORY.md > USER.md > Obsidian Wiki > session
```

解释：如果一条信息满足 ADR 的写入条件（架构决策），即使它也满足 MEMORY.md 的写入条件（跨项目经验），也应优先进入 ADR。MEMORY.md 中只放指向 ADR 的指针。

---

## 5. Closeout Memory Check 工作流

### 5.1 阶段流程

```
hermes-orchestration-closeout
  │
  ├── Phase 1: Task Summary
  │   └── 任务完成后生成执行摘要
  │
  ├── Phase 2: Verification Loop
  │   └── 验证任务输出是否符合预期
  │
  ├── Phase 3: Closeout Memory Check  ← 本设计的作用域
  │   ├── Step 1: 收集候选记忆
  │   │   ├── 遍历本次任务的关键决策点
  │   │   ├── 提取可复用的经验教训
  │   │   ├── 识别项目状态变更
  │   │   └── 生成候选记忆列表
  │   │
  │   ├── Step 2: 去重检查
  │   │   ├── 同 session 去重
  │   │   ├── MEMORY.md 语义去重
  │   │   ├── SOUL.md 去重
  │   │   ├── 信息源验证（git/project 可推导？）
  │   │   └── 临时性检查（事件日志？）
  │   │
  │   ├── Step 3: 生成提案
  │   │   ├── 为每条通过去重的候选记忆：
  │   │   │   ├── 分配 ID（MEM-XXX）
  │   │   │   ├── 填写 source / last_confirmed / status
  │   │   │   ├── 填写关系字段（linked_to / supersedes）
  │   │   │   ├── 标注 category
  │   │   │   └── 写入目标判断（MEMORY.md / PROJECT.md / 仅 session）
  │   │   └── 生成 Markdown 格式的提案文本
  │   │
  │   ├── Step 4: 呈现提案
  │   │   ├── 按写入目标分组展示
  │   │   ├── 每组标注：「哪些是新增」「哪些关联已有」「哪些取代旧条目」
  │   │   └── 附带「建议跳过」条目及跳过理由
  │   │
  │   └── Step 5: 等待确认
  │       ├── 人逐条确认/修改/拒绝
  │       ├── 确认后执行写入（Agent 写入，但仅写入人确认过的条目）
  │       └── 同时更新旧条目的 status/superseded_by 字段
  │
  └── Phase 4: Cleanup
      └── 清理临时文件、更新 session 索引
```

### 5.2 提案输出格式

```markdown
## Closeout Memory Check — 提案

### 新增 MEMORY.md 条目 (2)

- [ ] **MEM-051**: Hermes 确认不使用向量数据库，所有记忆基于文件系统
  - source: session-2026-06-08/adr-closeout-memory-check
  - last_confirmed: 2026-06-08
  - status: current
  - supersedes: MEM-042
  - category: decision

- [ ] **MEM-052**: ADD-only + linked_memory_ids 模式在去重场景下比 UPDATE/DELETE 更安全
  - source: session-2026-06-08/turn-032
  - last_confirmed: 2026-06-08
  - status: current
  - category: lesson

### 更新已有条目 (1)

- [ ] **MEM-042**: status current → superseded, superseded_by: MEM-051

### PROJECT.md 状态变更 (1)

- [ ] **deployment.memory_strategy**: ADD-only, source: ADR-closeout-memory-check, status: current

### 建议跳过 (2)

- [ ] "2026-06-08 完成 Closeout Memory Check ADR" — 事件日志，不进 MEMORY.md
- [ ] "Hermes memory 架构为三层" — SOUL.md § 信息源优先级已覆盖
```

---

## 6. 对现有 Hermes 架构的兼容性

### 6.1 不变的部分

- MEMORY.md 仍然是一个 Markdown 文件，在每轮对话开始时注入 system prompt
- USER.md 仍然是仅人编辑
- Obsidian Wiki 仍然仅人写入
- OpenChronicle 仍然自动记录所有会话
- Skill 仍然有版本管理和测试要求
- SOUL.md 仍然是 Hermes 身份和边界的最高权威
- hermes-authority-map.md 仍然是信息源优先级的权威指引

### 6.2 新增的部分

- MEMORY.md 条目增加 YAML 结构化字段（id, source, last_confirmed, status 等）
- Closeout Memory Check 成为 hermes-orchestration-closeout 的标准阶段
- PROJECT.md 获得明确的 schema 定义
- 记忆写入权限分层有了明确的 Agent 边界

### 6.3 移除的部分

- 不再允许 Agent 在无提案/无确认的情况下修改 MEMORY.md
- 不再允许按日期的事件日志条目进入 MEMORY.md
- 不再允许与 SOUL.md 重复的内容留在 MEMORY.md

---

## 7. 实施检查清单

在开始 Phase 2（判断标准编写）前，确认以下前提：

- [ ] ADR-closeout-memory-check 已获确认（本文档依赖的 ADR）
- [ ] 现有 MEMORY.md 条目已盘点（共多少条，哪些需迁移）
- [ ] MEMORY.md 现有条目中已识别出与 SOUL.md 重复的条目
- [ ] PROJECT.md 当前状态已盘点（哪些字段需保留，哪些缺 source）
- [ ] hermes-orchestration-closeout 的现有流程已阅读

---

## 附录 A：借鉴来源速查

| 机制 | 来源 | 借鉴程度 |
|------|------|:--:|
| ADD-only（不覆盖，只积累） | mem0 V3 | 完全采纳 |
| linked_memory_ids（关联不取代） | mem0 V3 ADDITIVE_EXTRACTION_PROMPT | 采纳 |
| status: current/superseded/deprecated | Graphiti bi-temporal | 采纳（轻量版） |
| episode provenance（source 追踪） | Graphiti EpisodicNode | 采纳（用 session_id/turn_id 替代图节点） |
| 写入前去重检查 | mem0 ADDITIVE_EXTRACTION_PROMPT | 采纳（文件级实现） |
| Memory Block 标签化 | Letta memory_blocks | 部分采纳（用 category 字段） |
| Agent 自写记忆 | Letta Core Memory self-edit | **不采纳** |
| 向量数据库 | mem0, Graphiti, Letta | **不采纳** |
| 图数据库 | Graphiti (Neo4j/FalkorDB) | **不采纳** |
| LLM 自动事实提取 | mem0, Graphiti | **不采纳**（用人工确认替代） |
| Recursive summarization | Letta/MemGPT | **不采纳**（准确率仅 35.3%） |

---

*Implementation Design 结束。*
