# Hermes 2.8 升级方案：从多 Agent 系统到秘书型主 Agent

以意图理解、任务分发、质量门禁、项目记忆为核心，提升 Hermes 对复杂工作任务的真实交付能力。

---

## 核心目标

当前 Hermes 的核心问题不是"功能不够多"，而是主 Agent 缺少秘书型能力：

1. **不懂你要什么** — 没有结构化的意图补全机制
2. **不会分工** — 大部分任务主 Agent 自己做了，但你对结果不满意
3. **不透明** — 不知道为什么这么判断、为什么不分发、哪一步偏了
4. **不验收** — 没有交付前的质量审查，你的隐性标准没固化进系统

这个方案不是给 Hermes 加功能，是给它换一套工作方式：
**从"回答型 Agent"升级为"秘书型主 Agent"**。

---

## 施工约定（Claude Code 执行本方案时必须遵守）

1. 每个 Sprint 单独分支：`upgrade/hermes-2.8-sprint-N`
2. 每个 Sprint 开始前先跑现有测试，记录基线
3. 每个 Sprint 只改该 Sprint 涉及的文件，不做大范围重构
4. 禁止删除用户文件，禁止修改 `.env`、密钥、凭证
5. 禁止执行 `rm -rf`、`curl | bash`、`sudo`、`chmod 777`
6. 改动前先输出变更计划，改动后输出 diff summary
7. 每个 Sprint 完成后单独 commit，输出：changed_files、commands_run、tests_run、test_results、known_limitations、next_sprint_risks
8. **Event Log 是所有状态变化的唯一事实来源。** Task Card 只保存当前状态快照，不做独立的状态历史。

---

## 总体策略

6 个 Sprint，每个 Sprint 一件事，边界清晰。按体验杠杆从高到低排列。

```
Sprint 1: Task Card + Minimal Event Log        ← 让 Hermes 搞清楚"这次任务到底是什么"
Sprint 2: Review Gate + 静态审查模板            ← 让 Hermes 在交付前替你把关
Sprint 3: Lightweight Memory                    ← 沉淀偏好、项目规则、负反馈
Sprint 4: Agent Router / Pipeline               ← 让任务流向正确的 Agent
Sprint 5: Decision Event Log 扩展               ← 让系统可复盘、可调试
Sprint 6: Skill Permission MVP                  ← 安全扩展第三方 Skill
```

---

## Sprint 1：Task Card + Minimal Event Log

### 目标

每个用户请求进来，主 Agent 第一件事不是回答，是**把任务结构化**。Task Card 是后续所有 Sprint 的数据基础。Event Log 只记录 Task 生命周期事件，不记录智能决策链。

### Task Card 结构

```json
{
  "schema_version": "2.8.0",
  "task_id": "uuid",
  "created_at": "iso_timestamp",
  "updated_at": "iso_timestamp",
  "version": 1,
  "raw_user_request": "用户的原始输入",
  "compiled_intent": {
    "real_task": "用户真正想做的事（用一句完整的话描述）",
    "task_category": "architecture_review | code_analysis | brand_strategy | visual_design | research | document | prompt_design | other",
    "assumptions": ["主 Agent 基于上下文做的假设"],
    "must_keep": ["绝对不能偏离的约束"],
    "must_avoid": ["绝对不能做的事"],
    "success_criteria": ["什么叫做好了"]
  },
  "execution_plan": {
    "mode": "self_execute | single_agent | pipeline | review_only",
    "agents": [],
    "delegation_reason": "为什么这么分 / 为什么不拆分"
  },
  "acceptance_criteria": {
    "auto_checkable": ["可自动化验证的条件"],
    "human_judgment": ["需要人工判断的条件"],
    "user_preference_check": ["是否符合 Gu 的偏好"]
  },
  "status": "pending",
  "result_summary": null,
  "review_result": null
}
```

**设计约束**：
- Task Card 只保存当前状态快照。状态历史从 Event Log 读取，Task Card 不做独立的 status_history。
- `updated_at` 每次写入时刷新。
- `version` 每次写入时递增，防止并发覆盖。

### 意图补全规则（不在此 Sprint 实现，仅作为 Task Card 的填写指引）

主 Agent 在生成 `compiled_intent` 时必须遵循：

1. 用户表达不完整时，根据上下文和历史偏好主动补全，而非追问。除非是方向性歧义（"你要 A 还是 B？"），否则不做确认式追问。
2. 识别隐含约束：用户说"帮我写个方案"，隐含约束包括：不要空泛建议、要有核心判断、要有可执行改法、要符合 Gu 的表达偏好（直接、不废话）。
3. 区分表面任务和真实任务：用户说"看看这个方案有什么问题"，真实任务通常是"帮我改进这个方案"，不只是"找出问题列表"。

### Minimal Event Log

**Sprint 1 只做这些事件类型**（只保证状态流转可追溯）：

```
task_created         — Task Card 创建
task_updated         — Task Card 字段更新
status_changed       — pending → running → reviewing → completed | failed | blocked | partial
execution_started    — 开始执行
execution_completed  — 执行完成
execution_failed     — 执行失败
artifact_created     — 产出物（文件、commit 等）
```

**不做**：
- intent_inferred（→ Sprint 5）
- dispatch_decision（→ Sprint 4/5）
- quality_check（→ Sprint 2）
- user_feedback（→ Sprint 5）
- memory_candidate（→ Sprint 3/5）
- tool_call / tool_result（如 Hermes 已有工具日志则不重复）

### Event Schema

```python
@dataclass
class SessionEvent:
    event_id: str          # UUID
    session_id: str
    task_id: str           # 关联 Task Card
    type: str              # task_created | status_changed | ...
    timestamp: float
    source: str            # model | user | system
    payload: dict
```

### Event Payload 最小规范

每个事件类型有固定 payload 结构，防止 Sprint 5 复盘时无法复用：

```json
// task_created
{
  "task_category": "architecture_review",
  "raw_user_request_preview": "评估 Hermes 强化方案...",
  "execution_mode": "self_execute"
}

// status_changed
{
  "from_status": "pending",
  "to_status": "running",
  "reason": "Task execution started",
  "actor": "main_agent"
}

// execution_completed
{
  "result_type": "text | file | refactored_code",
  "artifact_count": 1,
  "turn_count": 5
}

// execution_failed
{
  "error_type": "timeout | tool_error | model_error | user_abort",
  "error_message": "...",
  "retryable": true
}

// artifact_created
{
  "artifact_type": "file | task_card | memory_entry",
  "artifact_path": "~/.hermes/task_cards/xxx.json"
}
```

未列出的 payload 字段允许自由扩展，但 listed fields 必须存在。

### 存储

SQLite，独立 `events.db`，不跟 `state.db` 混用。Sprint 1 使用 append-only 表，不做复杂索引，不做事件压缩，不做跨 session 聚合。

```sql
CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  type TEXT NOT NULL,
  timestamp REAL NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX idx_events_task_id ON events(task_id);
CREATE INDEX idx_events_session_id ON events(session_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

### Task Card 存储规范

- 路径：`~/.hermes/task_cards/{task_id}.json`
- 创建时写入完整 JSON
- 更新时读旧文件 → patch 字段 → 写回（非 overwrite）
- 每次更新 `updated_at`，每次递增 `version`
- 写入失败必须抛出异常并写入 `execution_failed` 事件

### 改动文件

| 文件 | 改动 |
|------|------|
| **新增** `agent/task_card.py` | TaskCard dataclass + JSON 序列化 |
| **新增** `agent/session_event_log.py` | EventLog + SQLite 存储 + append-only 写入 |
| `run_agent.py` | 用户输入后构建 TaskCard，写入 task_created 事件 |

### 验证

- 任意请求 → `~/.hermes/task_cards/{task_id}.json` 存在且格式正确
- `~/.hermes/events.db` 中有 `task_created` 事件
- 任务状态变化 → 有 `status_changed` 事件，payload 含 from_status / to_status / reason / actor

---

## Sprint 2：Review Gate + 静态审查模板

### 目标

每个任务交付前经过 Review Gate。先做静态审查模板，不依赖 Memory 系统。

### Review Gate 结构

```json
{
  "task_id": "",
  "checked_at": "",
  "rule_checks": {
    "has_task_id": { "pass": true },
    "has_compiled_intent": { "pass": true },
    "has_result_summary": { "pass": true },
    "has_review_result": { "pass": true },
    "success_criteria_addressed": { "pass": true, "details": "" }
  },
  "llm_checks": {
    "matches_real_intent": { "pass": true, "evidence": "" },
    "matches_user_preferences": { "pass": true, "evidence": "" },
    "matches_project_context": { "pass": true, "evidence": "" },
    "not_only_surface_task": { "pass": true, "evidence": "" }
  },
  "quality_score": 0,
  "risks": [],
  "needs_revision": false,
  "revision_instruction": ""
}
```

Review Gate 分两层：
- **Rule-based**：结构性检查，确定性判断，不需要 LLM
- **LLM-based**：语义质量检查，由主 Agent 调用辅助模型判断

Review Gate 结果写入 Task Card 的 `review_result` 字段：

```json
{
  "review_result": {
    "checked_at": "iso_timestamp",
    "quality_score": 85,
    "needs_revision": false,
    "revision_count": 0,
    "review_exhausted": false
  }
}
```

不塞进 `result_summary`，不另建文件。Sprint 5 复盘时直接从 Task Card 读取。

### 静态审查模板

按任务类型硬编码在 `review_templates.py`，不读 Memory，不读数据库：

**品牌方案类**（蒙牛项目）：
- 是否有母品牌心智（"要强=蒙牛"）
- 是否把品牌理念转译到具体场景
- 是否避免把品牌方案写成销售方案
- 是否有品牌归因机制
- 是否能回答"为什么必须由蒙牛做"
- 是否能回答"竞品为什么复制不了"

**架构设计类**（Hermes 项目）：
- 是否服务"主 Agent 秘书化"目标
- 是否区分基础设施升级和体验升级
- 是否有明确优先级
- 是否避免过度工程化
- 是否能被分步实现

**通用**（所有任务）：
- 是否有核心判断，而非空泛建议
- 是否有可执行改法，而非罗列选项
- 是否符合 Gu 的表达偏好（直接、不废话）
- 是否能直接进入下一步工作

模板结构：

```python
# review_templates.py
REVIEW_TEMPLATES = {
    "brand_strategy": {
        "name": "品牌方案审查",
        "checks": [
            {
                "id": "brand_core",
                "question": "是否有母品牌心智？是否把"要强=蒙牛"转译到了具体场景？",
                "type": "llm",
            },
            # ...
        ],
    },
    "architecture_review": {
        "name": "架构设计审查",
        "checks": [
            {
                "id": "serves_secretary_goal",
                "question": "是否服务'主 Agent 秘书化'目标？",
                "type": "llm",
            },
            # ...
        ],
    },
    "universal": {
        "name": "通用质量审查",
        "checks": [
            {
                "id": "has_core_judgment",
                "question": "是否有核心判断，而非空泛建议？",
                "type": "llm",
            },
            {
                "id": "has_result_summary",
                "question": "是否有 result_summary？",
                "type": "rule",
            },
            # ...
        ],
    },
}
```

### Review Gate 阻断规则

**阻断交付**（以下任一成立，不交付给用户）：
1. 没有 Task Card
2. 没有 `compiled_intent`
3. 没有 `result_summary`
4. 没有回应 `success_criteria` 中任一条
5. `rule_checks` 任一未通过
6. `quality_score < 70` 且 `revision_count < 1`
7. `needs_revision = true` 且 `revision_count < 1`

**允许降级交付**（标注 risk 即可交付）：
1. LLM 检查不确定（confidence 低）
2. 信息不足但已在 `result_summary` 中明确标注 limitation
3. 子 Agent 失败但主 Agent 已接管并在 result_summary 中说明了风险和替代方案

**Revision Loop 硬上限**：最多返工 1 次。1 次 revision 后仍不通过 → 降级交付并标注 `review_exhausted: true`。

### 改动文件

| 文件 | 改动 |
|------|------|
| **新增** `agent/review_gate.py` | ReviewGate 类 + rule-based 检查 + 阻断规则 |
| **新增** `agent/review_templates.py` | 静态审查模板（硬编码） |
| `run_agent.py` | 任务交付前调用 ReviewGate.check() |

### 验证

- 完成任务 → Task Card 附带 review_gate 结果
- Rule-based 检查不通过 → 阻断交付
- LLM-based 检查不通过 → 标注 needs_revision + revision_instruction
- 触发 revision → 确认 revision_count <= 1，超限降级交付

---

## Sprint 3：Lightweight Memory

### 目标

沉淀用户偏好、项目规则、负反馈。先从 4 类记忆 + 3 级 scope 开始，不堆字段。

### 记忆类型

```
user_preference    # Gu 的长期偏好
project_context    # 当前项目规则
feedback_rule      # 对某类输出的否定反馈
working_principle  # 工作原则
```

### Scope

```
global     # 跨项目始终生效
project    # 当前 git repo
session    # 仅当前会话
```

### 记忆元数据

每条记忆带 3 个字段：

- `confidence`: high | medium | low
- `source`: user | inferred | feedback
- `last_verified_at`: iso_timestamp

### 存储格式

与旧格式兼容。每条记忆用 YAML frontmatter + 正文：

```yaml
---
type: feedback_rule
scope: project
confidence: high
source: feedback
last_verified_at: "2026-05-02T10:00:00Z"
---
用户不喜欢信息太多、太噪、模块堆砌的 PPT 页面，偏好高级、克制、清爽的策略页表达。
```

旧条目（无 frontmatter）自动视为 `type=memory, scope=global, confidence=medium`。

### 写入策略（比存储格式更重要）

1. 用户明确说"记住" → 直接写入
2. 用户连续 2 次表达同类偏好 → 建议写入，等用户确认
3. 用户强烈否定某类输出：
   - **默认写入 session scope 的 feedback_rule**
   - 同类反馈重复出现 2 次 → 建议升级为 project 或 global
   - 用户明确说"以后都不要这样" → 直接写入 project/global
4. 项目长期原则 → 写入 project/global 的 project_context
5. 临时任务信息 → 不写入

### 检索策略

system prompt 注入时：当前 project 的记忆 + 所有 global 记忆 + 当前 session 记忆全部注入。

**注入上限（防 prompt 膨胀）**：
- global 记忆最多 20 条
- project 记忆最多 30 条
- session 记忆最多 20 条
- 超出时按 `last_verified_at` 倒序取最近 N 条

不做复杂检索排序，不做语义检索。

### 改动文件

| 文件 | 改动 |
|------|------|
| `tools/memory_tool.py` | 新增 `type`/`scope`/`confidence`/`source`/`last_verified_at` 参数；YAML frontmatter 读写；向后兼容旧格式 |
| `agent/review_gate.py` | `matches_user_preferences` 和 `matches_project_context` 检查接入 Memory |

### 验证

- 写入 `type: feedback_rule, scope: session` 记忆 → 会话结束后不再注入
- 写入 `type: user_preference, scope: global` 记忆 → 跨会话注入
- 旧格式记忆 → 正常可读，自动获得默认元数据
- 写入含 API key 的内容 → 扫描报警但不阻断

---

## Sprint 4：Agent Router / Pipeline

### 目标

从"主 Agent 自己干或扔给一个人"升级为"按任务类型路由到正确的 Agent，支持流水线，支持 override，支持失败回退"。

### Agent 分工

```text
Hermes 主 Agent：分析意图、拆解任务、整合结果、质量把关
Kimi (k2-thinking)：搜索、调研、读长文、整理信息
Claude Code / Claude Opus：写代码、改文件、跑脚本（仅执行明确修改）
图像/PPT Agent：视觉创意、PPT 生成
```

### 默认路由规则（按 task_category）

```
architecture_review  → self_execute
code_analysis        → pipeline: Kimi(读代码/查文档) → Hermes(分析判断)
brand_strategy       → self_execute
visual_design        → single_agent: 图像/PPT Agent
research             → single_agent: Kimi
document             → pipeline: Kimi(收集素材) → Hermes(撰写整合)
prompt_design        → self_execute
```

### Routing Override

路由规则不是死板的 if-else。主 Agent 可以覆盖默认路由：

```json
{
  "execution_plan": {
    "mode": "self_execute | single_agent | pipeline | review_only",
    "agents": [],
    "delegation_reason": "",
    "routing_basis": [
      "task_category_default",   // 用了默认路由还是覆盖了
      "required_capability",     // 实际需要的能力决定的
      "risk_level"               // 风险级别是否改变了路由
    ]
  }
}
```

覆盖条件：
- `required_capability` 发现默认路由的 Agent 能力不够时 → 覆盖
- `risk_level` 高时 → 强制走 pipeline + Review Gate
- 用户显式指定"用 XX 做" → 覆盖默认

### Pipeline 模式

```
Kimi 查资料 / 读代码
      ↓
Hermes 分析判断 / 撰写
      ↓
Claude Code 执行明确修改（仅当需要改文件）
      ↓
Hermes 验收（Review Gate）
```

### Fallback 机制

```
Kimi 无结果 → Hermes 自行完成并标记信息不足
Claude Code 执行失败 → 回 Hermes 生成修复建议
子 Agent 输出质量低 → Review Gate 打回一次；二次失败则主 Agent 接管
Pipeline 任一步失败 → Task Card status = partial 或 blocked，不简单标 failed
```

### 关键约束

- **Claude Code 是执行器，不是思考器**。拿到的 prompt 是"改 X 文件的 Y 函数，改成 Z"，不是"优化一下性能"。
- **子 Agent 结果不能直接交付用户**。必须由主 Agent 整合、复核、必要时打回。
- **主 Agent 对最终答案负责**。子 Agent 产出差，主 Agent 应该打回或重写，而非直接拼贴。

### 改动文件

| 文件 | 改动 |
|------|------|
| `agent/task_card.py` | `execution_plan` 扩展 routing_basis + fallback 字段 |
| `tools/delegate_tool.py` | 不改接口，路由逻辑在主 Agent 侧 |
| `agent/review_gate.py` | 新增 `agent_result_accepted/rejected` 检查 |

### 验证

- 调研类任务 → 确认先调 Kimi 再整合
- 代码任务 → 确认 Claude Code 收到的是明确指令而非模糊需求
- Pipeline 失败一步 → 确认 status 变为 partial/blocked 而非 failed
- 显式指定 Agent → 确认 routing_basis 包含 user_override

---

## Sprint 5：Decision Event Log 扩展

### 目标

从"Task 生命周期日志"扩展为"智能决策日志"。记录主 Agent 的判断链路，让每次任务可复盘。

### 新增事件类型

```
intent_inferred       — 主 Agent 如何理解用户意图
task_classified       — 任务被分到哪个类别
dispatch_decision     — 为什么 self_execute / single_agent / pipeline
agent_called          — 调用了哪个子 Agent，传了什么 prompt
agent_result          — 子 Agent 返回了什么
agent_result_accepted — 主 Agent 采纳子 Agent 结果
agent_result_revised  — 主 Agent 打回/修改子 Agent 结果
quality_check         — Review Gate 结果
user_feedback         — 用户对最终答案的反应（如有）
memory_candidate      — 是否建议写入记忆
```

### 任务复盘摘要

每个任务完成后自动从 Event Log 生成：

```json
{
  "task_id": "",
  "user_request": "评估 Hermes 强化方案",
  "inferred_intent": "判断方案是否存在系统性硬伤，并给出升级建议",
  "task_type": "architecture_review",
  "dispatch_decision": "self_execute",
  "dispatch_reason": "架构评审类任务的核心价值在主 Agent 的判断力和对 Hermes 全局的把握，子 Agent 无法提供这种判断",
  "quality_gate_passed": true,
  "result_status": "completed",
  "key_decisions": [],
  "events_chain": [
    "task_created → intent_inferred → task_classified → dispatch_decision → execution_started → execution_completed → quality_check → status_changed(completed)"
  ]
}
```

### 改动文件

| 文件 | 改动 |
|------|------|
| `agent/session_event_log.py` | 扩展事件类型 + 复盘摘要生成 |
| `agent/task_card.py` | 任务结束时联动写入复盘摘要 event |
| `tools/session_search_tool.py` | 新增 `search_by_task_id`、`search_replay_chain` |

### 验证

- 任务完成后 → `events.db` 中有完整决策链
- `session_search search_by_task_id` → 可检索到所有关联事件
- `session_search search_replay_chain` → 按时间序列返回完整决策链

---

## Sprint 6：Skill Permission MVP

### 目标

给 Skill 加最小安全边界。不追求复杂 hook 权限体系，不做运行时拦截。

### Skill Manifest

```yaml
---
name: apple
version: "1.0"
description: macOS automation skills
triggers: [苹果, mac, iMessage]
platform: darwin
permissions:
  tools: [bash, file_read, file_write]
  network: false
trust: installed
---
```

### Trust Level

```python
BUNDLED    # 随 Hermes 发布，完全信任
INSTALLED  # 用户主动安装，默认信任
UNTRUSTED  # 第三方/社区 skill，受限运行
```

UNTRUSTED skill 限制：
- 网络请求需用户确认
- 文件写入限于 workspace
- 环境变量只传白名单
- 不能注册 transform hook

### 不做

- 不做 hook 运行时拦截
- 不做 skill 自动降权/自动优化
- 不做 hook permission 分级（字段预留，不实现）

### 改动文件

| 文件 | 改动 |
|------|------|
| `agent/skill_utils.py` | manifest 解析 + trust level 校验 |
| `agent/skill_commands.py` | 加载时读 manifest，注入 trust 信息 |
| `tools/skills_tool.py` | 安装/查看时展示权限信息 |

### 验证

- 安装无 manifest 的 skill → 加载警告但不阻断
- 安装 UNTRUSTED skill → manifest 被识别，trust=UNTRUSTED
- 查看 UNTRUSTED skill → 展示权限风险（tools/network/env）
- 调用 UNTRUSTED skill 的高风险能力 → 触发用户确认或警告
- 安装 INSTALLED skill → 正常加载，信任标记正确
- **不做**：不承诺完整运行时沙箱隔离、不承诺文件写入自动拦截、不承诺网络请求自动阻断

---

## Sprint 依赖关系

```
Sprint 1 (Task Card + Minimal Event Log)
   │
   ├──▶ Sprint 2 (Review Gate + 静态模板)   ← 读 Task Card 结构
   │         │
   │         ├──▶ Sprint 3 (Lightweight Memory)  ← 接入 Review Gate
   │         │         │
   │         │         ├──▶ Sprint 4 (Agent Pipeline)  ← 读 Task Card + Memory
   │         │         │         │
   │         │         │         └──▶ Sprint 5 (Decision Log)  ← 扩展 Event Log
   │         │         │
   │         │         └──▶ Sprint 6 (Skill Permission)  ← 独立，Sprint 3 后即可并行
```

Sprint 6 在 Sprint 3 之后可并行启动（只依赖 manifest 格式稳定，不依赖 Sprint 4/5）。

---

## 改动文件总览

| Sprint | 文件 | 改动类型 |
|--------|------|---------|
| 1 | **新增** `agent/task_card.py` | TaskCard dataclass |
| 1 | **新增** `agent/session_event_log.py` | EventLog + SQLite |
| 1 | `run_agent.py` | TaskCard 创建 + 事件写入 |
| 2 | **新增** `agent/review_gate.py` | ReviewGate |
| 2 | **新增** `agent/review_templates.py` | 硬编码审查模板 |
| 2 | `run_agent.py` | 任务交付前调用 ReviewGate |
| 3 | `tools/memory_tool.py` | 重构：type/scope/元数据 + frontmatter |
| 3 | `agent/review_gate.py` | 接入 Memory |
| 4 | `agent/task_card.py` | routing_basis + fallback 字段扩展 |
| 4 | `agent/review_gate.py` | agent_result_accepted/rejected |
| 5 | `agent/session_event_log.py` | 扩展事件类型 + 复盘摘要 |
| 5 | `agent/task_card.py` | 联动复盘摘要 |
| 5 | `tools/session_search_tool.py` | search_by_task_id |
| 6 | `agent/skill_utils.py` | manifest 解析 |
| 6 | `agent/skill_commands.py` | manifest 加载 |
| 6 | `tools/skills_tool.py` | 权限展示 |

---

## 验证总览

| Sprint | 验证方法 |
|--------|---------|
| 1 | Task Card JSON 落盘 + events.db 有 task_created |
| 2 | Review Gate 结果附加到 Task Card + 硬编码模板可读 |
| 3 | 记忆写入 scope 过滤有效 + 旧格式兼容 + 写入策略生效 |
| 4 | 调研走 Kimi pipeline + 代码任务 Claude Code 收到明确指令 + 失败有 fallback |
| 5 | events.db 含完整决策链 + session_search 可回溯 |
| 6 | UNTRUSTED skill 权限可识别、可展示；高风险调用触发确认或警告；无 manifest 不阻断 |

---

## Claude Code 执行总 Prompt

> 将此 prompt 与方案一起交给 Claude Code。每次只执行一个 Sprint。

```text
你是 Claude Code。你将根据《Hermes 2.8 升级方案》对 Hermes Agent (~/.hermes/hermes-agent/) 执行升级。

执行规则：
1. 不要一次性执行全部方案。每次只执行用户指定的一个 Sprint。
2. 开始前先阅读本方案全文、项目结构和 Sprint 涉及的关键文件。
3. 输出该 Sprint 的执行计划，等待用户确认后再改代码。
4. 严格遵守方案开头的"施工约定"章节。
5. 不做当前 Sprint 范围外的任何内容。如果发现可优化的相邻代码，记入 known_limitations 但不顺手改。
6. 改动前后输出 diff summary。
7. 每次完成后输出：
   - changed_files：改了哪些文件
   - commands_run：跑了哪些命令
   - tests_run：跑了哪些测试
   - test_results：测试结果
   - known_limitations：已知限制和未覆盖的边界
   - next_sprint_risks：对下一个 Sprint 的风险提示
8. 如果发现项目结构与方案假设不一致，先停止并报告差异，不要自行大改方案。
9. Sprint 间的 Event Log / Task Card 字段变更必须是向前兼容的（新增字段有默认值，不删已有字段）。
```

---

## 不做事项

- 不做 frontend UI（Task Card 可视化等）
- 不做 skill 自动降权、自动优化
- 不做 hook 运行时拦截
- 不做 fork/resume 机制
- 不做多模型路由（Sprint 4 只做 Agent 路由）
- 不做复杂记忆检索排序
- 不做事件压缩和跨 session 聚合
- Sprint 1 不做 Review Gate、Memory、Router、决策日志
