# Agent Memory Systems 深度研究报告

> 研究日期：2026-06-08
> 研究范围：mem0ai/mem0、getzep/zep、getzep/graphiti、letta-ai/letta
> 目标：为 Hermes Managed Agents 的 Closeout Memory Check、PROJECT.md、记忆分层提供设计参考

---

## 1. mem0ai/mem0

### 1.1 记忆写入机制

**写入触发**：调用方（应用代码/Agent 框架）显式调用 `memory.add(messages, user_id=..., agent_id=..., run_id=...)`。不是自动触发，但框架设计为在每轮对话后调用。

**证据**：README 中的 `chat_with_memories()` 示例显示每次对话后都调用 `memory.add(messages, user_id=user_id)`。源码 `main.py` 的 `add()` 方法签名要求至少传入 `user_id`、`agent_id` 或 `run_id` 之一。

**写入前过滤机制**（V3 架构，2026年4月更新）：

1. **Phase 0 — 上下文收集**：获取最近 10 条消息 (`get_last_messages`)，解析当前消息
2. **Phase 1 — 存续记忆检索**：用当前消息做向量搜索，取 top_k=10 条已有记忆
3. **Phase 2 — LLM 单次提取**：使用 `ADDITIVE_EXTRACTION_PROMPT`，一次 LLM 调用完成全部提取

**【关键设计】V3 的 ADD-only 策略**：
源码和 README 明确声明：
> "Single-pass ADD-only extraction — one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten."

这意味着 mem0 完全放弃了 UPDATE/DELETE 操作，只用 ADD + 链接（linked_memory_ids）来处理新旧记忆的关系。

**去重机制**（从 ADDITIVE_EXTRACTION_PROMPT 中提取）：
- 检查「Recently Extracted Memories」（同会话最近 20 条）—— 首要去重参考
- 检查「Existing Memories」（搜索返回的相关记忆）—— 语义等价检查
- 当新记忆与已有记忆「语义等价」且无实质新信息时跳过
- 当新记忆与已有记忆有关联但不重复时，使用 `linked_memory_ids` 链接到已有记忆 UUID
- 对已知实体（如 "User has a dog named Max"）不阻止提取新事件（如 "User went camping with Max"）

**什么值得记**（从 `FACT_RETRIEVAL_PROMPT` 和 `ADDITIVE_EXTRACTION_PROMPT` 中提取）：
- 存储：个人偏好、重要个人详情、计划和意图、活动偏好、健康偏好、职业详情、杂项
- **不记**：通用助手寒暄（"Sure!", "Great question!"）、模糊的性格判断（除非用户明确确认）、助手对自身能力的元评论

**冲突/过期处理**：
- V3 不做传统冲突解决，而是：新事实 ADD，旧事实保留（不删除），通过 `linked_memory_ids` 建立关联
- 时间锚定：所有相对时间（"上周"、"昨天"）都被解析为绝对日期，基于 Observation Date

### 1.2 记忆读取机制

**检索触发**：调用方显式调用 `memory.search(query, filters={"user_id": ...}, top_k=20)`。

**检索范围**：
- 必须包含 `user_id`、`agent_id` 或 `run_id` 至少一个
- 支持高级元数据过滤（eq/ne/in/nin/gt/gte/lt/lte/contains/AND/OR/NOT）
- 本质上是按会话标识符隔离的多租户设计

**多信号检索**（README 声明）：
> "Multi-signal retrieval — semantic, BM25 keyword, and entity matching scored in parallel and fused."

- 语义搜索（embedding cosine similarity）
- BM25 关键词匹配
- 实体匹配增强（entity boosting）
- 时间感知检索（temporal reasoning）

**来源追踪**：
- 每条记忆存储 role（user/assistant）、actor_id（发言人姓名）
- V3 引入了 entity linking，实体被提取、嵌入并在记忆间链接

### 1.3 架构要点

- **存储后端**：向量数据库（Qdrant/FAISS/ChromaDB 等，通过 VectorStoreFactory 抽象）+ SQLite（历史 DB）
- **LLM 依赖**：写入时需要 LLM 做事实提取（默认 gpt-5-mini），嵌入模型（默认 text-embedding-3-small）
- **去中心化**：纯库模式，无中心服务

---

## 2. getzep/zep

### 2.1 记忆写入机制

**重要背景**：Zep Community Edition 已停止维护，代码移至 `legacy/`。当前 Zep 是云服务平台。

**写入触发**：用户通过 SDK 显式调用 API 将聊天消息、业务数据、事件送入 Zep。

**证据**：README 声明：
> "Add context: Feed chat messages, business data, and events to Zep as they occur"

**自动提取**：
> "Graph RAG: Zep automatically extracts relationships and maintains a temporal knowledge graph that understands how context evolves over time"

这与 Graphiti 的提取机制一致 —— Zep 在后台自动将非结构化数据转化为知识图谱。

**去重/冲突**：由底层 Graphiti 的 temporal knowledge graph 处理（见 Graphiti 章节）。

### 2.2 记忆读取机制

**检索方式**：
> "Retrieve & assemble: Get pre-formatted, relationship-aware context blocks optimized for your LLM"

- 不是简单的向量搜索，而是关系感知的上下文组装
- 提供了 User/Thread/Message 的内置管理层
- 检索延迟声称 <200ms

**隔离设计**：内置 Users 和 Threads 概念，记忆按用户隔离。

### 2.3 架构要点

- Zep = Graphiti + 用户管理 + 对话管理 + 治理 + 仪表板 + 企业功能
- 云服务：SOC2 Type 2 / HIPAA 合规
- 适合企业级生产部署，不适合作为轻量设计参考

**【对 Hermes 的关键启示】**：Zep 本身不适合 Hermes（太重、闭源云服务），但它验证了一个重要设计模式：**Graphiti 作为记忆引擎 + 上层治理层**。

---

## 3. getzep/graphiti

### 3.1 记忆写入机制

**写入触发**：调用方显式调用 `graphiti.add_episode(name, episode_body, source_description, reference_time, group_id=...)`。

**证据**：源码 `graphiti.py` 中 `add_episode()` 方法完整签名。

**写入管线**（从源码和 README 提取）：

1. **Episode 摄入**：原始对话/数据以 Episode 形式进入，保留 source_description 和 reference_time
2. **实体提取** (`extract_entities`)：LLM 从 episode 中提取实体节点，支持自定义 entity_types（Pydantic 模型）
3. **关系提取** (`extract_edges`)：LLM 提取实体间关系/事实，每条边有 `valid_at` 时间戳
4. **去重与消解** (`resolve_extracted_edges`)：
   - 检测重复节点和边
   - 当新事实与已有事实冲突时，将旧边标记为 `invalid_at`（不删除！）
   - 返回三元组：`(resolved_edges, invalidated_edges, new_edges)`
5. **嵌入生成**：为语义搜索生成向量嵌入
6. **图写入**：批量写入图数据库

**【关键设计】Bi-temporal 事实管理**：
README 明确声明：
> "Temporal Fact Management: Facts have validity windows. When information changes, old facts are invalidated — not deleted. Query what's true now, or what was true at any point in time."

这是 Graphiti 最突出的设计 —— 每个事实有 `valid_at`（何时开始为真）和 `invalid_at`（何时被取代），不删除历史。

**Episode 溯源**：
> "Episodes & Provenance: Every entity and relationship traces back to the episodes (raw data) that produced it. Full lineage from derived fact to source."

**去重判断**：
- 节点去重：基于语义相似度合并重复实体
- 边去重：`resolve_extracted_edges` 判断新边是否与已有边等价/冲突/全新
- 冲突信号 = 新信息取代旧信息，触发旧边 invalidate

**自定义本体**：
> "Prescribed & Learned Ontology: Define entity and edge types upfront via Pydantic models (prescribed), or let structure emerge from your data (learned)."

**什么值得记**：
- 通过 `entity_types` 和 `edge_types` 参数控制哪些类型的实体/关系需要提取
- 通过 `excluded_entity_types` 排除不需要的类型
- 通过 `custom_extraction_instructions` 注入自定义提取规则

### 3.2 记忆读取机制

**检索方式**（从 `search.py` 和 `graphiti.py` 提取）：

**混合检索引擎**：
- 语义搜索（cosine similarity + embedding）
- 全文搜索（BM25/fulltext）
- 图遍历（BFS — 从中心节点沿边扩展）
- 以上结果通过 RRF（Reciprocal Rank Fusion）融合
- 可选 cross-encoder 重排序
- 可选 MMR（Maximal Marginal Relevance）去冗余

**搜索范围**：
- Edge 搜索（事实/关系）
- Node 搜索（实体）
- Episode 搜索（原始对话）
- Community 搜索（社区摘要）
- 可组合配置（`SearchConfig`）

**时间维度**（核心特色）：
- 所有搜索支持 `reference_time` 参数
- 可以查询「当前为真」的事实（`invalid_at IS NULL`）
- 可以查询「某个历史时刻为真」的事实
- 可以追踪事实随时间的演变

**隔离机制**：通过 `group_ids` 实现分区隔离，一个 group_id 对应一个用户/项目/会话。

**来源追踪**：
- 每条 Edge 通过 EpisodicEdge 追溯到产生它的 Episode
- Episode 带有 `source_description`（如 "slack_message", "email", "meeting_notes"）

### 3.3 架构要点

- **图数据库**：Neo4j 5.26+ 或 FalkorDB 1.1.2+（Kuzu 已弃用）
- **LLM 依赖**：实体提取 + 关系提取 + 嵌入生成，均需 LLM
- **增量更新**：新数据即时集成，不需批量重算
- **论文**：arXiv 2501.13956

---

## 4. letta-ai/letta

### 4.1 记忆写入机制

**核心架构**（从 MemGPT 论文 2310.08560 和 Letta API 文档提取）：

Letta 的记忆设计源于「LLM as OS」范式，将 Agent 记忆类比计算机的内存层次：

| 层级 | 计算机类比 | Letta 实现 | 说明 |
|------|-----------|-----------|------|
| **Core Memory** | RAM/寄存器 | memory_blocks（如 human、persona） | 始终在 Agent 的上下文窗口中 |
| **Recall Memory** | 虚拟内存 | 上下文窗口管理 + 检索 | Agent 决定哪些记忆「换入」上下文 |
| **Archival Memory** | 磁盘 | 持久化存储（向量 DB + DB） | 长期记忆，通过检索访问 |

**Memory Blocks**（从 API 示例和源码提取）：
- Agent 创建时定义 `memory_blocks`，每个 block 有 `label` 和 `value`
- 常见 label：`human`（用户信息）、`persona`（Agent 人格）
- Block 内容可由 Agent **自行编辑** —— Agent 通过 function/tool call 更新自己的 memory block
- 这是一个关键设计特征：**Agent 控制自己的记忆写入**

**写入触发**：
- 初始写入：创建 Agent 时由开发者设定 memory_blocks
- 运行时写入：**Agent 自己决定何时写** —— Agent 调用 `update_memory` 类型的工具来修改自己的 Core Memory
- 这完全不同于 mem0/Graphiti 的「外部系统决定写什么」，而是「Agent 自己决定写什么」

**证据**：MemGPT 论文描述了 Agent 通过 `conversation_search`、`archival_memory_insert`、`archival_memory_search` 等函数自主管理记忆。

### 4.2 记忆读取机制

**上下文组装**（从论文和 API 设计推断）：
- Agent 启动时，Core Memory blocks 被直接拼入 system prompt
- 超过上下文窗口时，Agent 使用「自我编辑」策略：总结旧内容、释放空间、加载新记忆
- Recall Memory 通过工具调用按需检索
- Archival Memory 通过向量搜索检索

**Agent 隔离**：
- 每个 Agent 有独立的 `agent_state`，包含独立的 Memory 对象
- 不同 Agent 的记忆空间完全隔离
- 没有跨 Agent 共享记忆的机制（by design）

**时间维度**：
- Letta 没有内置的 temporal reasoning
- 记忆的时间性质完全依赖 Agent 自己管理（在文本中写日期）

### 4.3 架构要点

- **设计哲学**：Agent 是自主的 —— 包括记忆管理也是 Agent 自己的事
- **与 MemGPT 的关系**：Letta 是 MemGPT 的商业化/产品化演进
- **存储后端**：PostgreSQL + 向量扩展（从 db 目录可见）
- **子 Agent 支持**：Letta Code 支持 subagents，每个子 Agent 有自己的记忆空间

---

## 5. 对 Hermes 的可借鉴点

### 5.1 A. Closeout Memory Check

**从 mem0 借鉴**：

1. **ADD-only 策略**（V3 最关键的转变）
   - Hermes 的 Closeout Memory Check 应该只做 ADD 判断，不做 UPDATE/DELETE
   - 新旧信息的关联通过 linking 实现（如「参见之前的决策 ADR-003」）
   - 这从根本上避免了「覆盖有价值历史」的风险

2. **值得记 vs 不值得记的判断标准**（从 ADDITIVE_EXTRACTION_PROMPT 提取）：
   - ✅ 值得记：偏好变更、新决策、项目状态变更、重要日期、新实体引入、可复用经验
   - ❌ 不值得记：通用寒暄、模糊判断未被确认的、已有等价记忆的、一次性临时信息

3. **去重检查清单**：
   - 检查同 session 内已写入的记忆（Recently Extracted Memories）
   - 检查已有记忆文件中语义等价的条目
   - 已知实体不阻止新事件，但同一事实不重复写入

**从 Graphiti 借鉴**：

4. **Episode 溯源概念**
   - 每条记忆应追溯到「哪个任务/会话的哪轮对话」
   - Hermes 可以通过 OpenChronicle 的 session_id + turn_id 实现轻量溯源
   - 不需要图数据库，只需要一个 `source` 字段

5. **Bi-temporal 轻量版**
   - 不删除旧记忆，而是标记 `superseded_at`
   - 适合 PROJECT.md 中的状态字段

**从 Letta 借鉴**：

6. **不借鉴 Letta 的 Agent 自写模式**
   - Letta 允许 Agent 自己编辑 Core Memory，这对 Hermes 是反模式
   - Hermes 应该保持：**人在回路，Agent 提案，人确认**

### 5.2 B. PROJECT.md / Project Context

**从 Graphiti 借鉴的字段设计**：

```yaml
# PROJECT.md 参考结构
project:
  name: hermes-managed-agents
  last_confirmed: 2026-06-08

decisions:
  - id: DEC-001
    title: "使用文件级记忆而非向量数据库"
    source: session-2026-06-01/turn-45
    valid_from: 2026-06-01
    status: current        # current | superseded | deprecated
    superseded_by: null
    confirmed_by: user-gu

state:
  - key: "verification-loop.version"
    value: "v2.1"
    source: ADR-012
    last_confirmed: 2026-06-08
    status: current

risks:
  - id: RISK-003
    description: "子 Agent 自动写入导致记忆污染"
    severity: high
    mitigation: "Closeout Memory Check 需人工确认"
    source: session-2026-05-15/turn-102
    status: active
```

**从 mem0 借鉴的 scope 设计**：
- `user_id` / `agent_id` / `run_id` 三层隔离
- Hermes 应支持 `project_id` / `agent_id` / `session_id` 三层 scope

**核心原则**：
- 每条状态必须有 `source`（追溯来源）
- 每条状态必须有 `last_confirmed`（时效性判断）
- 每条状态必须有 `status`（区分当前/过期/被取代）

### 5.3 C. ADR / Wiki / Skill 分层

**分层决策矩阵**（综合四个项目的设计理念）：

| 内容类型 | 写入位置 | 判断标准 | 借鉴来源 |
|---------|---------|---------|---------|
| **架构决策** | ADR | 涉及系统结构、技术选型、不可逆的选择 | Graphiti 的 prescribed ontology 理念 |
| **项目状态** | PROJECT.md | 当前有效、需频繁更新、有 status 字段 | Graphiti 的 bi-temporal + mem0 的 ADD-only |
| **用户偏好/习惯** | USER.md | 跨项目稳定、个人化、低频变更 | mem0 的 user memory 概念 |
| **可复用经验/规则** | Skill | 可执行、有输入输出契约、版本化 | Letta 的 memory block label + Skill 概念 |
| **知识/参考资料** | Obsidian Wiki | 结构化知识、需要双向链接、长期价值 | 无直接借鉴，Hermes 自有设计 |
| **会话上下文** | session only | 仅当次任务相关、不具复用价值 | Graphiti 的 Episode 概念（原始数据层） |
| **经验教训** | MEMORY.md | 跨项目通用、低频但高价值、有教训性质 | mem0 的 linked_memory_ids 关联模式 |

**写入权限分层**：

| 操作 | 权限 | 机制 |
|------|------|------|
| 写入 MEMORY.md | 仅人确认 | Closeout Memory Check 输出提案 → 人审批 → 写入 |
| 写入 USER.md | 仅人确认 | 同上 |
| 写入 PROJECT.md | 人确认后自动 | Closeout 时 Agent 提案状态变更 → 人确认 → 自动更新 |
| 写入 ADR | 仅人确认 | ADR 有独立审批流程 |
| 写入 Obsidian Wiki | 仅人 | Agent 不直接写 Wiki |
| 写入 Skill | 仅人 | Skill 有版本管理和测试要求 |
| 写入 session | 自动 | OpenChronicle 自动记录 |

---

## 6. 不适合 Hermes 的部分

### 6.1 太重不适合的设计

| 设计 | 来源 | 原因 |
|------|------|------|
| **向量数据库** | mem0, Graphiti, Letta | Hermes 基于文件系统，引入向量 DB 破坏简洁性 |
| **Neo4j/FalkorDB 图数据库** | Graphiti | 运维成本极高，Hermes 的场景用文件级 linking 足够 |
| **LLM 自动事实提取** | mem0, Graphiti | 每次写入都调用 LLM 做提取，token 成本高，不适合 CLI 工具 |
| **云服务依赖** | Zep | 完全违背 Hermes 本地优先的原则 |
| **Managed graph infrastructure** | Zep | 企业级治理在 Hermes 的规模下是过度设计 |

### 6.2 破坏 Agent 隔离的设计

| 设计 | 来源 | 原因 |
|------|------|------|
| **Agent 自写 Core Memory** | Letta | 子 Agent 自行编辑记忆块 → 越权，无法审计 |
| **全局共享记忆空间** | mem0（如不设 filter） | mem0 虽然支持 scope，但如果放任全局搜索则破坏隔离 |

### 6.3 导致记忆污染的设计

| 设计 | 来源 | 原因 |
|------|------|------|
| **LLM 自动提取无人工审核** | mem0, Graphiti | LLM 提取会出错、会幻觉、会遗漏关键信息 |
| **Agent 自主 UPDATE/DELETE** | Letta | Agent 可能基于错误推理删除正确记忆 |
| **自动总结（recursive summarization）** | Letta/MemGPT | 递归总结会导致信息蒸馏失真（35.3% 准确率 vs Zep 94.8%） |

**证据**：Zep 的 benchmark 数据显示 recursive summarization 在 DMR 上只有 35.3% 准确率，而结构化记忆系统达到 94.8%。

### 6.4 暂时不该做的设计

| 设计 | 原因 |
|------|------|
| 自动知识图谱构建 | 需要 LLM 持续运行、图数据库运维，收益在当前规模不明确 |
| Agent 运行时记忆自管理 | 破坏 Hermes 的人-in-the-loop 原则 |
| 记忆向量化/语义搜索 | 文件级 grep + session_search 已能覆盖当前需求 |
| 跨 Agent 记忆共享 | 先做好单 Agent 的记忆管理，再考虑共享 |
| 自动过期/淘汰 | 先做好写入控制，淘汰策略可以后加 |

---

## 7. 最终结论

### 7.1 结论表

| 项目 | 值得学的机制 | 不该学的机制 | 对 Hermes 的具体建议 |
|------|-------------|-------------|----------------------|
| **mem0** | ① ADD-only 策略（不覆盖，只积累+链接）② 三层 scope（user/agent/run）③ 去重检查清单（Recently Extracted + Existing）④ 值得记/不值得记的分类标准 | ① 向量数据库 ② LLM 自动事实提取 ③ UPDATE/DELETE 操作的旧版 API | Closeout Memory Check 采用 ADD-only 策略，每次 closeout 只提案新增记忆，生成 linked_memory_ids 关联已有记忆 |
| **Zep** | ① Context Assembly 概念（记忆不只是检索，而是组装成结构化上下文）② User/Thread 管理层设计模式 | ① 云服务架构 ② 闭源商业产品 ③ 整个 Zep CE（已弃用） | 不直接借鉴 Zep 的具体实现，但验证了 Graphiti 的 temporal KG 路线是有效的 |
| **Graphiti** | ① Bi-temporal 事实管理（valid_at/invalid_at，不删除）② Episode 溯源（每条记忆追溯到原始对话）③ 自定义本体（prescribed entity_types）④ group_id 分区隔离 | ① Neo4j/FalkorDB 图数据库 ② LLM 驱动的实体+关系提取管线 ③ 复杂的多信号搜索架构 | PROJECT.md 采用轻量 bi-temporal 字段；每条状态加 source/last_confirmed/status；ADR 用 prescribed ontology 思路定义字段结构 |
| **Letta** | ① Memory Block 标签化组织（human/persona/label）② Agent 独立记忆空间 | ① Agent 自写记忆（越权）② Recursive summarization（准确率仅 35.3%）③ OS 式记忆层次（对 Hermes 过度设计） | Hermes 记忆分层参考 block label 思路：USER.md / MEMORY.md / PROJECT.md / ADR / Skill / session 六层；强调 Agent 只能提案不能直接写 |

### 7.2 Closeout Memory Check 应该补充的判断标准

```
✅ 值得记入长期记忆：
  - 用户明确表达的偏好变更（与 USER.md 中现有内容不同）
  - 架构/技术决策（应进 ADR，Closeout 只做索引引用）
  - 项目状态变更（应进 PROJECT.md）
  - 可复用的经验教训（有「为什么」和「如何应用」的）
  - 新引入的实体/概念/术语定义
  - 被验证有效的操作模式/工作流

❌ 不值得记：
  - 与已有记忆语义等价的（去重检查）
  - 仅当次会话相关的临时上下文
  - 通用寒暄和过程性对话
  - Agent 的推测/猜测未被用户确认的
  - 一次性任务的具体执行细节（除非有教训）
  - 可以从 git/project 文件推导出的信息

⚠️ 需要人工判断：
  - 部分正确的信息（需要修正后再记）
  - 可能很快过时的信息（加 expires 标记）
  - 敏感信息（需要确认脱敏后再记）
```

### 7.3 PROJECT.md 应该参考的字段

```yaml
# 每条项目状态记录应包含：
- id: 唯一标识符
- key: 状态键（如 "deployment.target", "api.version"）
- value: 当前值
- source: 来源（session_id/turn_id 或 ADR 编号）
- last_confirmed: 最后确认日期
- valid_from: 该状态开始生效的日期
- status: current | superseded | deprecated
- superseded_by: 取代此条目的记录 ID（可选）
- confirmed_by: 确认者（user/agent_id）
- notes: 补充说明（可选）
```

### 7.4 Hermes 记忆分层写入规则

```
Layer 1: session（OpenChronicle）
  - 写入方式：自动
  - 写入者：系统
  - 内容：完整会话日志
  - 生命周期：永久存档，但不在上下文窗口

Layer 2: MEMORY.md
  - 写入方式：Closeout 提案 → 人确认 → 写入
  - 写入者：人（Agent 提案）
  - 内容：跨项目通用经验、教训、模式
  - 去重：检查已有条目，只 ADD 不 UPDATE

Layer 3: USER.md  
  - 写入方式：人直接编辑
  - 写入者：仅人
  - 内容：用户偏好、习惯、个人上下文
  - Agent 可建议但不可写入

Layer 4: PROJECT.md
  - 写入方式：Closeout 提案 → 自动更新（状态类）/人确认（决策类）
  - 写入者：Agent 提案，自动或人工执行
  - 内容：项目当前状态、活跃决策、风险
  - 每条带 source + last_confirmed + status

Layer 5: ADR
  - 写入方式：独立审批流程
  - 写入者：人
  - 内容：架构决策记录
  - Agent 可起草但不可直接写入

Layer 6: Obsidian Wiki
  - 写入方式：仅人
  - 写入者：仅人
  - 内容：结构化知识、参考资料
  - Agent 完全不可写

Layer 7: Skill
  - 写入方式：版本化开发流程
  - 写入者：人
  - 内容：可复用的能力模块
  - 有测试要求
```

### 7.5 是否建议现在引入任何新依赖

**不建议引入任何新依赖。**

具体而言：

- ❌ **不建议引入 mem0**：虽然 ADD-only 策略值得借鉴，但 mem0 依赖向量数据库 + LLM 自动提取，对 Hermes 当前架构是过度引入。mem0 的价值在设计理念，不在代码。
- ❌ **不建议引入 Graphiti**：图数据库（Neo4j）+ LLM 提取管线的依赖太重。bi-temporal + provenance 的设计理念可以直接在 Markdown 文件 + YAML frontmatter 中实现轻量版。
- ❌ **不建议引入 Zep Cloud**：云服务，完全违背本地优先原则。
- ❌ **不建议引入 Letta**：Agent 自写记忆的模式与 Hermes 的人-in-the-loop 原则冲突。

**建议的方向**：
1. 在 Closeout Memory Check 中实现「ADD-only + linked_memory_ids」的判断逻辑
2. 在 PROJECT.md 中引入轻量 bi-temporal 字段（valid_from/status/source）
3. 不需要任何新数据库或新服务
4. 不需要任何新的 LLM 调用（Closeout 时已有 LLM 上下文，直接做判断即可）
5. 当前的文件级（Markdown + YAML frontmatter）+ OpenChronicle + session_search 组合已足够

---

## 参考来源

1. mem0ai/mem0 README: https://github.com/mem0ai/mem0 — V3 ADD-only extraction, multi-signal retrieval, benchmarks
2. mem0ai/mem0 源码 `mem0/memory/main.py` — add() 管线（Phase 0-2）、search() API、三层 scope
3. mem0ai/mem0 源码 `mem0/configs/prompts.py` — ADDITIVE_EXTRACTION_PROMPT、FACT_RETRIEVAL_PROMPT、去重规则
4. Mem0 论文: arXiv 2504.19413 — 架构描述、benchmark 对比
5. getzep/zep README: https://github.com/getzep/zep — Zep 平台描述、与 Graphiti 关系、Community Edition 弃用说明
6. getzep/graphiti README: https://github.com/getzep/graphiti — Context Graph 概念、bi-temporal design、episode provenance
7. getzep/graphiti 源码 `graphiti_core/graphiti.py` — add_episode() 管线、resolve_extracted_edges、edge invalidation
8. getzep/graphiti 源码 `graphiti_core/search/search.py` — 混合搜索（语义+BM25+BFS+RRF+cross-encoder+MMR）
9. Graphiti/Zep 论文: arXiv 2501.13956 — Temporal Knowledge Graph Architecture for Agent Memory
10. Zep Blog: "State of the Art in Agent Memory" — DMR 94.8%、LongMemEval、recursive summarization 35.3%
11. letta-ai/letta README: https://github.com/letta-ai/letta — memory_blocks API、Agent 创建示例
12. MemGPT 论文: arXiv 2310.08560 — LLM as OS、Memory hierarchy（Core/Recall/Archival）、Agent 自管理记忆
13. letta-ai/letta 源码 `letta/agent.py` — Agent 类、Memory 对象、BlockManager
