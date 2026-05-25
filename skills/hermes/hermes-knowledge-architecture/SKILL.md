---
name: hermes-knowledge-architecture
description: "Hermes 知识架构管理 — memory + Obsidian 外脑 + skill。Memory 只存 always-on 稳定事实、外脑指针和第一层逻辑；procedural knowledge 进 skill；全量配置、历史和长文档进 Obsidian。按阶段或用户要求用工程控制论梳理闭环。"
triggers:
  - memory 满
  - memory limit
  - 外脑
  - obsidian memory
  - knowledge architecture
  - 知识分层
  - memory migration
  - external brain
  - memory too long
  - 存储空间
  - memory 自动整理
  - 档案原则
  - 控制论梳理 skill
tags: [hermes, memory, knowledge-management, obsidian, engineering-cybernetics]
agents: [hermes]
---

# Hermes 知识架构

> 最后更新: 2026-05-21 (v9 — 增加 SOUL/Identity Document Upgrade Workflow)

### Session Context Recovery Protocol (会话超时恢复)

**Trigger**: User returns after session expired (inactivity timeout), references previous context you've lost. User signals: "我不是说了吗", "你忘了？", "别明天了现在做", "检查就过时无更新？".

### Problem
Hermes sessions expire due to inactivity timeout. When the user returns, the conversation context is gone — no memory of what was being discussed or what task was in progress. The user doesn't know sessions expire and interprets the loss as you not paying attention.

### Recovery Flow

1. **Don't say "no context" without trying.** Immediately gather evidence in parallel:
   - `mcp_openchronicle_recent_activity(limit=10)` — past 30 min of user activity
   - `mcp_openchronicle_current_context()` — what's on the user's screen right now
   - `session_search(query=<keywords from user message>, limit=3)` — past conversations
   - `cronjob(list)` — pending scheduled tasks

2. **Cross-reference signals**: Feishu docs open, Codex conversations, Chrome tabs → topic clues. Recent activity apps → task type. Session search → past task context.

3. **Make an informed hypothesis**: say what you CAN infer, even if partial.

4. **If still can't find context, explain the root cause (session expiry), not "I checked and found nothing"**:
   - ❌ "检查就过时无更新？" (sounds like negligence)
   - ✅ "上一轮会话超时过期了，上下文被清空。你甩个链接或说个主题，我立刻开搞。"

5. **Proactively suggest next steps** based on what you CAN infer from screen state and recent activity.

### Preventative: context anchoring
During long multi-step tasks (VNS pipeline, deployment, image gen), periodically save critical task state to memory so it survives session expiry.

### Pitfalls — communicate what you're doing
- ❌ Don't ask "what were we talking about?" — frustrates users who assume persistence
- ❌ Don't claim "checked but nothing found" — explain WHY (session expiry)
- ✅ Do check OpenChronicle + session_search + current_context in parallel

---

## SOUL/Identity Document Upgrade Workflow

**Trigger**: You and the user have confirmed a new architectural principle, behavioral rule, or decision framework that changes how Hermes operates. Needs to be preserved beyond the current conversation.

### The Problem

Without a preservation workflow, architectural decisions live only in the current conversation's context. When the session ends, the reasoning disappears. The next time the same question arises, you start from scratch — or worse, do the wrong thing because the rule wasn't recorded.

### Workflow: Backup → Modify → Document → Index → Memory

When the user confirms a new principle (e.g. Managed Agents framework, anti-pattern ban):

1. **Backup**: Before modifying SOUL.md, copy the current version to `~/.hermes/docs/soul-backups/SOUL.md.<YYYY-MM-DD>`
   - `mkdir -p ~/.hermes/docs/soul-backups`
   - `cp ~/.hermes/SOUL.md ~/.hermes/docs/soul-backups/SOUL.md.<YYYY-MM-DD>`

2. **Modify SOUL.md**: Write the principle into SOUL.md's relevant section (usually "四、核心哲学").
   - Keep it dense — one paragraph per principle, not session-level detail.
   - The principle itself goes in SOUL.md. The reasoning and analysis behind it goes in step 3.

3. **Document in Obsidian Wiki**: Create a permanent decision record under the appropriate theme directory.
   - For Hermes architecture: `个人知识库/3-知识/wiki/AI与Agent/Hermes/<决策主题>.md`
   - Include: core framework (comparison table if applicable), decision timeline, key reasoning, related file links, decision status (locked/finalized)
   - Also include any deep analysis that arose during the conversation (e.g. "本体升级 vs SOUL 升级" comparison)

4. **Update the Obsidian index.md**:
   - Add a file reference to `AI与Agent/index.md` Hermes table
   - Add a "最新决策" annotation under the section heading if this is a major decision

5. **Record in Memory**: Add a compact summary entry to persistent memory so the next session knows what happened:
   ```
   2026-05-21: Managed Agents(编制制)架构确认为 Hermes 操作模式，写入 SOUL.md 核心哲学 + Obsidian wiki。SOUL 备份: ~/.hermes/docs/soul-backups/SOUL.md.2026-05-21。
   ```

### Pitfalls
- ❌ Don't skip the backup — SOUL.md has no version control of its own
- ❌ Don't write session-level narrative into SOUL.md — SOUL is for principles, not story
- ❌ Don't create the Obsidian doc without updating index.md — it becomes invisible
- ❌ Don't leave the reasoning only in conversation — it won't survive session expiry
- ✅ Do keep the Obsidian entry decision-focused: what was decided, when, by whom, and why. Not the full conversation transcript.
- ✅ Do mark the decision as "已确认，锁定（不重新讨论）" when the user explicitly rules out re-debating it

### Related: Hermes本体升级 vs SOUL升级 comparison

When a Hermes engine upgrade (`hermes update`) is pending alongside a SOUL upgrade, the two are fundamentally different and should not be confused:

| Dimension | Engine Upgrade (hermes update) | Identity Upgrade (SOUL.md) |
|-----------|-------------------------------|---------------------------|
| What changes | Code, tools, providers, gateway protocols | Behavior rules, decision frameworks, role boundaries |
| Who writes it | Upstream Hermes team | Gu + Hermes together |
| Gu's role | Consumer — decides whether to merge | Designer — defines how the system operates |
| Rollback | `git reset` backup branch | Patch SOUL.md back (no formal versioning) |
| Verification | Tests + gateway checks + feishu replies | Observe subsequent conversations for compliance |
| Risk | Service outage, merge conflicts, feature regressions | Rule inconsistency, behavioral drift |
| Recommendation | Wait for tagged releases; don't chase every commit | Always backup before modifying — communicate what you're doing
- ❌ Don't ask "what were we talking about?" — frustrates users who assume persistence
- ❌ Don't claim "checked but nothing found" — explain WHY (session expiry)
- ✅ Do check OpenChronicle + session_search + current_context in parallel

---


> 核心原则：Memory 是 always-on 稳定注入层，Skill 是流程库，Obsidian 是外脑和全量持久存储，session_search 是短期会话线索。当前主 Agent 有核心 skill 白名单；子 Agent 的 registry `skills` 白名单机制已被代码支持，但 live registry 尚未填充显式 skills 数组。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│              Hermes 知识架构 (三层)                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  第一层: Hermes Memory (每次对话注入)                       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  只存 always-on 稳定信息：                              │ │
│  │  • Obsidian vault 路径（文件读写根）                   │ │
│  │  • USER.md 指针和少量长期稳定用户偏好                    │ │
│  │  • 第一层逻辑：控制论、先研究再动手、迭代验证              │ │
│  │  • 一条指针：「系统配置→Obsidian; 流程→skill」          │ │
│  │  • 写入分类规则：memory / Obsidian / skill / 不保存      │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  第二层: Skill (~/.hermes/skills/)                       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  存「可变的」procedural knowledge：                    │ │
│  │  • 具体流程、步骤、workflow                           │ │
│  │  • 工具用法、API 调用模式、debug 路径                  │ │
│  │  • 每次任务复盘的输出（非底层逻辑的部分入 skill）         │ │
│  │  • 阶段性或按需用控制论做反馈闭环：查漏洞→更新→去重→补缺 │ │
│  └─────────────────────────────────────────────────────┘ │
│                    ↓ (read_file / search_files)            │
│  第三层: Obsidian Wiki (无大小限制)                        │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  个人知识库/3-知识/wiki/AI与Agent/                     │ │
│  │  ├── 系统环境配置.md    ← 工具/CLI/API/端口全量配置    │ │
│  │  ├── Open Design笔记.md ← 单工具完整笔记               │ │
│  │  ├── 大模型API配置手册.md ← API Key 汇总              │ │
│  │  ├── Agent网页研究工具链.md ← CLI 工具栈               │ │
│  │  └── index.md          ← 导航索引，从这开始             │ │
│  └─────────────────────────────────────────────────────┘ │
│                    ↓ (session_search)                      │
│  第四层: 前次会话日志                                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  • 已完成任务的上下文（跨会话保留）                      │ │
│  │  • 临时 TODO、调试记录、一次性的任务日志                 │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 指导原则

### 首要标准：钱学森工程控制论

作为第一层逻辑，用于抽象底层规律、驱动 skill 演进和形成闭环；不是每个任务都机械套术语或扩大范围。知识管理可用这五条评判：
1. **系统论** — 整体大于部分之和，从系统层面看知识架构而非局部优化
2. **控制论 — 反馈闭环** — 感知状态 → 比较目标差 → 执行调整 → 再感知（见「阶段性控制论梳理」）
3. **从定性到定量综合集成** — 不凭感觉判断 memory 满不满，用占用率数据说话
4. **顶层设计** — 先定知识分类体系（三层），再按规则落子
5. **可靠性** — 容错机制：memory 满了不会丢信息，Obsidian 有索引可导航

### 三层分类：什么放哪里

| 放 Memory | 放 Skill | 放 Obsidian Wiki |
|-----------|----------|-----------------|
| always-on 稳定事实 | 具体步骤、流程、workflow | 全量配置、环境信息 |
| 外脑/skill 指针 | 工具用法、API 调用模式 | 工具安装路径和版本号 |
| 第一层逻辑（控制论边界、先研究再动手） | Debug 路径、问题修复流程 | API 端点和调用方式 |
| Vault 路径（文件读写必须知道） | 可复用检查清单和验证步骤 | 端口配置和 CORS 设置 |
| 少量长期稳定用户偏好索引 | 多步骤操作手册 | Bug 修复记录和根因分析 |
| 写入分类规则 | 值得复用的复盘产物 | 项目特定知识（如 OD 笔记） |

**判断标准**：这件事如果下次会话还是一样的做法 → 存 skill。如果只是参考信息、配置、历史或可能变 → 存 Obsidian。如果是 Gu 长期稳定偏好 → 存 USER.md。如果是 Hermes 总是需要注入的底层系统事实或外脑指针 → 存 MEMORY.md。临时任务进度、一次性错误、未经确认的软件栈不保存。

### 归档规则

- **触发条件**：用户要求整理、阶段性复盘、或发现 Memory 注入变噪
- **阈值**：> **80%**（~1,760 chars）
- **动作**：将低频工具/配置类条目迁至 `系统环境配置.md`，只留用户偏好索引+外脑指针+底层逻辑
- **典型可迁移条目**：工具路径、版本号、API 端点、端口配置、已修 bug 详情、一次性环境信息
- **边界**：不默认自动改写核心记忆；除非用户授权或当前任务明确要求整理。

## Agent-Scoped Skills — 部分落地，待补 registry 白名单（2026-05-18 校准）

> **状态：代码能力已支持，当前配置未完全启用 registry 白名单**
> 设计目标仍是方案 A 双向锁定（agent-registry 白名单 + SKILL.md 标签双重过滤）。
> 当前 live registry `/Users/gu/.hermes/config/agent-registry.json` 尚未给各 Agent 填充 `subagent_profile.skills` 数组，所以不能把现状描述为「registry 白名单已完全落地」。
> 实施详情见 Obsidian wiki：[[Hermes/Agent-Scoped-Skills-设计提案]]

### 解决的问题

之前所有 Agent 全量加载 65+ skill（92 条记录），子 Agent 0 skill 白板启动。目标效果：

| Agent | 之前 | 之后 |
|-------|------|------|
| Hermes（主控） | 92 全量（~2K-3K token/轮） | **8 核心 skill** |
| deepseek-tui / claude / codex | 0（白板） | 4-7 编码类 |
| openclaw | 0（白板） | 3 调研/浏览器类 |
| pirlo | 0（白板） | 3 设计类 |
| nesta | 0（白板） | 5 技术分析类 |

### 当前实现机制

1. `SKILL.md` frontmatter → `agents: [...]` 标签，声明 intended visibility
2. `agent/prompt_builder.py` → `_skill_matches_agent()` 过滤 + `build_skills_system_prompt(agent_id=...)`
3. `HERMES_CORE_SKILLS` 常量 → 主 Agent 只显示核心 skill
4. `agent-registry.json` → 代码支持读取每个 Agent 的 `subagent_profile.skills` 白名单，但当前 live registry 尚未填充该字段
5. `tools/delegate_tool.py` → 如果 registry 中存在 `profile.skills`，子 Agent 启动时会注入 scoped skills + `skills` 工具集

### 代码文件

- `~/.hermes/hermes-agent/agent/skill_utils.py` — `extract_skill_agents()` + `get_agent_profile_skills()`
- `~/.hermes/hermes-agent/agent/prompt_builder.py` — `_skill_matches_agent()` + `build_skills_system_prompt(agent_id=...)`
- `~/.hermes/hermes-agent/tools/delegate_tool.py` — `_build_child_agent()` skills 注入
- `~/.hermes/hermes-agent/tests/agent/test_skill_scoping.py` — 32 个测试

### 新增 Skill 标准流程

以后新增 SKILL.md 时：

1. 写 SKILL.md（正常写，name 字段作为匹配 key）
2. 在 frontmatter 末尾加 `agents: [hermes]`（默认主 Agent 用）
3. 只有确定子 Agent 也该用时，才规划更新 `agent-registry.json` 中对应 Agent 的 `skills` 数组；当前先保持标签驱动和文档校准，不批量填白名单

仅改 SKILL.md 通常不需要重启 gateway；修改 `agent-registry.json` 后按 delegation skill 的规则重启相关 gateway。

### 设计历史

以下为原始设计方案记录，供参考：

#### 背景问题

| 维度 | 主 Agent（Hermes） | Named Agent（deepseek-tui 等） |
|------|-------------------|-------------------------------|
| 技能数 | 160+ 全量加载 | 0 个加载 |
| Token 开销 | 每轮 4K-6K（约 16% 非核心提示词） | 每个子进程额外推理成本（无领域知识） |
| 认知干扰 | 写代码时出现 baoyu-comic/spotify 等无关描述 | 没有编码规范、debug 路径、流程指导 |
| 错误率 | 模型可能误加载 partial-match 不相关 skill | 子 Agent 重头摸索流程，常出错 |

### 根因：上下文污染（Context Pollution）

**这是 Agent-Scoped Skills 方案的首要驱动因素，不是 Token 节省。** Token 节省是锦上添花，上下文污染才是用户不用的根本原因。

**什么是上下文污染**：
1. **执行痕迹污染** — Agent 执行任务时的中间输出（搜索结果摘要、代码报错、403/500 调试信息、终端日志）塞满对话上下文，用户看到的不是干净对话而是\"脏活记录\"
2. **记忆漂移** — 聊完编码任务后，短期记忆混入技术术语，导致紧接着聊营销方案时 persona 偏移
3. **领域串台** — 不同领域 skill 描述混在一起，Agent 不知道当前该用哪个 persona

**用户原话**：*\"最大的痛点就是我感觉会被污染，然后它的记忆，它的 Agent 的设定都会被改变。\"*

**设计推论**：只省 Token 不解决污染等于没解决。多 Bot Profile 隔离比单 Bot skill 裁剪更直接——因为它做的是会话级隔离。

### 设计方案（已实施）

扩展 `agent-registry.json` 中每个 Agent 的 `subagent_profile`，新增 `skills` 字段。以下为历史参考，实际已选择方案 A 并落地。

#### 方案 A：双向锁定（agent-registry 白名单 + SKILL.md 标签）

注册文件写死每个 agent 加载哪些 skill，skill 的 frontmatter 加 `agents` 标签做二次匹配。

```json
"deepseek-tui": {
  "subagent_profile": {
    "skills": ["github-code-review", "python-debugpy"]
  }
}
```
```yaml
# SKILL.md frontmatter
agents: [deepseek-tui, claude, codex]
```

**优点**：双向约束，不易出错。**缺点**：改一个 agent 的 skill 要改两个地方。

#### 方案 B：纯标签驱动（只有 SKILL.md 标签）

每个 skill 的 frontmatter 写 `agents` 列表，agent 启动时自动扫描标签匹配的 skill。

**优点**：单点维护，加新 skill 只要写标签。**缺点**：agent 视角不知道"我应该有哪些 skill"，全靠 skill 自己声明。

#### 方案 C：双向 + 交集校验

skill 声明 `agents`，agent-registry 也声明 `skills`，启动时取交集。冲突时自动告警。

**优点**：最严谨，适合多人协作。**缺点**：复杂度最高。

#### 子 Agent Skill 分配表（初版）

```json
"deepseek-tui": {
  ...
  "subagent_profile": {
    "toolsets": ["file", "terminal"],
    "skills": [
      "github-code-review",
      "python-debugpy",
      "nextjs-standalone-deployment",
      "hermes-tool-input-repair-layer"
    ],
    ...
  }
}
```

Skill 本身的 frontmatter 也加 `agents` 标签，声明哪些 Agent 需要它：

```yaml
---
name: python-debugpy
agents: [deepseek-tui, claude, codex]  # 只给编码 Agent
category: software-development
---
```

### 预计效果

| Agent | 加载技能数 | 每轮节省 Token |
|-------|-----------|---------------|
| Hermes（主控） | ~8-10 核心 | -4K~6K |
| deepseek-tui | ~4-6 编码相关 | - |
| claude | ~4-6 编码相关 | - |
| openclaw | ~2-3 桌面操作 | - |
| hermes-internal | ~2-3 分析方法论 | - |

### 优先级分级

Implementation priority（供参考，取决于 Hermes 版本路线图）：

1. **P0** — 在 `agent-registry.json` 的 `subagent_profile` 中新增 `skills` 字段（schema 变更）
2. **P0** — 给所有现有 SKILL.md frontmatter 加 `agents` 标签
3. **P1** — 修改 `agent/skill_commands.py`，按 agent 过滤技能加载
4. **P1** — 修改 `tools/delegate_tool.py`，子 Agent 初始化时加载 scoped skills
5. **P2** — 主 Agent 白名单化（仅加载核心技能 + 按任务动态注入）

### 已有基建参考

- `channel_skill_bindings`（`config.yaml` 的 feishu 段）— 已支持按频道绑定技能，是技能作用域化的先例
- `hermes-subagent-delegation` skill — 详细记录了 agent-registry.json 结构和子 Agent 配置

### 完整设计文档

完整的 Agent-Scoped Skills 设计方案（含实现方案分阶段计划、开放式问题、收益估算）已存入 Obsidian wiki：

```markdown
[[Hermes/Agent-Scoped-Skills-设计提案]]
```

路径：`3-知识/wiki/AI与Agent/Hermes/Agent-Scoped-Skills-设计提案.md`

### Profile-Level Skills Management

> This is the CURRENT approach (filesystem-level), distinct from the FUTURE Agent-Scoped Skills design above.

### How profiles inherit skills

When created via `hermes profile create <name> --clone`, a profile copies the full skill tree (~155 categories). This is fast but bloated — most sub-agents don't need 90% of them.

### Trimming by role

Each role type needs a different subset. Reference mapping from actual trimming (2026-05-13):

| Role | Keep categories | Example |
|------|----------------|---------|
| **总助（马蒂尼）** | Core system + orchestration + content/design + social/info | hermes, devops, creative, research, html-ppt, social-media, kanban-board |
| **技术专员（内斯塔）** | Technical + system + devops | devops, github, software-development, autonomous-ai-agents, mcp |
| **方案策划（皮尔洛）** | Content/planning + design + devops | creative, design-brief, html-ppt, web-prototype, devops, huashu-design |
| **质量审核（安布罗西尼）** | Analysis/review + system | critique, devops, hermes, data-science, research, software-development |

### ⚠️ Profile skill trimming vs Agent-Scoped Skills 的区别

**Profile-level trimming**（通过 `hermes profile create --clone` + 删减 profile 下的 skill 目录）对主 Agent 的 prompt token **没有效果**——系统始终从 `~/.hermes/skills/` 全量注入。这是 by design：主控（马蒂尼）需要看到所有 skill 才能正确派发。

**真正起效的是 Agent-Scoped Skills**（当前为代码支持 + 主 Agent 白名单，子 Agent registry 白名单待补）：
- 主 Agent（Hermes）只加载 8 个核心 skill（`HERMES_CORE_SKILLS`）
- 子 Agent 目前主要依赖 SKILL.md 的 `agents` 标签表达意图；只有在 registry 补齐 `subagent_profile.skills` 后，才是严格双向过滤

所以结论：**别折腾 profile 裁剪省 token，那没效果。Agent-Scoped Skills 的 `build_skills_system_prompt(agent_id=...)` 才是正确的路径**。

### ⚠️ Kanban pitfall: devops category must be available

Every profile that receives kanban tasks must have access to the `kanban-worker` skill, which lives under the `devops` category. If you trimmed `devops` from a profile, kanban dispatcher will crash with:

```
Error: Unknown skill(s): kanban-worker
consecutive_crashes=3 | most_recent_outcome=crashed
```

**Fix**: symlink the global devops directory into the profile's skills:

```bash
ln -s /Users/gu/.hermes/skills/devops /Users/gu/.hermes/profiles/<profile>/skills/devops
```

Verify: `hermes -p <profile> --skills kanban-worker -z "hello"`

### Quick overview of category contents

| Category | Contains |
|----------|----------|
| `devops` | kanban-worker, kanban-orchestrator |
| `hermes` | hermes-webui, hermes-knowledge-architecture, hermes-cron-management |
| `creative` | sketch, pixel-art, comfyui, architecture-diagram, humanizer, claude-design |
| `software-development` | debugging-hermes-tui-commands, hermes-agent-skill-authoring, python-debugpy, spike, node-inspect-debugger, open-design-ops |

## 阶段性控制论梳理 Skill

当一个阶段结束、完成明显工作量、用户提醒，或某个 skill 连续暴露偏差时，对相关 skill 做一次控制论反馈闭环：

1. **检查漏洞 (Perception)** — 每个 skill 今天的调用是否报错？有没有遗漏的步骤或参数？
2. **更新 (Comparison)** — 对比实际执行和 skill 描述，找出偏差（过时的命令、改版后的 API、新增的 flag）
3. **去重 (Regulation)** — 两个 skill 是否覆盖同一类任务？合并或建立互相引用
4. **补缺 (Adaptation)** — 今天发现的新的 workflow 是否值得创建一个新 skill？还是加到现有 umbrella 下？

这个流程本身就是控制论的体现：感知→比较→调节→适应。

### 什么时候迁移到 Obsidian

**信号**: Memory 占用 > 80%，且含有大量工具/环境/API 类条目。

**时机**: 用户提出类似「Memory 快满了怎么办」或新发现一个工具配置需要记录。

### 迁移步骤

1. **盘点 memory** — 读全部条目，按「偏好的」「方法的」「环境的」分类
2. **创建/更新 Obsidian 文件**
   - 工具/环境条目 → `3-知识/wiki/AI与Agent/系统环境配置.md`
   - 单工具详细笔记 → `3-知识/wiki/AI与Agent/<工具名>笔记.md`（如 `Open Design笔记.md`）
   - 遵循已有文件格式：前有概览/后有表格
   - ⚠️ iCloud deadlock: 如果 iCloud 报 "Resource deadlock avoided"，用 `write_file` 工具（通常能绕过），或 `brctl evict` 后重试
3. **清理 memory** — 删除所有已迁移条目
4. **加指针** — 加一条：「全工具/环境配置已迁至 Obsidian：个人知识库/3-知识/wiki/AI与Agent/系统环境配置.md。需查工具路径/API/CLI/端口信息时，read_file 该文件。」
5. **更新 index.md** — 在 `3-知识/wiki/AI与Agent/index.md` 的「工具与集成」段落添加链接

### 什么时候读 Obsidian 而不是靠记忆

触发条件（任一匹配就 read_file）：
- 需要查工具路径、版本号、端口
- 需要查 API 端点或调用方式
- 用户问起某个之前修复过的 bug
- 用户说"看一下XXX配置"
- 进行需要精确路径/参数的操作

### 写 Obsidian 文档的格式规范

参照已有的 `Open Design笔记.md` 风格：
- 文件名中文、有头部的单行简介
- 一级标题 = 主题名
- 目录（可选，长文档推荐）
- 最后有「相关链接」段落
- 索引用 `[[wikilink]]` 格式

## 参考文件

- For the full migration example, see the session transcript for 2026-05-05 — "Memory 快满了" → created `系统环境配置.md`, freed 1,200+ chars in memory.
- **[references/2026-05-06-cli-tool-inventory-and-patterns.md](references/2026-05-06-cli-tool-inventory-and-patterns.md)** — Full CLI tool audit: tools I was underusing (lark-cli, gh, tesseract, jq, hermes doctor/insights/logs), correct usage patterns, and iCloud deadlock workaround. Read this for "before going manual, check CLI tools" principle.
- **[references/2026-05-15-agent-scoped-skills-implementation-pitfalls.md](references/2026-05-15-agent-scoped-skills-implementation-pitfalls.md)** — Batch SKILL.md frontmatter modification pitfalls: safe vs unsafe patterns for YAML frontmatter editing, JSON modification strategy, multi-repo management.
- **[references/2026-05-15-mcp-audit-workflow.md](references/2026-05-15-mcp-audit-workflow.md)** — Full-system MCP inventory audit: how to check Hermes/Claude Code/DeepSeek TUI/npm/uv/pip for all MCP servers, version checking, and cleanup.

---

## External Content Ingestion — Learning from Tutorials/Posts

**Pattern:** User sends a link (Xiaohongshu, blog, video, tutorial) → Agent needs to extract, learn, and document.

### Workflow

1. **Extract content** — use the best tool for the source:
   - Plain text page: `browser_navigate` → `browser_snapshot` (DOM text)
   - Image-based (Xiaohongshu carousel): `browser_get_images` → download → OCR/vision (see `browser-automation-for-blocked-sites` skill)
   - Video: `browser_navigate` → extract description/comments, or use dedicated subtitle tool

2. **Understand and categorize** — what class of knowledge is this?
   - **Tool/methodology we don't have** → consider installing (ask first if non-trivial)
   - **Tool/methodology we already have** → map each feature to our existing capabilities
   - **General inspiration** → save as Obsidian reference note

3. **Map to existing toolchain** — for each skill/concept in the post, make a preliminary mapping

4. **🧪 CRITICAL: Verify claims in source code before documenting.** This is the step that prevents factual errors.
   - Search the Hermes Agent source code (`~/.hermes/hermes-agent/`) for each claimed feature
   - Use `search_files` with multiple keywords (short name, long form, alternative spellings)
   - Check the built-in skills directory (`skills/`) — many features exist as SKILL.md, not as standalone tools
   - Check the Obsidian wiki docs for any existing documentation
   - Only after source verification, finalize the mapping with accurate status: ✅ implemented / ❌ not found / ⚠️ partial
   - **If the post mentions features under a specific system name (Hermes vs OpenClaw vs Claude Code), verify which system the feature actually belongs to** — don't assume all features belong to the same system

5. **Document in Obsidian wiki**:
   - Create `3-知识/wiki/AI与Agent/<topic>-参考.md` (reference doc)
   - Structure: overview table (with verified status) → per-skill detailed mapping → conclusion (what we have, what we're missing)
   - Update `index.md` with a link to the new file
   - Optionally check off items in the "待 ingest" section

6. **Update 系统环境配置.md** if the session revealed new tool versions or config changes

### Mapping Table Format (after source verification)

```markdown
| # | Skill | Post Claim | ✅ Verified | Implementation | Notes |
|---|-------|-----------|-------------|---------------|-------|
| 1 | Obsidian联动 | — | ✅ 已实现 | `obsidian` skill | instruction-level |
| 2 | LiveDoc | ⭐7.6K | ❌ 未实现 | 源码无相关代码 | 唯一真正缺口 |
| 3 | YouTube字幕 | ⭐6.4K | ✅ 已实现 | `youtube-content` skill | `fetch_transcript.py` |
| 4 | SuperAgent | ⭐12.8K | ✅ 已实现 | `cron/` + `delegate_task` | 3 种实现方式 |
| 5 | LLM Wiki | 内置 | ✅ 已实现 | `llm-wiki` v2.1.0 | 506 行 SKILL.md |
```

### Trigger Conditions
- User sends a link and says "了解一下" / "你看下这个"
- User sends a link about AI tools/workflows
- User asks "我们有没有类似的功能"
- Any tutorial/post that lists features/skills comparable to our setup

### Pitfalls
- ❌ **Don't just save the link.** Extract the content first, then decide what to do
- ❌ **Don't create a new Obsidian file if it's just a few lines** — update an existing doc instead
- ❌ **Don't claim equivalence without verifying in source code first.** The social media post may be wrong about what exists or may attribute features to the wrong system.
- ❌ **Don't confuse Hermes with OpenClaw.** If the post mentions both or uses similar branding, verify which system each feature belongs to by searching source code.
- ❌ **Don't write "缺X" for a feature that already exists in Hermes.** Verify before claiming gaps.
- ❌ **Don't claim equivalence where there's a real gap** — honesty about limitations is better
- ❌ **Don't leave the Obsidian index stale** — always add the new file link to index.md
- ❌ **Don't go manual before checking for CLI tools first.** When a tool fails (e.g. `feishu_doc_read` errored), don't immediately resort to raw API calls. Ask: "Is there a CLI tool that can do this?" — run `which <tool-name>`, check `~/.npm-global/bin/`, `brew list`, or `hermes doctor`. The full tool inventory is in Obsidian `系统环境配置.md`. (Classic mistake: lark-cli was already installed but I did manual Feishu API curl calls.)
- ❌ **Don't use browser when a CLI is faster.** For GitHub operations, use `gh search` not browser_navigate. For JSON parsing, use `jq` not Python `json.loads()`. For simple OCR, use `tesseract` not delegation to a subagent.

### Example
See `个人知识库/3-知识/wiki/AI与Agent/Hermes+Obsidian高阶用法参考.md` (created 2026-05-06, corrected 2026-05-06): a Xiaohongshu post about 5 Hermes+Obsidian advanced skills, verified against Hermes source code with accurate implementation status.

For the detailed verification results (code locations, skill paths, script files), see `references/2026-05-06-hermes-feature-verification.md` under this skill.

### Advanced: Deep Analysis via Codex Delegation

For complex External Content Ingestion cases (e.g., a technical article that maps to Hermes architecture):

**Use `delegate_task(agent_id='codex', ...)`** to have codex:
1. Read the extracted content
2. Deep-dive into the Hermes codebase (`search_files` with multiple keywords, `read_file` of core files)
3. Compare current implementation vs article's approach
4. Produce a prioritized implementation plan

**When to use this:**
- The content describes a methodology or architecture pattern, not just a tool feature
- The user wants actionable recommendations, not just documentation
- The content maps to internal Hermes architecture (e.g., tool call handling, agent loop, schema design)

**Example**: 2026-05-06 — Obsidian note about @CommandCodeAI's tool-input repair layer → codex explored `model_tools.py`, `run_agent.py`, `tools/registry.py` → produced `Tool_Input_Repair_Layer_Analysis.md` (7-phase plan). See `references/2026-05-06-tool-input-repair-layer-analysis.md`.

### Example (Xiaohongshu post)

- **[[obsidian-knowledge-base]]** — Obsidian vault file operation rules, CLAUDE.md reading requirement, and the Obsidian-side output steps of the External Content Ingestion workflow.
