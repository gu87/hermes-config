---
name: hermes-subagent-delegation
description: "子Agent（Named Agent / delegation）配置与排障 — agent-registry.json、config.yaml delegation段、toolsets隔离、模型继承"
tags: [hermes, subagent, delegation, troubleshooting]
category: hermes
agents: [hermes, nesta]
---

# Hermes 子Agent Delegation 配置与排障

## 触发条件

当出现以下情况时加载此技能：
- 子Agent（如 `agent_id='kimi'` 等命名Agent）返回空结果、0 tokens、无工具调用
- 子Agent行为异常（使用了错误的模型/Provider）
- 新增或修改子Agent配置后验证
- 配置修改后网关重启

## 排查流程

### Step 1: 检查子Agent注册配置

文件：`~/.hermes/config/agent-registry.json`

关注字段：
- `toolsets` — 子Agent可用工具集列表。注意 `file` + `web` 可能不足以完成搜索类任务，需加 `terminal`、`browser` 等
- `blocked_tools` — 显式禁用的工具。`terminal` 默认有时在 blocked_tools 中
- `isolation` — `"readonly"` 会剥离写工具集，建议 `"shared"`
- `permission_mode` — `"read_only"` 限制工具权限，建议 `"ask"`
- `skills` — ⚠️ **当前缺失**：subagent_profile 还没有 skills 字段，所有 Named Agent 加载不到任何技能（纯白板状态）。详见 `hermes-knowledge-architecture` skill 中的「Agent-Scoped Skills」设计文档

```bash
cat ~/.hermes/config/agent-registry.json | jq '.agents.kimi'
```

### Step 2: 检查全局 Delegation 配置

**这是最容易被忽略的坑。**

文件：`~/.hermes/config.yaml` → `delegation:` 段

```yaml
delegation:
  # ⚠️ 如果 model/provider/base_url/api_key 被硬编码（非注释状态），
  #    它们会覆盖所有子Agent的模型设置，包括命名Agent（agent_id='kimi' 等）
  model: claude-sonnet-4-6       # ← 硬编码会导致所有子Agent用这个模型
  provider: anthropic             # ← 对应 Provider 不可用则子Agent空转
  # ...
```

**关键规则**：子Agent的模型/Provider继承优先级为：
1. `agent-registry.json` 中 `profile.subagent_profile.model`（如果有）
2. `config.yaml` 中 `delegation.model` / `delegation.provider`（⚠️ 如果有硬编码，会覆盖所有子Agent）
3. 父Agent的当前模型（默认行为，当上述两项都为空时）

**修复方法**：将硬编码行注释掉，让子Agent继承父级模型
```yaml
delegation:
  # model: claude-sonnet-4-6     ← 前面加 #
  # provider: anthropic           ← 前面加 #
```

### Step 3: 网关重启

配置修改后必须重启网关：

```bash
# 推荐方式（绕过 launchd 生命周期管理）
hermes gateway run --replace
```

> 当遇到 launchd drain 超时或重启后进程反复挂掉时，优先用 `hermes gateway run --replace` 绕过生命周期管理。`hermes gateway restart` 不是永久禁用项；如果当前版本已修复或服务由 launchd 正常托管，可按实时状态选择。
> 验证：`ps aux | grep hermes | grep -v grep`

### Step 4: 验证子Agent

用一个简单任务测试：

```python
delegate_task(agent_id='kimi', goal='搜索今天的AI新闻', context='用中文回复')
```

## 分析子Agent行为：tool_trace

子Agent返回结果中的 `tool_trace` 字段是排查利器：

```json
{
  "tool_trace": [
    {"tool": "web_search", "args_bytes": 48, "result_bytes": 702, "status": "ok"},
    {"tool": "terminal", "args_bytes": 193, "result_bytes": 76, "status": "error"}  // ← 失败调用
  ],
  "usage": {"input_tokens": 0, "output_tokens": 0},  // ← 空调用说明模型配置有问题
  "api_calls": 23
}
```

判读：
- `usage.input_tokens = 0` + `usage.output_tokens = 0` → 模型/Provider配置错误，子Agent根本没法调用API
- 大量 `terminal` 或 `browser` 失败 → 工具权限或网络环境问题
- 只有 `web_search` 成功但数据不够 → 需要扩充 toolsets

## 子Agent Soul/Persona 注入机制

当通过 `delegate_task(agent_id='...')` 调用 Named Agent 时，子 Agent 的 system prompt 由 `_build_child_system_prompt()` 函数生成。从 v2026-05-13 起，该函数支持通过 `soul` 参数注入角色人格。

### Soul 存储位置

在 `agent-registry.json` 中，每个 agent 可以有一个 `soul` 字段：

```json
"nesta": {
  "id": "nesta",
  "display_name": "内斯塔",
  "soul": "你是 B 技术专员内斯塔。你的职责是把 Gu 的模糊技术需求翻译成 Claude Code 能直接执行的任务包……",
  ...
}
```

### 注入机制

`delegate_tool.py` 的 `_build_child_agent()` 函数在构建子 agent 时：

```python
# 从 agent_config 提取 soul
soul = (agent_config.get('soul', '') or '') if agent_config else ''

# 传给 _build_child_system_prompt
child_prompt = _build_child_system_prompt(
    goal,
    context,
    soul=soul,    # ← 新增
    ...
)
```

`_build_child_system_prompt()` 将 soul 作为 `# YOUR ROLE\n{soul}\n` 块插入 system prompt 最前面，优先级高于通用 prompt。

### 生效条件

- ✅ `delegate_task(agent_id='nesta')` — soul 注入生效
- ❌ 飞书 Bot 直接 DM — soul 不生效（走的是该 Bot 自己的 system prompt）

### ⚠️ 关键架构约束：双路径人格差异

**每个 Named Agent 可能存在两条独立的人格通道：**

| 通道 | 触发方式 | 人格来源 | 状态 |
|------|---------|---------|------|
| **delegate_task 路径** | `delegate_task(agent_id='nesta')` | agent-registry.json `soul` 字段 → `_build_child_system_prompt()` 注入 | ✅ 需手动配置 |
| **飞书 Bot 直连路径** | 在飞书 DM 内斯塔 Bot | 该 Bot 自身的 Hermes profile / SOUL.md / 飞书后台 prompt | ❌ 默认是通用 AI 助手 |

**诊断方法：**
- 通过 `delegate_task` 调用 Agent → 检查回复是否使用了 soul 中定义的 persona
- 在飞书直接 DM 该 Bot → 检查回复是否是通用模板

**解决方案（按侵入性排序）：**

| 方案 | 做法 | 成本 |
|------|------|------|
| 走 delegate_task 委托 | 用户 DM 飞书 Bot 时，由马蒂尼拦截并 delegate_task 到目标 agent | 零部署，需用户习惯 |
| 创建独立 Hermes Profile | 为目标 Agent 创建 profile + SOUL.md + 独立飞书 Bot 凭证 + gateway 进程 | 中（约 15 分钟） |
| 配置飞书后台 prompt | 在飞书开放平台修改 Bot 的系统提示词 | 低（需开放平台权限） |

**真实案例（2026-05-13 内斯塔）**：
- `delegate_task(agent_id='nesta')` → 回复 "我是 B 技术专员内斯塔，负责..." ✅
- 飞书 DM 内斯塔 Bot → 回复 "AI助手，能处理文档、表格、日程、任务这些..." ❌

### 添加 `soul` 到现有 Agent

在添加新 Agent 时，确认 soul 字段已经包含在 agent-registry.json 中。soul 的内容应来自 **多Agent团队执行手册** 或 **§I 角色框架** 中的角色 Prompt。

**验证 soul 已生效的方法：**
```python
delegate_task(
    agent_id='nesta',
    goal='介绍你自己：你是谁，你的角色定位是什么？'
)
# 期望回复中包含 soul 中定义的角色身份
```

## Pitfalls

### 1. 模型硬编码是隐形杀手
`config.yaml` delegation 段如果有 `model:` 和 `provider:` 非注释，所有子Agent强制使用该模型，即使 `agent_id` 指定了不同的 profile。这是子Agent空转（0 tokens）的最常见原因。

### 2. 修改 agent-registry.json 后必须重启网关
配置加载在 Gateway 启动时完成，热改不生效。

### 3. GLOBAL_SUBAGENT_BLOCKED_TOOLSETS
Hermes 源码中有全局 blocked toolsets 常量，默认会移除 `terminal` 和 `read` 工具集。需在 `agent-registry.json` 的 `toolsets` 中显式加入来覆盖。

### 4. 隔离模式影响写能力
- `readonly` → 剥离所有写工具集（file write, terminal 等）
- `shared` → 继承父Agent工具集（推荐）

### 5. 子Agent模型推理超时（新失败模式）

**症状**：子 Agent 成功执行工具调用（如 read_file），但当需要模型推理生成大输出时，`exit_reason: "interrupted"`，报 `"waiting for model response (X s elapsed)"`。

**真实案例（2026-05-11，已验证修复）**：三次派发 deepseek-tui 和 Claude 写 91 条策略的 HTML 工具页均超时中断——子 Agent 读取 data.json 成功（tool_trace 显示 read_file 正常），但在模型推理生成 500+ 行 HTML 时卡住。

**修复全程记录**：
1. 首次诊断：检查 `child_timeout_seconds: 600` 和 `dialog_timeout_s: 300`，均够用 → 排除配置太短
2. 确认特征：「调用存在（tokens > 0）vs 模型配错的 0 tokens」→ 确认是 API 限流而非配错
3. Gu 在 `~/.hermes/config.yaml` delegation 段切换了 provider
4. 切换后 deepseek-tui 一次成功（88s，90k input tokens，41KB 文件）→ 诊断正确
5. Claude 后续也成功完成（336s，484k input tokens，23k output tokens）
6. 之后的 Claude 任务（生成 91 条 image-2 提示词）也成功（572s，790k input tokens）

**关键经验**：provider 切换是已验证的修复路径。如果连续超时 2 次 → 不要重复重试 → 建议用户切换 delegation provider → 再试。不要自己猜测还有其他配置要改。

**特征**：
- `usage.input_tokens/output_tokens > 0`（和模型配置错误的 0 tokens 不同）
- `tool_trace` 中前几个工具调用正常（如读取文件），之后卡住
- 多次重试同一子 Agent 依然在模型推理阶段超时

**根因链路**：
1. 父 Agent 和子 Agent 使用**同一个 deepseek-v4-flash API**
2. 子 Agent 完成工具调用后，需要模型做**大输出推理**（如生成 500+ 行 HTML）
3. deepseek API 对并发子会话的推理请求响应慢/限流
4. 系统在 `dialog_timeout_s: 300`（5分钟）之内等待模型响应超时

**触发条件**：
- 子 Agent 任务需要生成大量内容（如完整的 HTML 文件、长文档分析报告）
- 父 Agent 和子 Agent 使用同一个 Provider（特别是 deepseek）
- `busy_input_mode: interrupt` — 父会话在子 Agent 工作时不能插话

**排查方法**：
```bash
# 确认配置
grep -n "dialog_timeout_s\|busy_input_mode\|child_timeout_seconds" ~/.hermes/config.yaml
```

**诊断建议（优先判断正确方向）**：

先确认是「模型配置错」还是「模型推理超时」——不要盲目改配置：

```bash
# 1. 检查是否为 provider 限流（最常见原因）
#    看子 Agent 的 model 是否和父 Agent 相同 provider
grep "provider\|default\|model" ~/.hermes/config.yaml | head -5

# 2. 检查 dialog_timeout 是否够
grep "dialog_timeout_s" ~/.hermes/config.yaml

# 3. 如果子 Agent 没改过配置，但同一个 provider 连超 2 次，
#    基本可以判定是 API 限流，直接换 provider
```

**解决方案**（按可行优先级）：
1. **换 Provider 跑子 Agent** — 最有效。父 Agent 和子 Agent 同 provider（特别是 deepseek）时，API 对并发子会话的推理请求限流。在 `~/.hermes/config.yaml` 中：
   ```yaml
   delegation:
     model: claude-sonnet-4-6        # 指定不同模型
     provider: anthropic              # 指定不同 provider
   ```
   **验证**：改完后用 `delegate_task(agent_id='deepseek-tui', goal='说你好')` 快速测试，如果子 Agent 能正常响应说明 provider 切换生效。

2. **数据直接嵌入 context，不走 read_file** — 当子 Agent 要处理的数据已知且可嵌入时，直接放在 `context` 参数中传给子 Agent，避免子 Agent 先 read_file 再推理的额外步骤。不过这不是根治办法（根因是 API 限流），仅作为减少子 Agent tool call 轮次的手段。

3. **数据拆小再派** — 不一次性让子 Agent 生成完整大输出，而是分步：先生成骨架，再追加填充

4. **主会话直接写** — 不走子 Agent，由父 Agent 直接完成文件操作（当子 Agent 连续超时时，兜底方案）。父 Agent 可用 `write_file` + `patch` 工具做定向修改，不需要子 Agent。

### 6. 连续失败后的策略切换 — 必须立即通知用户

如果同一个子 Agent 连续超时 2 次，**必须立即通知用户**，不要静默重试。

**铁律**（来自 Gu 2026-05-11 明确要求）：
- 有问题要及时反馈，不能自己重试 3 次都不出声
- 第一次失败 → 换不同 agent_id 或方案再试
- 第二次失败 → **立刻告知用户**，说明现象、尝试了什么、下一步建议
- 不要猜用户想怎么修，先同步情况

**策略切换顺序**：
1. 先换 provider（用户操作）→ 再试
2. 换不同 agent_id（如 claude → deepseek-tui）— 只有换了 provider 后才有效
3. 换为主会话直接写

**和「0 tokens 空转」的区别**：
| 维度 | 模型配错（已记录） | 模型推理超时（本记录） |
|------|-------------------|---------------------|
| tokens | 0 / 0 | >0（有实际调用量） |
| tool_trace | 0 次调用 | 前面几次成功，后续卡住 |
| exit_reason | 空/空转 | `interrupted: waiting for model response` |
| 修复方向 | 改 config.yaml delegation 段 | 换 provider / 拆小任务 / 主会话写 |

## 成本优化委托模式（廉价模型预处理 → 贵模型执行）

当任务需要"先摸索再动手"时（如不熟悉代码库、模糊需求转精确指令），采用分阶段委托以节省昂贵的推理 token：

### 模式说明

```
用户：不懂技术的模糊需求（如"首页加载慢"）
  │
  ├─ Stage 1: 预处理 Agent（便宜模型）
  │   Agent: 内斯塔 (DeepSeek V4 Pro/Flash)
  │   工具: read_file, search_files, terminal
  │   成本: ~$0.02/百万输入 token
  │   产出: 精确任务包（目录结构、相关文件行、问题定位、待改代码段）
  │
  └─ Stage 2: 执行 Agent（贵模型）
      Agent: Claude Code (Claude Sonnet 4.6)
      工具: patch, write_file, terminal（只改代码不探索）
      成本: ~$3/百万输入 token
      产出: 改好的代码
```

### 触发条件

- 用户给的技术需求模糊、非精确（不懂编程的用户）
- 任务涉及不熟悉的代码库（需要先摸索项目结构）
- 探索步骤可能消耗大量 token（搜索、读文件、定位问题）

### 工作流

```text
马蒂尼 → delegate_task(agent_id='nesta', goal='预处理')
     ↓
     内斯塔（DS V4 Pro）：
     ① 搜项目结构 → 找到相关模块
     ② 读关键文件 → 定位问题
     ③ 搜性能日志/配置 → 排除无关因素
     ④ 输出精确任务包（文件路径 + 问题行 + 待改方案）
     ↓
     内斯塔 → terminal() 调用 Claude Code：
     "claude -p '改第N行的XXX函数，加YYY逻辑...'"
     或
     内斯塔 → delegate_task(agent_id='claude', context=精确任务包)
     ↓
     Claude Code 只改代码 → 返回结果
```

### 节省估算

| 阶段 | 模型 | 成本 | 典型 token 消耗 | 预估花费 |
|------|------|------|----------------|----------|
| 探索（内斯塔） | DeepSeek V4 Pro | $0.42/M输入 | 50K-200K | $0.02-$0.08 |
| 探索（内斯塔） | DeepSeek V4 Flash | $0.02/M输入 | 50K-200K | $0.001-$0.004 |
| 执行（Claude Code） | Claude Sonnet 4.6 | ~$3/M输入 | 10K-50K | $0.03-$0.15 |
| **合计** | | | | **$0.03-$0.23** |
| 直接给 Claude Code（无预处理） | Claude Sonnet 4.6 | ~$3/M输入 | 200K-800K | $0.60-$2.40 |

### 配置需求

- 内斯塔（或类似预处理 Agent）需要有 `file` + `terminal` 工具集
- Claude Code 需要在系统 PATH 中可用（需先 `which claude` 确认）
- 如果通过 delegate_task 调用 Claude Code，确保 agent-registry.json 中有对应的 claude entry

## 第三方 CLI 工具集成模式

当外部 CLI 工具（非 Hermes 子Agent）需要被集成到委托流程中时，通过 `terminal` 工具封装调用。

### 模式说明

```
Hermes → terminal("外部CLI --headless --input '任务描述' --format json")
       → 解析 stdout JSON → 返回结果
```

### 已验证的工具：Agent TARS（字节桌面 GUI Agent）

**工具信息：**
- CLI: `/Users/gu/.npm-global/bin/agent-tars`
- 版本: 0.3.0
- 用途: 桌面 GUI 自动化（点击、输入、截图、浏览器操作）
- 模型: 可通过 `--model.provider` `--model.baseURL` `--model.id` `--model.apiKey` 参数配置

**调用方式（headless + JSON）：**

```bash
agent-tars run --headless \
  --input "打开计算器并计算 1024*768" \
  --format json \
  --model.provider openai \
  --model.baseURL https://api.deepseek.com \
  --model.id deepseek-v4-pro \
  --model.apiKey <your-key>
```

**返回格式：**
```json
{
  "sessionId": "xxx",
  "result": {
    "id": "xxx",
    "type": "assistant_message",
    "timestamp": 1234567890123,
    "content": "执行结果描述...",
    "finishReason": "completed"
  }
}
```

**配置步骤：**
1. 创建 `agent.config.ts`（可选，不传命令行参数时使用）
2. 确认 API key 可访问（可通过 `--model.apiKey` 或环境变量传递）
3. 先手工测试一个简单任务验证连通性

**局限性：**
- 冷启动较慢（几秒），每次运行是新环境
- 需保证终端工具可用且 node 版本 ≥22.15.0
- 无状态，每次需要重设上下文

### 通用集成规则

| 规则 | 说明 |
|------|------|
| 优先 headless + JSON 输出 | 避免解析人类可读的 stdout |
| 先手工验证一次 | 确保 CLI 可用、API key 正确、模型可达 |
| 适当超时 | 桌面操作任务通常需要 30s-120s |
| 失败降级 | 如果 CLI 工具连续失败，降级为 OpenClaw 或其他备选 |

### 6. 新增 Agent 到注册表 ≠ 新增 delegate_task 的 agent_id

agent-registry.json 只是路由决策的配置文件，**不决定 `delegate_task` 函数的可用 agent_id 列表**。

### 7. 完整 Named Agent 添加流程（含角色审计）

新增一个 Named Agent 到 Hermes 系统需要走完整流程，不能只改 registry：

#### 步骤一：角色审计（先于技术配置）

在写任何配置之前，先对照 **多Agent团队执行手册** 或 **§I 角色框架** 确认：

- 这个角色在手册中的职责、标准输出、边界是什么？
- 该角色的 `type` 应该是什么？（如 technical_analyst / content_planner / code_reviewer / researcher）
- 能力（capabilities）必须精确匹配手册描述，不能多也不能少
- `best_for` / `not_for` 必须与手册的「做什么/不做什么」一致

#### 步骤二：agent-registry.json 完整配置模板

```json
{
  "id": "agent-id",
  "display_name": "中文名",
  "type": "角色类型",
  "capabilities": [
    // 精确匹配手册的角色能力，不多不少
  ],
  "best_for": [
    // 该角色的典型使用场景
  ],
  "not_for": [
    // 明确声明不做什么（必须与手册一致）
  ],
  "output_types": [
    // 该角色标准产出的格式
  ],
  "delegation": {
    "method": "delegate_task",
    "command": "delegate_task(agent_id=\"...\", goal=\"...\")"
  },
  "trust_notes": [
    // 使用须知、风险点
  ],
  "status": "active",
  "availability": "always",
  "subagent_profile": {
    "model": "deepseek-v4-pro",         // 或 default（继承父级）
    "toolsets": ["file", "terminal"],   // 根据角色需要
    "blocked_tools": ["delegate_task", "send_message", "memory"],
    "permission_mode": "ask",
    "isolation": "shared",              // 或 readonly（纯审核角色）
    "allow_background": false,
    "required_mcp_servers": []
  }
}
```

#### 步骤三：更新 delegate_tool.py enum

delegate_tool.py 中 agent_id 枚举**硬编码在两处**，必须同步更新：

```python
# 位置 1: 第 3851 行附近 — batch task 级别的 per-task agent_id
"enum": ["kimi", "claude", "codex", "openclaw", "hermes-internal", "deepseek-worker", "...", "..."],

# 位置 2: 第 3880 行附近 — 顶层 agent_id 参数
"enum": ["kimi", "claude", "codex", "openclaw", "hermes-internal", "deepseek-worker", "...", "..."],
```

同时更新 `description` 字段中的 AGENTS 列表。

#### 步骤四：角色审计复查（关键步骤）

技术配置完成后，**再读一遍手册**，逐项比对新 Agent 的以下字段是否匹配：

| 审计项 | 检查内容 |
|--------|----------|
| `type` | 是否与手册角色定位一致 |
| `capabilities` | 是否有不应有的能力（如 codex 不该有 file_modification）|
| `not_for` | 手册说的「不做」是否都在这里 |
| `toolsets` | 是否需要 terminal（代码评审需要 git diff）+ 是否需要 browser（调研需要）|
| `blocked_tools` | 纯文职角色（皮尔洛）必须 blocked terminal |
| `model` | 是否需要单独配置（如 hermes-internal 用 Pro 而不是 default）|

**审计输出格式：**
```text
xxx 角色设定：
- type: ✅/❌ — 原因
- capabilities: ✅/❌ — 原因
- not_for: ✅/❌ — 原因
- toolsets: ✅/❌ — 原因
- blocked_tools: ✅/❌ — 原因
- model: ✅/❌ — 原因
```

#### 步骤五：重启 gateway

```bash
hermes gateway restart
# 或
hermes gateway run --replace
```

#### 步骤六：连通性测试

用简单任务测试每个新 Agent：

```python
delegate_task(agent_id='nesta', goal='回复此消息确认路由正常')
```

验证返回结果中的 `effective_toolsets` 和 `blocked_tools` 是否符合预期。

#### 步骤七：更新手册的角色表

将手册中「待创建」标记改为实际 agent_id，更新模型/工具列。

#### 真实案例（2026-05-13 添加 3 个 Agent）

| Agent | 审计发现的问题 | 修复 |
|-------|---------------|------|
| 皮尔洛 (pirlo) | 有 `research_synthesis` 能力，但手册说「不做调研」 | 改为 `information_organization` |
| codex | 有 `file_modification` 和 `script_execution`，但手册说「不改代码」 | 去掉这两个能力 |
| OpenClaw | 仍是 `desktop_operator` 类型，手册已改为调研专员 | 改为 `researcher`，同步更新路由 |

### 8. 角色审计：type/capabilities 常见错误

| 错误模式 | 问题 | 修复 |
|---------|------|------|
| type 与手册角色不匹配 | OpenClaw 是 desktop_operator 但手册说要调研 | 改为 researcher |
| capabilities 含不应有的能力 | codex 有 file_modification 但手册说「不改代码」 | 去掉 |
| capabilities 多了不该有的能力 | 皮尔洛有 research_synthesis 但手册说「不做调研」| 改为 information_organization |
| toolsets 与能力矛盾 | 纯文职角色有 terminal | blocked terminal |
| not_for 过于简略 | 只写「复杂代码修改」不够 | 精确列出手册的「不做什么」|

### 9. Profile 技能可见性陷阱：全局 skill 不会自动同步到 Profile

**问题：** 把新 skill 安装到 `~/.hermes/skills/`（全局）后，通过 `hermes -p <profile>` 运行的 Agent **看不到**这个 skill。Hermes 加载技能时，profile 优先从自己的 `skills/` 目录加载，不回退到全局目录。

**症状：**
- `hermes skills list | grep <skill>` → 可见（主 profile）
- `hermes -p <profile> skills list | grep <skill>` → 不可见（子 profile）

**修复：** symlink 全局 skill 到目标 profile 的 skills 目录

```bash
ln -s /Users/gu/.hermes/skills/<new-skill> /Users/gu/.hermes/profiles/<profile>/skills/<new-skill>
```

**验证：**
```bash
hermes -p <profile> skills list | grep <new-skill>
# 应显示为 local/enabled
```

**适用场景：**
- 为皮尔洛安装 Humanizer-zh（全局已装，但 piero profile 看不到）
- 为安布罗西尼安装新的分析 skill
- 为内斯塔安装新的技术 skill

**不适用场景：**
- `devops` 分类下的 skill（kanban-worker 等）——直接用全局 `devops` 的 symlink 即可
- 系统内置 skill（builtin）——始终可用

**真实案例（2026-05-13）：** 安装 `humanizer-zh` 到全局后，`hermes -p piero skills list | grep humanizer-zh` 返回空。symlink 到 piero 的 skills 目录后，可见且可用。

### 10. Profile 克隆陷阱：feishu_system_prompt 覆盖 SOUL.md

**问题：** 用 `hermes profile create <name> --clone` 新建 Hermes Profile 时，源 Profile 的 `feishu_system_prompt` 会被完整复制到新 Profile 的 `config.yaml` 中。对于飞书 Bot，`feishu_system_prompt` **优先级高于 SOUL.md**，意味着克隆出来的 Bot 人格是源 Profile 的，不是目标 Agent 的。

**症状：**
- 新建的 Profile 已正确配置 SOUL.md
- 网关已连接飞书，回复正常
- 但 Bot 回复的人格是错的（例如显示的是马尔蒂尼的人格，而不是内斯塔）

**根因：**
```yaml
# ~/.hermes/profiles/<name>/config.yaml
feishu:
  extra:
    feishu_system_prompt: "你是马尔蒂尼，用户的私人助理..."
    # ↑ 这个被克隆过来了，覆盖了 SOUL.md
```

**修复：**
1. 手动修改该 Profile 的 `config.yaml`，将 `feishu_system_prompt` 改为目标 Agent 的 prompt
2. 或直接删除该字段（让 SOUL.md 生效）

**验证方法：**
```
grep "feishu_system_prompt" ~/.hermes/profiles/<name>/config.yaml
# 检查内容是否与目标 Agent 匹配
```

### 10. Profile 重命名 + agent-registry.json 同步流程

当需要更改 Agent 的名称时（如代号名 → 真名），需要同步修改三处配置以确保一致性：

**需要修改的三处配置：**

| 修改位置 | 原因 | 命令/方法 |
|---------|------|----------|
| Profile 目录名 | Kanban 看板使用 profile 名作为 assignee 显示 | `hermes profile rename <old> <new>` |
| agent-registry.json 的 key | `delegate_task(agent_id='<name>')` 通过 key 查找 | Python JSON 操作 |
| agent-registry.json 的 id 字段 | 与 key 一致，agent 自述身份用 | 同上 |

**标准操作流程：**

```bash
# Step 1: 重命名 profile
hermes profile rename old-name new-name
# 输出：✓ Renamed old-name → new-name
# 注意：profile 下的 config.yaml、SOUL.md、skills 全部保留

# Step 2: 更新 agent-registry.json
# 用 Python 修改 JSON key 和 id 字段
python3 -c "
import json
path = '/Users/gu/.hermes/config/agent-registry.json'
with open(path) as f: data = json.load(f)
agents = data['agents']
if 'old-name' in agents:
    agents['new-name'] = agents.pop('old-name')
    agents['new-name']['id'] = 'new-name'
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('Done:', 'old-name', '→', 'new-name')
"

# Step 3: 验证
python3 -c "import json; json.load(open('/Users/gu/.hermes/config/agent-registry.json')); print('JSON valid')"
```

**影响范围：**

| 维度 | 影响 | 如何修复 |
|------|------|---------|
| `delegate_task(agent_id='old-name')` | ❌ 失效，必须用新名称 | 更新 agent-registry.json key |
| Kanban 旧任务 | ❌ 仍显示旧名 | 归档旧任务，用新名重建 |
| Kanban 新任务 | ✅ 显示新名 | `--assignee new-name` 即可 |
| Feishu Bot | ❌ 不受影响 | Bot 凭据在 .env 中，profile 名无关 |

**验证 rename 后 kanban 可用性：**

```bash
# 确保新 profile 能被 kanban 调度
hermes -p new-name skills list | grep kanban-worker
# 如缺少 → ln -s /Users/gu/.hermes/skills/devops ~/.hermes/profiles/new-name/skills/devops
```

**真实案例（2026-05-13）：**
- `hermes profile rename hermes-internal ambrosini`
- agent-registry.json key: `"hermes-internal"` → `"ambrosini"`, id: `"hermes-internal"` → `"ambrosini"`
- Kanban 看板：旧任务 t_5deb2903 仍显示 `@hermes-internal` → 归档重建后显示 `@ambrosini` ✅

### 11. agent-registry.json 修复工作流（已验证模式）

当多 Agent 测试发现配置缺陷时，采用以下工作流修复：

#### 修复流程

```
全链路测试 → 发现 agent-registry.json 问题
           → 马蒂尼整理问题清单
           → 内斯塔（B）读文件 + 出精确任务包（含 old_string/new_string）
           → Claude Code 按任务包顺序执行 patch
           → 马蒂尼验证结果（JSON valid + soul 字段数）
```

#### 此流程已验证（2026-05-13）

| 发现的问题 | 修复方式 | 状态 |
|-----------|---------|------|
| hermes-internal type/soul 矛盾（analyst vs quality_gate） | type→quality_gate, capabilities 改 review/verification | ✅ 已验证 |
| deepseek-worker 缺 soul | 新增 soul 字段 | ✅ 已验证 |
| deepseek-tui 缺 soul | 新增 soul 字段 | ✅ 已验证 |
| deepseek-worker toolsets 缺 terminal | toolsets 加 terminal | ✅ 已验证 |

**内斯塔的任务包规范**：每问题一个任务包，含：
- 文件路径（绝对路径）
- 修改位置（行号范围）
- 精确 old_string → new_string 替换对
- 修改后预期结果
- 执行顺序建议（依赖关系分析）

**Claude Code 执行规范**：严格按顺序，每步用 patch 工具（非写文件），完成后 JSON 校验。

#### 关键 pitfall：hermes-internal type/soul 矛盾模式

当 agent 的 `type` 与 `soul` 描述的职能不一致时，这是一个设计级缺陷而非配置错误：

```json
// ❌ 矛盾示例
"type": "analyst",        // 分析师 — 分析、决策、方案
"soul": "你是 G 质量审核角色。结论只能是 +1 通过或打回"  // QA gate
```

**修复原则**：以 `soul` 为准（soul 是角色人格定义，type 是系统分类）。如果 soul 说「只做审核」，则：
- type → `quality_gate`
- capabilities → 去掉分析/创意能力，增加 review/verification
- best_for → 改为审核相关描述
- delegation.method 和 subagent_profile 保持

### 11. OpenClaw 连接冲突：Bot Profile 上线前的必要清理

**问题：** 当为一个已有的飞书 Bot 创建独立的 Hermes Profile（Profile B）时，如果该 Bot 之前由 OpenClaw（或其他服务）通过 WebSocket 长连接处理消息，**Hermes 和 OpenClaw 不能同时连接同一个飞书 Bot**。飞书开放平台只允许一个 WebSocket 长连接客户端。

**症状：**
- Profile B 的 Gateway 已运行且显示 `feishu: connected`
- 但在飞书 DM 该 Bot 时，回复来自 OpenClaw 的默认模板（如 "AI 助手，跑在 OpenClaw 上"）
- Profile B 的 Gateway 日志中没有收到该 DM 消息

**排查：**
```bash
# 1. 确认 OpenClaw 是否还连接着该 Bot
grep -A 3 "appId.*cli_a9434\|enabled" ~/.openclaw/openclaw.json | head -10
# feishu.enabled: true → OpenClaw 还在连接

# 2. 确认 Hermes Gateway 已连接
cat ~/.hermes/profiles/<name>/gateway_state.json | grep feishu
# feishu.state 应为 connected
```

**修复：**
1. 在 OpenClaw 配置中禁用该 Feishu 频道：`~/.openclaw/openclaw.json` → `channels.feishu.enabled: false`
2. 停止 OpenClaw Gateway：`openclaw gateway stop`
3. 确认 OpenClaw 进程已退出：`ps aux | grep openclaw`
4. 重启目标 Hermes Profile 的 Gateway
5. 验证：在飞书 DM 该 Bot，检查回复是否来自 Hermes

### 12. 完整 Named Agent 添加流程（含飞书 Bot Profile 创建）

新增一个 Named Agent 到 Hermes 系统需要走完整流程。当 Agent 需要独立飞书 Bot 时，还需创建 Hermes Profile。

### 13. Feishu DNS 间歇故障（环境级风险）

**发现来源**：gateway.error.log 中频繁出现 DNS 解析失败。

**症状**：
```
ERROR Lark: connect failed, err: HTTPSConnectionPool(host='open.feishu.cn', port=443):
  Max retries exceeded — Failed to resolve 'open.feishu.cn' (NameResolutionError)
ERROR Lark: receive message loop exit, err: sent 1011 (internal error) keepalive ping timeout
```

**影响**：飞书 WebSocket 连接断连，重连期间 Bot 消息可能丢失或延迟。自动重连逻辑存在（通常 1-2 次后恢复），但不可预测。

**诊断**：
```
grep -E "keepalive ping timeout|reconnect|NameResolutionError" ~/.hermes/logs/gateway.error.log
```

**性质**：系统/网络层问题，非配置可修复。可尝试切换公共 DNS 或 /etc/hosts 硬编码缓解。

### 14. 批量 YAML frontmatter 编辑：子 Agent 的脆弱区

**问题**：让子 Agent（特别是 Claude Code）批量编辑 YAML frontmatter 文件（如给 50+ SKILL.md 加字段）高度不可靠。子 Agent 的 YAML 解析/重写逻辑容易出错，导致：
- frontmatter 缩进层级错乱（`agents:` 插入到子层级而非根层级）
- frontmatter 整体被删除（正则匹配失败导致写回空 frontmatter）
- 文件被批量损坏，需要 git 恢复

**真实案例（2026-05-15 Agent-Scoped Skills Phase 1）**：Claude Code 用 Python 脚本批量处理 53 个 SKILL.md，第一次写错了缩进，第二次修复脚本的正则把全部 frontmatter body 删除了。57 个文件损坏，全部通过 `git checkout -- skills/` 恢复。

**推荐做法**：
- **结构化批量 frontmatter 编辑**：由你（主控）直接写 `execute_code` 做 Python 字符串操作，不要在 frontmatter 上做 YAML 解析——直接用 `re.match` + 纯字符串插入
- **如果必须委托**：给子 Agent 一个精确的 Python 脚本（不是让它自己写），在本地先测试 1 个文件再批量
- **回滚准备**：批量操作前先 `git add && git stash` 或确保 git clean 可恢复
- **不用 YAML 库**：frontmatter 是 Markdown 的 YAML 块，用 `re` 正则读取写入比 YAML 解析库更安全

**SKILL.md agents 字段约定**（Agent-Scoped Skills 实施后）：
- 所有 SKILL.md frontmatter 必须有 `agents: [...]` 字段，声明此 skill 对哪些 Agent 可见
- 未声明 `agents` 的 skill → 默认对所有 Agent 不可见（安全默认）
- 新增 skill 时：加 SKILL.md → 写 `agents` 标签 → 决定是否更新 `agent-registry.json` 中对应 agent 的 `skills` 数组
- agents 标签值必须匹配 `agent-registry.json` 中的 agent `id` 字段

**状态**：Hermes 内置的 Kanban 任务板已接入「懂球帝营销中心」看板，运行端到端链路已验证通过。

| 组件 | 状态 |
|------|------|
| `kanban.db` SQLite 数据库 | ✅ 已初始化（default + dongqiudi 双看板） |
| `hermes kanban` CLI | ✅ 完整可用（create/list/assign/complete/block/tail/log） |
| Web UI Kanban 面板 | ✅ 有内容（3 任务链路已验证） |
| Gateway 调度器（每 60s） | ✅ 已配置 |
| kanban-orchestrator / kanban-worker skills | ✅ 已安装 |
| **端到端工作流已跑通** | ✅ **已验证**（内斯塔→皮尔洛→安布罗西尼） |

**已验证的完整链路**（2026-05-13）：
1. T1（内斯塔）→ dispatcher 派发 → 读文件分析 → 完成 ✅
2. T2（皮尔洛）→ 依赖 T1 完成 → 自动升 ready → 派发（首次 crash 因 skill 缺失，修复后成功）✅
3. T3（安布罗西尼）→ 依赖 T2 → 自动升 ready → 派发 → 发现 workspace 为空 → 阻塞并写详细审核意见 ✅

**已验证的能力**：
- 依赖链自动传导（parent done → child auto-promote）
- Dispatcher 自动派发（每 60s 或手动 `hermes kanban dispatch`）
- 质量审核阻断（安布罗西尼正确识别缺少实体文件并阻塞）
- Web UI 可视化管理（分组、状态、完成/归档操作）

**已知限制**：
- 调度器 spawn worker 时依赖 `kanban-worker` skill 在目标 profile 中可用（见「Profile 技能依赖」pitfall）
- DeepSeek API 在并发子会活中的模型推理超时问题仍可能影响

**适合接入的场景**：
- 需要 2 个以上 Agent 按顺序协作的复杂任务（探代码 → 写方案 → 审核）
- 需要断点恢复的任务链
- 需要审计轨迹的跨 Agent 协作

**目前 8 个 Agent 通过以下机制协作**：
- Feishu Bot DM（马蒂尼/内斯塔/皮尔洛）— 独立对话
- `delegate_task`（所有 Agent）— 上下文注入
- **Kanban 看板**（新建）— 跨 Agent 任务移交和进度追踪
- Cron 定时任务（加图索）— 情报推送

#### 步骤八（可选）：创建独立飞书 Bot Profile

如果 Agent 需要用户在飞书直接 DM（而非仅通过 delegate_task 调用），创建独立 Hermes Profile：

```bash
# 1. 克隆主 Profile
hermes profile create <agent-name> --clone

# 2. 编写 SOUL.md
edit ~/.hermes/profiles/<agent-name>/SOUL.md

# 3. 更换飞书 Bot 凭证
# ~/.hermes/profiles/<agent-name>/.env
# FEISHU_APP_ID=<目标 Bot 的 app_id>
# FEISHU_APP_SECRET=<目标 Bot 的 app_secret>

# 4. ⚠️ 关键清理：修改 feishu_system_prompt（克隆带来的）
# ~/.hermes/profiles/<agent-name>/config.yaml
# feishu_system_prompt 改为目标 Agent 的 persona

# 5. ⚠️ 可选清理：删除无关的 channel_skill_bindings
# 源 Profile 的斯塔姆绑定等不需要带过来

# 6. ⚠️ 可选清理：修改 api_server 端口或直接禁用\n# 克隆带来的 .env 可能有 API_SERVER_ENABLED=true\n# 如果 8642 端口已被主 gateway 占用，api_server 会不断重试\n# 最佳做法：直接禁用（纯飞书 Bot 不需要 api_server）\n# ~/.hermes/profiles/<agent-name>/.env\n# API_SERVER_ENABLED=false\n\n# 7. ⚠️ 可选清理：删除无关的 channel_skill_bindings\n# 源 Profile 的斯塔姆绑定等不需要带过来\n\n# 8. ⚠️ 可选清理：裁剪 skills（克隆带来 150+ skills）\n# 飞书 Bot Profile 不需要所有母库的 skill\n# 只保留与角色定位相关的 skill：\n# 技术类（内斯塔）：autocli, autonomous-ai-agents, devops, github, hermes,\n#   hermes-gateway-debug, hermes-multi-agent-research, hermes-subagent-delegation,\n#   productivity, software-development\n# 方案类（皮尔洛）：额外保留 creative, html-ppt, huashu-design, magazine-web-ppt\n# 按需删减：rm -rf ~/.hermes/profiles/<agent-name>/skills/<skill-name>/\n\n# 9. ⚠️ 必要：确认 OpenClaw 没有连接该 Bot（见 Pitfall 10）\n\n# 10. 启动 Gateway
<agent-name> gateway run --replace

# 9. 验证
# 在飞书 DM 该 bot → 检查回复的人格是否匹配 SOUL.md
```

**Profile 部署后检查清单：**

| 检查项 | 做法 |
|--------|------|
| feishu_system_prompt | `grep "feishu_system_prompt" config.yaml` — 必须与目标 Agent 匹配，而非克隆源 |
| api_server | `grep "API_SERVER_ENABLED" .env` — 纯飞书 Bot 建议设为 false 避免端口冲突 |
| SOUL.md 存在 | `cat SOUL.md` — 人格定义是否正确 |
| .env 凭证 | `grep FEISHU_APP_ID .env` — 必须是目标 Bot 的 app_id |
| channel_skill_bindings | `grep channel_skill_bindings config.yaml` — 克隆带来的绑定可能不适用 |
| skills 裁剪 | `ls skills/ | wc -l` — 克隆可能带来 150+ 不相关 skills，按角色裁剪 |
| OpenClaw 冲突 | `grep "enabled" ~/.openclaw/openclaw.json` — 确保目标 Bot 的 channel 已禁用 |
| Gateway 连接 | `cat gateway_state.json` — feishu.state 应为 connected |
| 飞书 DM 测试 | 在飞书发消息给该 Bot → 回复人格正确 |

**Profile 重命名（替代克隆）**

当需要更改已有 Profile 的名称时（例如 agent 从代号名改为真名），使用重命名而非克隆+重建：

```bash
hermes profile rename <old-name> <new-name>
```

这会重命名 `~/.hermes/profiles/<old-name>/` → `~/.hermes/profiles/<new-name>/` 并更新 Profile 注册表。现有配置和 SOUL.md 保持不变。

**注意事项：**
- Kanban 看板使用 Profile 目录名作为 assignee 标识符，重命名后新任务可用新名称创建，但旧任务仍显示原名
- agent-registry.json 的 key 不会自动更新。如果该 Profile 同时也作为 `delegate_task(agent_id='...')` 的目标，需要手动修改 agent-registry.json 的 key 和 id 字段
- Gateway 进程需重启才能用新名称运行：`hermes -p <new-name> gateway run --replace`

**真实案例：** `hermes profile rename hermes-internal ambrosini` — 重命名后 kanban 看板显示 `@ambrosini` 而非 `@hermes-internal`。agent-registry.json 的 key 也同步从 `"hermes-internal"` 改为 `"ambrosini"`，并将 `id` 字段改为 `"ambrosini"`。

**真实案例（2026-05-13 内斯塔 Profile 部署）：**
- 克隆后 `feishu_system_prompt` 为"你是马尔蒂尼"（源 Profile 的），导致 Bot 回复马尔蒂尼人格
- OpenClaw 配置中 `channels.feishu.enabled: true`（内斯塔 Bot 的 app_id），导致消息被 OpenClaw 拦截
- 修复：改 feishu_system_prompt + 禁 OpenClaw channel + 重启 gateway
- 完整记录见 `references/profile-deployment-nesta-2026-05-13.md`

当创建独立 Hermes Profile 为 Agent 提供独立飞书 Bot 时，需要该 Bot 的 `FEISHU_APP_SECRET`。**这个 secret 很难通过命令行获取：**

| 尝试方法 | 结果 | 原因 |
|---------|------|------|
| `security find-generic-password -w` | item not found | Keychain 条目无法通过命令行搜索到 |
| browser clipboard.readText() | timeout | 沙箱拦截 clipboard API |
| `keyring.get_password()` | ModuleNotFoundError | keyring 库未安装 |

**可靠方法：** 让用户自己在飞书开放平台 → 应用 → 凭证与基础信息 → 点击复制按钮，然后粘贴给你。

### 跨 Profile 委托（独立 Gateway 通信）

当子 Agent 运行在独立的 Hermes Profile 中（不同 gateway 进程），不能使用 `delegate_task`。改用 api_server 做 HTTP 通信：

**架构：**
```
马蒂尼 gateway ←→ HTTP/curl → 皮尔洛 profile gateway (api_server :8643)
```

**马蒂尼调用皮尔洛：**
```bash
curl -s http://127.0.0.1:8643/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "审查这个仓库 /path/to/repo"}]
  }'
```

**适用场景：**
- 需要完全上下文隔离（不同飞书 Bot）
- 需要不同的 skillset / 模型
- 不需要实时同步响应（HTTP stateless）

**局限性：**
- 每次调用都是无状态的（除非传 session_id）
- 马蒂尼需要等 HTTP 返回，不能异步等待
- 通信数据量大时有序列化开销

详细团队架构设计见 `hermes-multi-agent-research` skill 的 §I — 多 Agent 团队架构设计。

**详细接入手册**：见 Obsidian wiki → `3-知识/wiki/AI与Agent/Hermes/多Agent系统接入手册.md`
该手册完整记录了：
- 架构总览（双层控制：配置层 + 代码层）
- 每种 Agent 的接入方式（ACP子进程 / 内部AIAgent / 外部服务）
- 需要修改的文件位置（delegate_tool.py 第3785行和第3814行 enum）
- 当前 6 个 Agent 的状态快照
- 配置文件关键段参考

**以后问多Agent系统问题，先查该手册作为入口。** 如果手册可能过期、要确认当前实现、排查根因或验证运行状态，继续查源码、配置、日志和实际调用结果。

#### 快捷参考：新增 Agent 的两种模式

| 模式 | 适用 | 需改动 | 示例 |
|------|------|--------|------|
| **注册为 Named Agent** | 需要 `delegate_task(agent_id=...)` 派发 | ① `delegate_tool.py` enum（两处）+ ② `agent-registry.json` | claude, codex |
| **CLI 子进程封装** | 快速接入，无需改 Hermes 源码 | 仅终端调用 | `deepseek-tui exec --auto --json "任务描述"` |

## 使用模式：多文档分析 + 报告生成

### 单视角分析 — 用 deepseek-tui 做深度工程审计

详见 `references/multi-doc-analysis-deepseek-tui.md`。

### 多视角分析 — 用多个 Agent 做交叉评估

> 当用户要求对同一系统/问题做全面评估时，可以把同一任务派发给**不同定位的 Agent**，让各 Agent 从自己的角度输出独立报告。视角按任务需要分配，不固定绑定某个 Agent。

#### 工作流

```text
用户指令 (如 "用X分析评估XX系统，用Y分析评估XX系统，用Z分析评估XX系统")
  │
  ├─ Step 1: 收集源文档（同上）
  │
  ├─ Step 2: 分包派发（并行或串行）
  │
  │   ├─ 派A → 当前适合工程审计的 Agent
  │   │    工程视角：代码正确性、安全漏洞、schema验证
  │   │    goal: 读取 /tmp/input.md，从6个技术维度分析，输出结构化Markdown
  │   │
  │   ├─ 派B → 当前适合用户体验评估的 Agent
  │   │    用户视角：好不好用、学习成本、是否过度设计
  │   │    goal: 读取源文档，从用户角度分析需要加强/可以简化的地方
  │   │    context: "Respond in Chinese. You are analyzing from a non-technical user's perspective."
  │   │
  │   └─ 派C → 当前适合产品/策略分析的 Agent
  │       产品视角：功能优先级、产品路线图、典型用户旅程
  │       goal: 读取源文档，从产品经理角度分析
  │       context: "Respond in Chinese. This is the THIRD analysis — offer a distinct perspective."
  │
  ├─ Step 3: 保存各报告到 Obsidian wiki
  │   路径：个人知识库/3-知识/wiki/AI与Agent/Hermes/
  │   命名：<主题><视角>评估-<引擎名>.md
  │   例如：
  │     - Agent系统全面评估报告-v2.7.md           (工程视角)
  │     - Agent系统用户视角评估.md                (用户视角)
  │     - Agent系统产品视角评估.md                (产品视角)
  │
  └─ Step 4: 更新 wiki 索引（添加全部三条链接）
```

#### 视角分配指南

| 视角 | 适合的 Agent 类型 | prompt 关键词 |
|------|-------------------|--------------|
| 工程/技术 | 当前擅长代码审计、安全、架构、数据流的 Agent | "从X个技术维度分析，标注CRITICAL/HIGH/MEDIUM/LOW" |
| 用户/体验 | 当前擅长易用性、学习成本、过度设计判断的 Agent | "从非技术用户视角，哪些好哪些复杂，3-5条行动建议" |
| 产品/策略 | 当前擅长优先级、路线图、MVP、竞品判断的 Agent | "从产品经理视角，功能矩阵、典型旅程、分阶段路线图" |

#### 关键规则

1. **每个 agent 独立分析** — 不让后分析的 agent 看到前一份报告，除非用户要求"参考/对比"。
2. **如果用户要求参考前序报告** — 在 context 中明确"这是第N次分析，请与之前结果形成差异对比"。
3. **文件命名必须区分引擎** — 用 `-deepseek-tui.md` / `-ClaudeCode.md` / `-Codex.md` 后缀避免覆盖。
4. **报告长度范围** — 6K-15K tokens 之间。工程审计最长（~15K），用户视角最短（~6K）。
5. **大数据输入先确认通道能力** — 如果 CLI 不支持 stdin、参数长度或文件读取，优先用能读取文件的 `delegate_task(...)` 或其他可靠委托通道。

#### Obsidian wiki 更新陷阱

当更新 `index.md` 添加新链接时，注意：
- `read_file` 显示 `||` 前缀（行号 `|` 内容），**实际内容只有单 `|`**
- 用 `patch` 工具时 new_string **必须用单 `|` 前缀**
- 子目录文件用 `[[子目录/文件名]]` 格式（如 `[[Hermes/文件名]]`）
- 索引在 `AI与Agent/` 根目录，文件在 `Hermes/` 子目录
- 对比表格条目用 `| **[[Hermes/文件名]]** | **描述文字** |` 加粗样式

详见 `references/multi-perspective-analysis.md`。

### 场景

用户要求对一组文档进行全面分析评估，生成结构化报告并存入 Obsidian wiki。

### 工作流

```
用户指令 (如 "用deepseek-tui 全面分析评估XX系统")
  │
  ├─ Step 1: 收集源文档
  │   从 Obsidian wiki 读取所有相关文件
  │   注意文件大小，长文档可能需多次 read_file
  │
  ├─ Step 2: 聚合为单一输入文件
  │   写入 /tmp/ds_analysis_prompt.md
  │   包含：分析指令(维度/格式要求) + 所有文档内容(用---分隔)
  │
  ├─ Step 3: 委托当前适合的深度分析 Agent
  │   delegate_task(
  │     agent_id='<current-analysis-agent>',
  │     goal='读取 /tmp/ds_full_input.md，按X个维度分析...',
  │     context='输出语言中文，报告要详细结构化'
  │   )
  │   ⚠️ 如果某个 CLI 不支持 stdin 管道或大输入，
  │      delegate_task 方式更可靠（agent 自己用 read_file 读文件再分析）
  │
  ├─ Step 4: 保存报告到 Obsidian wiki
  │   路径：个人知识库/3-知识/wiki/AI与Agent/Hermes/<文件名>.md
  │   文件命名规范：<主题><评估报告/分析>-<版本>.md
  │
  └─ Step 5: 更新 wiki 索引
       修改 index.md 添加新条目
       注意：Obsidian 表格内 wikilink 用单 `|` 前缀
       子目录文件用 [[子目录/文件名]] 格式
       index.md 在 wiki 根目录，Hermes 文件需加 Hermes/ 前缀
```

### 关键洞察

- 某些 CLI 不支持标准输入管道（stdin pipe），复杂多文档分析应使用能读取文件的委托方式
- 被委托 Agent 必须具备 file/read 工具，能自行 read_file 读取输入文件
- 报告输出约 6K-15K tokens，直接写回 Obsidian wiki
- 更新 index.md 时要小心 Obsidian 表格格式：read_file 显示为 `||` 前缀，实际内容只有单 `|`

### Pip install/Python 环境

如果 deepseek-tui 需要 Python 集成，当前环境为 `python3` → `~/.local/bin/python3` (uv 管理的 3.12.12)。

## Coding Task Spec + Delegate Pattern

当用户要求修改代码（如扩展、脚本、配置文件），且明确偏好多Agent系统完成时，不要手动用 `patch`/`read_file`/`terminal` 做逐行修改。采用以下模式：

### 触发条件

- 用户说 "你别自己搞，用多Agent做" / "派XXX去做"
- 涉及跨文件的代码修改（2+ 文件）
- 修改逻辑较复杂（非单一字符串替换可搞定）

### 工作流

```text
用户：帮我改[项目]，增加[功能]/[配置]
  │
  ├─ Step 1: 读代码，理解结构
  │   read_file / search_files 扫清楚下面几点：
  │   - 文件组织结构
  │   - 现有函数/数据流（关键 import、事件绑定）
  │   - 配置存储方式（chrome.storage.sync、localStorage 等）
  │
  ├─ Step 2: 写详细 spec
  │   context 中必须包含：
  │   - 工作目录（绝对路径）
  │   - 需要改的 2-3 个文件和各自改什么
  │   - 新加函数的签名/行为
  │   - 用户说的「为什么」——不懂为什么改就猜不对
  │   - 输出语言偏好
  │   ⚠️ 不要写 "按用户意图" 或 "发挥创意"——要写具体
  │
  ├─ Step 3: 派 coding agent
  │   delegate_task(
  │     agent_id='deepseek-tui',  # 或用户指定的 agent
  │     goal='明确的改动目标',
  │     context='完整 spec（工作目录 + 文件列表 + 改动细节）',
  │     toolsets=['terminal', 'file']
  │   )
  │
  └─ Step 4: 验证 & 报告
      - 用 read_file 检查改动后的关键段
      - 确认无语法错误（import 名、函数签名引用正确）
      - 向用户总结：改了什么、怎么用、要不要试
```

### 关键规则

| 原则 | 要做 | 不要做 |
|------|------|--------|
| **Spec 要具体** | `在第3个 files 数组的 object 加 baseUrl 字段，值从模型定义取` | `加个配置让用户能选` |
| **先读再派** | 先看当前代码结构，再写 context | 不读直接派，容易写错函数名/路径 |
| **spec 里的路径必须是绝对路径** | `/Users/gu/Downloads/xxx/` | `~/Downloads/xxx/` |
| **验证必有** | 每次派完都要 read_file 确认 | 看了 subagent 报告就完事 |

### 🔴 多轮派发陷阱：文件状态漂移

**问题**：当先后派两个 coding agent 修改同一批文件时，第二个 agent 读到的可能是旧版本，父 Agent 的 read_file 缓存也可能是旧的。

**诊断方法**：
```bash
# 对比 subagent 报告的代码内容和实际磁盘文件
# 看文件大小和结构是否一致
ls -la /path/to/file.js
wc -l /path/to/file.js

# 看文件头部的 import/export 是否符合预期
head -30 /path/to/file.js
```

**修复方法**：

| 方案 | 做法 | 适用场景 |
|------|------|---------|
| 手动重新补 | 父 Agent 用 skill_manage patch 补上缺失的部分 | 少量改动 |
| 重新派一轮 | 先重新读文件，再写新 spec 派 | 改动较多或结构变了 |
| 一次派到底 | 把所有改动写进同一个 context，只派一次 | 改动已知时推荐（避免漂移） |

**预防**：
- 多轮派发时，每轮之间先用 `read_file` 或 `terminal` 重新读取被改文件的最新状态
- 如果第一轮涉及完整重写（不只是增量修改），第二轮也走完整重写而非 patch
- 优先把全部改动合并在一次 delegation 的 context 中，避免多轮漂移

**真实案例 — image2prompt 预设模型添加（2026-05-12）**：
1. **第一轮**：派 deepseek-tui 为 image2prompt 增加 OpenAI 兼容 provider → 它做了**完整架构重写**（从三提供商变为多提供商架构），`provider-catalog.js` 从 4 个 provider 变为 7 个 `BUILTIN_PROVIDERS`
2. **第二轮**（用户要求补充更多预设）：派另一个 deepseek-tui 去添加 flashapi/Claude 等模型 — 但它读到的代码还是**旧架构**（`PROVIDER_CATALOG` + `openai_compat` with `{id, label, tone}`），对新架构（`BUILTIN_PROVIDERS` + `{id, label}`）一无所知
3. **结果**：第二轮 agent 的 patches 全部成功执行，但**写入了错误架构的文件**。磁盘上的实际文件是第一轮的新架构，第二轮对旧架构的 patches 只修改了内存中的旧版本，磁盘上的新架构未被触及
4. **检测方法**：用户在下一轮调用中注意到文件大小不一致（`wc -l` 忽然变少），父 Agent 用 read_file 确认架构已改变
5. **修复**：父 Agent 直接对新架构的 `provider-catalog.js` 执行 `patch`，添加 flashapi 和 zai 两个提供商的完整配置块

**教训**：
- 如果第一轮 agent 的 summary 说"重写了整个文件"或文件大小变化超过 20%，第二轮必须重新读文件确认结构
- 轮次之间用 `ls -la` + `head` 快速校验文件结构是否一致
- 最简单的预防：如果改动全部已知，就把所有修改写进一次 delegation

### 真实案例

**image2prompt Chrome 扩展添加 OpenAI 兼容预设模型（2026-05-11）**：
1. Hermes 先读 `provider-catalog.js`、`options.js`、`background.js` → 理解结构：models 是 `{id, label, tone}`，预设切换在 `handleProviderModelPresetChange`
2. context 写清楚：每个模型加 `baseUrl`、导出一个 `getModelById`、切换时自动填 baseUrl
3. 派 deepseek-tui → 85s 完成 3 个文件修改（provider-catalog models + export，options import + handler）
4. Hermes verify read_file → 全部正确

**关键经验**：deepseek-tui 擅长这种「读现有结构 → 按 spec 做增删改」的模式，一次成功。不要自己手改。

## Codebase Deep-Dive Debugging with Codex

当需要对一个复杂代码库做**深度调试**时（读 30+ 文件、找根因、改代码、跑测试），用 `delegate_task(agent_id='codex')` 比手工逐个读文件效率高得多。

### 触发条件

- 某个系统（如 Open Design、Claude Code adapter）报奇怪的 bug
- 错误信息不明显（如 `(unnamed) error` 或参数为空 `{}`）
- 怀疑是深层的代码逻辑/提示词冲突/配置错配
- 需要跨多个文件追踪数据流

### 工作流

```text
用户：XX系统有个bug，错误现象是[描述]
  │
  ├─ Step 1: 用户确认目标 → "用Codex修复这个bug" / "让Codex分析"
  │
  ├─ Step 2: 构造委托任务
  │   delegate_task(
  │     agent_id='codex',
  │     goal='深入分析[系统名]的[文件名/函数]，找[具体症状]的根因',
  │     context='[环境上下文：工作目录、关键文件位置、已知排除可能]',
  │     toolsets=['terminal', 'file']  // 需要读写文件
  │   )
  │
  │   关键：goal 要写清楚：
  │   - 项目路径（codex需要 cd 进去）
  │   - 已知不能解决问题方向（避免浪费时间）
  │   - 期望输出：根因定位 + 修复方案 + 验证
  │
  ├─ Step 3: Codex 的典型行为模式
  │   ① search_files + read_file 扫描源码结构（可读 50+ 文件）
  │   ② 定位出问题函数/模块
  │   ③ 分析数据流或提示词组合逻辑
  │   ④ 用 git diff 确认改动内容
  │   ⑤ 应用修复（patch）
  │   ⑥ 运行相关测试验证
  │   ⑦ 报告结果（subagent summary）
  │
  └─ Step 4: 验证 & 整合
       - 检查测试是否通过
       - 重启服务验证运行时代码已更新
       - 从 Codex 报告提取关键信息写入 Obsidian wiki
```

### 关键给 Codex 的 goal 写法原则

| 原则 | 好的写法 | 差的写法 |
|------|---------|---------|
| 具体路径 | `工作目录: ~/open-design/, 关键文件: apps/daemon/src/server.ts` | `看那个项目的bug` |
| 排除法 | `不是 permissions 问题，已经试过 --dangerously-skip-permissions` | `修复它` |
| 现象精确 | `Write 调用传空参数 {}，InputValidationError` | `agent 报错` |
| 期望输出 | `找出根因并给出修复方案` | `看看怎么回事` |

### 真实案例

详见 `references/codex-deep-dive-open-design.md` — Codex 对 Open Design daemon 的深度调试实录。

## 参考文件

- `references/8-agent-roster-final-2026-05-13.md` — 8 角色最终配置总表：名称、系统 ID、Profile、Skill 数、瘦身幅度、看板接入状态
- `references/agent-adapter-write-debugging.md` — Agent Write 工具调用传空参数 debug 指南
- `references/codex-deep-dive-open-design.md` — Codex 对 Open Design daemon Write bug 的深度调试分析实录（读 50+ 文件、找根因、修复、跑测试）
- `references/diagnostic-case-kimi.md` — 会话实录：Kimi 子Agent修复全流程
- `references/multi-agent-test-2026-05-13.md` — 全链路多 Agent 测试实录：8 角色测试方法、发现问题、修复记录、kanban 缺口
- `references/large-output-subagent-strategy.md` — 大输出任务子Agent策略（数据嵌入、选型、SVG导出、多轮迭代）
- `references/multi-doc-analysis-deepseek-tui.md` — 多文档分析 + 报告生成实录（2026-05-05）
- `references/soul-injection-delegate-task.md` — Soul/Persona 注入机制详解：agent-registry.json soul 字段 → delegate_tool.py _build_child_system_prompt 修改 + 双路径人格差异排查
- `references/agent-registration-examples-2026-05-13.md` — 新增 3 个 Named Agent 的完整配置 + 角色审计修正案（内斯塔/皮尔洛/Agent TARS + 修正 OpenClaw/codex）
- `references/profile-deployment-nesta-pirlo-2026-05-13.md` — 独立飞书 Bot Profile 部署实录：克隆陷阱、feishu_system_prompt 覆盖、OpenClaw 连接冲突、api_server 端口冲突、skills 裁剪
