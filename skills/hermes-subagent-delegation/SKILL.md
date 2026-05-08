---
name: hermes-subagent-delegation
description: "子Agent（Named Agent / delegation）配置与排障 — agent-registry.json、config.yaml delegation段、toolsets隔离、模型继承"
tags: [hermes, subagent, delegation, troubleshooting]
category: hermes
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

### 5. 新增 Agent 到注册表 ≠ 新增 delegate_task 的 agent_id

`agent-registry.json` 只是路由决策的配置文件，**不决定 `delegate_task` 函数的可用 agent_id 列表**。

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

- `references/agent-adapter-write-debugging.md` — Agent Write 工具调用传空参数 debug 指南：prompt conflict 根因定位 + 修复模式
- `references/codex-deep-dive-open-design.md` — Codex 对 Open Design daemon Write bug 的深度调试分析实录（读 50+ 文件、找根因、修复、跑测试）
- `references/diagnostic-case-kimi.md` — 会话实录：Kimi 子Agent修复全流程
- `references/multi-doc-analysis-deepseek-tui.md` — 多文档分析 + 报告生成实录（2026-05-05）
