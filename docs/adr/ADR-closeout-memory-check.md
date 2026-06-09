# ADR: Closeout Memory Check

**状态**: Accepted + Implemented + Verified (v1)
**日期**: 2026-06-08
**作者**: Gu + Hermes
**作用域**: `verification-loop` Step 5 + `hermes-orchestration-closeout` Step 4
**实施说明**: 
  - v1 实现已部署到两个 skill 中（verification-loop → Closeout Memory Check，closeout → Memory Check）
  - 马蒂尼自处理路径通过流程自检意识覆盖
  - Phase 2-5 已冻结，不继续扩展

---

## 背景

Hermes 当前已有完善的知识架构（MEMORY.md / USER.md / OpenChronicle / Obsidian Wiki / ADR / Skill / session），但缺少一套系统化的「任务结束后，什么该写入长期记忆、什么不该写」的判断标准。具体痛点：

1. **知识流失**：任务结束后，决策上下文和经验教训只留在会话中，会话过期即消失
2. **上下文组装不稳定**：开工前从 MEMORY.md / OpenChronicle / session_search 中组装上下文时，缺少统一的组装优先级
3. **记忆分散**：决策、项目状态、经验分散在不同层级，缺乏统一写入规则
4. **越权风险**：子 Agent 没有写入长期记忆的权限定义，存在自动乱写的风险

同期，我们完成了对 mem0、Zep、Graphiti、Letta 四个开源 Agent Memory 系统的深度研究（见 `docs/research/agent-memory-systems-research.md`）。研究结论：

- **mem0 V3** 的最大教训：ADD-only 策略——放弃 UPDATE/DELETE，只做 ADD+链接，避免覆盖历史
- **Graphiti** 的核心创新：bi-temporal 事实管理（valid_at/invalid_at，不删除旧事实）+ episode 溯源
- **Letta** 的反面教材：Agent 自写 memory block 会导致越权和记忆污染
- **Zep** 的验证：recursive summarization 准确率仅 35.3%，结构化记忆达到 94.8%

**核心结论**：不引入任何新依赖，只吸收设计原则到 Hermes 现有的文件级记忆架构中。

---

## 决策

### 1. ADD-only 写入策略

Closeout Memory Check **只允许提出「新增记忆」**。

**禁止的操作**：
- UPDATE — 不允许修改已有记忆条目的内容
- DELETE — 不允许删除已有记忆条目
- OVERWRITE — 不允许用新值覆盖旧值
- 自动替换已有结论

**允许的操作**：
- ADD — 新增记忆条目
- LINK — 通过 `linked_to` 字段关联已有记忆
- SUPERSEDE — 通过 `supersedes` / `superseded_by` 建立新旧关系
- STATUS CHANGE — 通过 `status` 字段标记条目生命周期

### 2. 冲突处理：多字段关系模型

当新旧信息冲突时，不覆盖旧条目，而是通过关系字段建立链接：

```yaml
# 旧条目保持原样，仅 status 变更
- id: MEM-042
  text: "Hermes 使用 Qdrant 作为向量存储后端"
  status: superseded           # 从 current → superseded
  superseded_by: MEM-051      # 指向新条目

# 新条目 ADD，引用旧条目
- id: MEM-051
  text: "Hermes 已确认不使用向量数据库，所有记忆基于文件系统 (Markdown + YAML frontmatter)"
  status: current
  supersedes: MEM-042          # 引用被取代的旧条目
  source: session-2026-06-08/adr-closeout-memory-check
  last_confirmed: 2026-06-08
```

### 3. 强制 Source / Provenance 追踪

所有长期记忆候选**必须**带有来源信息。至少包含：

| 字段 | 含义 | 必填 | 示例 |
|------|------|:--:|------|
| `source` | 该记忆的来源标识 | ✅ | `session-2026-06-08/turn-045`、`ADR-closeout-memory-check`、`OpenChronicle/recall` |
| `last_confirmed` | 最后确认日期 | ✅ | `2026-06-08` |
| `status` | 生命周期状态 | ✅ | `current` / `superseded` / `deprecated` |

推荐扩展字段：

| 字段 | 含义 | 触发条件 |
|------|------|---------|
| `confirmed_by` | 确认者标识 | 人工确认时填写 (`user-gu` / `agent-hermes/proposal`) |
| `valid_from` | 该事实开始为真的日期 | 信息有明显时效起点时填写 |
| `supersedes` | 被此条目取代的旧条目 ID | 新信息取代旧信息时填写 |
| `superseded_by` | 取代此条目的新条目 ID | 旧条目被取代时回填 |
| `linked_to` | 关联但不取代的其他条目 | 信息相关但不冲突时填写 |

### 4. 写入权限分层

| 写入目标 | 谁可提案 | 谁可写入 | 机制 |
|---------|---------|---------|------|
| MEMORY.md | Closeout Memory Check | **仅人确认后** | Agent 生成提案 → 人审批 → 写入 |
| USER.md | 无（Agent 不可提案） | **仅人** | Agent 不可写 |
| PROJECT.md (状态字段) | Closeout Memory Check | Agent 自动（状态变更） | 提案中状态变更可自动执行 |
| PROJECT.md (决策字段) | Closeout Memory Check | **仅人确认后** | 同 MEMORY.md |
| ADR | 无（需独立流程） | **仅人** | ADR 有独立审批流程 |
| Obsidian Wiki | 无 | **仅人** | Agent 完全不写 Wiki |
| Skill | 无 | **仅人** | Skill 有版本管理和测试要求 |
| session (OpenChronicle) | 系统自动 | 系统自动 | 完整会话日志 |

---

## 为什么

### 为什么是 ADD-only

1. **信息不可逆**：覆盖记忆是不可逆的信息丢失。mem0 在 V3 中验证了 ADD-only 在大规模 benchmark 上的有效性（LoCoMo 91.6, LongMemEval 94.8），证明积累+链接优于替换+删除
2. **审计可追溯**：ADD-only 天然保留了记忆的状态变化历史，从「当前是什么」能追溯到「以前是什么」「谁改的」「什么时候改的」
3. **降低判断负担**：Closeout 时不需判断「这条该不该删」「这条需不需要改」，只需判断「有没有值得记的新东西」，降低 Agent 出错面
4. **Graphiti 的 bi-temporal 验证**：Graphiti 的高准确率（LongMemEval +18.5% vs full-context）证明了「不删除、标记过期」优于「覆盖旧值」

### 为什么需要 Source 追踪

1. **去重需要知道来源**：判断「这是不是新信息」时，必须知道它来自哪个 session 的哪轮对话
2. **信任需要知道来源**：来自 ADR 的结论和来自 Agent 推测的结论，信任度不同
3. **Graphiti 的 Episode 溯源**：每条 derived fact 追溯到原始 episode 的设计，验证了 provenance 在生产系统中的价值

### 为什么 Agent 不能直接写

1. **Letta 的教训**：Agent 自写 Core Memory 的模型下，Agent 可以基于错误推理修改自己的记忆，形成反馈循环
2. **Hermes 的人-in-the-loop 原则**：SOUL.md 明确规定「关键不确定、不可逆操作先确认再执行」——写入长期记忆是不可逆的信息操作
3. **子 Agent 隔离**：Managed Agents 架构下，子 Agent 不应修改主控 Agent 的记忆空间

---

## 影响范围

### 需要变更的文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `skills/hermes-orchestration-closeout/SKILL.md` | 新增 | 新增 Closeout Memory Check 阶段，含 ADD-only 判断逻辑 |
| `memories/MEMORY.md` | 格式升级 | 现有条目补全 `source`、`last_confirmed`、`status` 字段 |
| `docs/hermes-authority-map.md` | 更新 | 补充 Closeout Memory Check 的写入规则 |
| `docs/adr/ADR-closeout-memory-check.md` | 新增 | 本文档 |

### 不需要变更的部分

- **不引入新数据库**：所有记忆仍在 Markdown + YAML frontmatter 中
- **不引入新依赖**：不需要 mem0 / Graphiti / Letta / 向量数据库 / 图数据库
- **不修改 Agent 路由**：Closeout Memory Check 是主控 Agent（Hermes）的任务收尾阶段，不涉及子 Agent 调度变更
- **不修改 OpenChronicle**：session 日志自动记录不受影响

---

## 替代方案评估

### 方案 A：保持现状，不做 Closeout Memory Check

- ❌ 任务结束后知识继续流失
- ❌ 重复踩坑，每次重构/排障从头开始
- ✅ 零变更成本

### 方案 B：接入 mem0 作为记忆后端

- ❌ 引入向量数据库（Qdrant/FAISS）+ LLM 自动提取依赖
- ❌ 每次写入调用 LLM 做事实提取，token 成本高
- ❌ 对 Hermes CLI 工具的简洁性有根本破坏
- ✅ 开箱即用的去重和搜索

### 方案 C：本方案（ADD-only + Provenance + 人确认）

- ✅ 不引入新依赖
- ✅ 与 Hermes 现有文件级记忆架构兼容
- ✅ 明确 Agent 权限边界（提案 ≠ 写入）
- ✅ 可逆——关系字段（status/supersedes）比物理删除安全
- ⚠️ 需要人工确认环节，不是全自动

**选择方案 C**。

---

## 实施阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 1** (本文档) | ADR 确立 ADD-only + Provenance 设计原则 | 无 |
| **Phase 2** | 编写 Closeout Memory Check 判断标准（值得记/不值得记清单） | Phase 1 |
| **Phase 3** | 定义 PROJECT.md 字段 schema | Phase 1 |
| **Phase 4** | 更新 `hermes-orchestration-closeout` skill | Phase 2, 3 |
| **Phase 5** | 现有 MEMORY.md 条目迁移（补全 source/last_confirmed/status） | Phase 2 |

Phase 2-5 不在此 ADR 范围内。此 ADR 只确立设计原则。

---

## 附录 A：研究来源

本 ADR 的设计决策基于以下研究：

1. mem0ai/mem0 README + 源码 `mem0/memory/main.py` + `mem0/configs/prompts.py` — V3 ADD-only extraction, multi-signal retrieval
2. Mem0 论文: arXiv 2504.19413 — 架构描述, benchmark 对比
3. getzep/graphiti README + 源码 — bi-temporal fact management, episode provenance, hybrid search
4. Graphiti/Zep 论文: arXiv 2501.13956 — Temporal Knowledge Graph Architecture for Agent Memory
5. Zep Blog: "State of the Art in Agent Memory" — DMR 94.8% vs recursive summarization 35.3%
6. letta-ai/letta README + MemGPT 论文 (arXiv 2310.08560) — Agent memory hierarchy, Agent 自写记忆模式
7. Hermes SOUL.md — Managed Agents 架构、人-in-the-loop 原则、操作边界
8. Hermes hermes-knowledge-architecture SKILL.md — 三层知识架构、Memory 审计方法

详见 `docs/research/agent-memory-systems-research.md` 完整研究报告。

---

*ADR 结束。*
