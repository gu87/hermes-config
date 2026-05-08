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
---

# Hermes 知识架构

> 最后更新: 2026-05-08 (v4 — 对齐 memory + Obsidian 外脑 + skill 分层)
> 核心原则：Memory 是 always-on 稳定注入层，Skill 是流程库，Obsidian 是外脑和全量持久存储，session_search 是短期会话线索

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

### 阶段性控制论梳理 Skill

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
