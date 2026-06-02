# Hermes 多 Agent 系统架构快照

> 导出时间：2026-06-01T22:12 CST
> 数据来源：`/Users/gu/.hermes/` 权威配置文件 + 实时健康检查
> 主机：MacBook Air M1 / 8GB / macOS 26.5

---

## 1. 系统入口与整体调用链

```
┌────────────────────────────────────────────┐
│              入口层                         │
│  飞书 DM (oc_936c...678)  ← 主入口          │
│  飞书 Home (oc_a171...044) ← 集团频道       │
│  飞书 技术频道 (oc_edbf...3f4) ← Hermes 技术翻译官 │
│  API Server (:8642)        ← 外部调用       │
│  CLI (hermes)              ← 本地调试       │
└──────────────┬─────────────────────────────┘
               │
┌──────────────▼─────────────────────────────┐
│        Hermes Gateway (常驻进程)             │
│  模型：deepseek-v4-pro @ api.deepseek.com   │
│  max_turns: 90 | timeout: 900s              │
│  memory: MEMORY.md 1811/3000 chars          │
│  user_profile: USER.md 551/1375 chars       │
│  人格：马蒂尼 (总控协调者)                    │
└──────────────┬─────────────────────────────┘
               │
┌──────────────▼─────────────────────────────┐
│        delegate_task() 调度层               │
│  model: deepseek-v4-flash                   │
│  max_concurrent_children: 3                 │
│  max_spawn_depth: 1 (不能嵌套委托)           │
│  child_timeout_seconds: 180                 │
│  orchestrator_enabled: false                │
│  subagent_auto_approve: false               │
└──────────────┬─────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    ▼          ▼          ▼          ▼
  9 个编制 Agent（最多同时 3 个并行）
```

---

## 2. Agent 编制清单（9 个已注册 + 1 个未同步）

### 2.1 核心 Agent

| # | Agent ID | 显示名称 | 职责 | 模型 | 权限 | 风险 | 工具边界 |
|---|----------|---------|------|------|------|------|---------|
| 1 | `hermes-internal` | Hermes 技术翻译官 | 技术中间层、需求拆解、策略判断 | GLM-5.1 (fallback: DeepSeek Pro → Qwen-Max → DeepSeek Pro) | **只读** | R0-R3 | file, mcp-codegraph。**禁止** write_file/patch/delegate_task/memory/send_message |
| 2 | `claude` | Claude 主程执行官 | 复杂代码修改、命令执行、git ops | Claude Opus 4.7 (外部 Claude Code CLI) | **需确认** | R1-R3 | file, terminal, git, mcp-codegraph。**禁止** delegate_task/memory/clarify。runtime: claude_code_cli |
| 3 | `deepseek-tui` | DeepSeek 低成本快工 | 小改/小测试/低风险机械执行 | DeepSeek Pro (fallback: Flash → Pro → Flash) | **需确认** | R0-R2 | file, terminal。**禁止** delegate_task/memory/clarify |
| 4 | `codex` | Codex 代码审查官 | 只读代码审查、架构评估 | GPT-5.5 (外部 Codex CLI) | **只读** | R0-R4 | file, terminal, mcp-codegraph。**禁止** write_file/patch/delegate_task/memory。runtime: codex_cli |
| 5 | `pirlo` | Pirlo 商业策划师 | 商业方案、PPT 提案、内容结构 | Kimi 2.6 (fallback: Kimi → MiniMax → DeepSeek Pro) | **只读** | R0-R2 | file only。**禁止** write_file/patch/delegate_task/memory |

### 2.2 专业 Agent

| # | Agent ID | 显示名称 | 职责 | 模型 | 权限 | 风险 | 工具边界 |
|---|----------|---------|------|------|------|------|---------|
| 6 | `intelligence` | Intelligence 情报研究员 | 调研/竞品/资料收集/信息核验 | Kimi 2.6 (fallback: Qwen-Max → Qwen → DeepSeek Flash) | **需确认** | R0-R2 | file, web。**禁止** delegate_task/memory/clarify |
| 7 | `designer` | Designer 视觉设计师 | 海报/视觉型HTML/品牌视觉/图片生成 | Kimi 2.6 (fallback: Qwen-Max → MiniMax → DeepSeek Pro) | **需确认** | R0-R2 | file, terminal, browser, image_gen。**禁止** delegate_task/memory/clarify |
| 8 | `agent-tars` | TARS 桌面操作员 | macOS 桌面/浏览器 GUI/截图/视觉验证 | Mimo-2.5 Pro (fallback: Mimo Omni → Qwen-Max → GPT-5.4) | **需确认** | R0-R2 | desktop, browser, file, terminal。**禁止** delegate_task/memory/clarify |
| 9 | `ambrosini` | Ambrosini 质量门卫 | 高风险验收/最终质量门 | GLM-5.1 (fallback: DeepSeek Pro → Qwen-Max → DeepSeek Pro) | **只读** | R0-R4 | file, mcp-codegraph。**禁止** write_file/patch/delegate_task/memory |

### 2.3 未同步 Agent（健康检查检出）

| Agent ID | 状态 | 说明 |
|----------|------|------|
| `opencode` | ❌ 仅存在于 `agents.yaml`，未同步到 `agent-registry.json` 和 `managed-agents.yaml` | 源码定义了 10 个 Agent，mirror 只有 9 个 |

---

## 3. 任务管道（v2.8 Task Card Pipeline）

### 3.1 管道流程图

```
┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
│ compile   │ → │  verify   │ → │ dispatch  │ → │  review   │ → │  gate     │
│ -task.py  │   │ -task.py  │   │ -task.py  │   │ -task.py  │   │ -policy   │
│           │   │           │   │           │   │           │   │   .py     │
│ 意图→任务卡│   │ outbox合规 │   │ 路由Agent │   │ 审查交付   │   │ 决策路由  │
│ execution │   │ schema验证│   │ timeout:  │   │ intent对照│   │           │
│ mode判定  │   │ 文件存在  │   │   600s    │   │ 越界检查  │   │           │
│ agent选择 │   │           │   │           │   │ must_avoid│   │           │
└───────────┘   └───────────┘   └───────────┘   └───────────┘   └───┬───────┘
                                                                   │
                          ┌────────────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │   gate-policy 决策     │
              │                       │
              │ approved → complete   │
              │ revision_needed →     │
              │   auto_revision loop  │
              │   (最多 N 次返修)       │
              │ hard_stop → reject    │
              │ timeout → switch_agent│
              │ manual_review → 人工   │
              └───────────────────────┘
                          │
              ┌───────────▼───────────┐
              │   run-ledger.py       │
              │   全程 JSONL 日志      │
              │   task-status.py      │
              │   返修链 rollup        │
              └───────────────────────┘
```

### 3.2 各阶段详解

**compile-task.py**（意图编译）
- 输入：user intent → 输出：Task Card JSON
- 从 `agent-registry.json` 加载 Agent 花名册
- 从 `feedback-memory.json` 查找历史规则
- 调用 `determine_execution_mode()` 判定执行模式
- 生成 `execution_plan` 含 primary_agent + secondary_agents
- 写入 `~/.claude/teams/{project}/inbox/{task_id}.json`

**verify-task.py**（交付验证）
- 验证 outbox schema（v2.8 格式）
- 检查 `changed_files` 文件是否存在
- 检查文件修改时间
- 验证 `status` 枚举值
- 验证 `error_taxonomy` 格式

**dispatch-task.py**（Agent 派遣）
- 从 Task Card 提取 `agent_id`（优先级：execution_plan → agent_id → compiled_intent → 默认 claude）
- 构建 delegate_task prompt
- 执行超时 600s
- 写入 outbox + ledger

**review-task.py**（交付审查）
- `check_intent_alignment`：outbox 摘要与 goal 关键词重合 ≥25%
- `check_allowed_files`：changed_files 不能超出 allowed_files
- `check_must_avoid`：不能触碰禁止文件/目录
- 返回 `decision` + `failed_checks` + `revision_instructions`

**gate-policy.py**（策略决策）
- `policy_for()` 5 条分支：
  - approved → `complete`
  - timeout → `switch_agent`
  - hard_stop 失败 → `reject`
  - revision_needed + 可自动修复 → `auto_revision`
  - 其他 → `manual_review`

**revision loop**（返修循环）
- `build_revision_inbox()` 创建 revision Task Card
- revision task_id 格式：`{原task_id}_rev{N}`
- `max_revisions` 耗尽 → manual_review

**run-ledger.py**（生命周期日志）
- 格式：JSONL，每行一条 `lifecycle_event`
- 字段：event_id, task_id, agent_id, run_type, phase, status, started_at, finished_at
- 路径：`~/.claude/teams/{project}/runs/ledger.jsonl`

**task-status.py**（状态查询）
- 读取 `tasks/index.jsonl`
- `latest_by_task()` 取最新记录
- `rollup_rows()` 合并 revision 链
- 支持 `--project` `--index` `--run-ledger` 参数

---

## 4. 路由规则和执行模式判定

### 4.1 能力→Agent 路由表

| 能力 | → Agent |
|------|---------|
| file_modification, script_execution, git_operations | claude |
| code_review, implementation_planning | codex |
| technical_decomposition, analysis, decision_making, strategy_decision | hermes-internal |
| web_research, market_intelligence, competitor_monitoring, news_gathering, source_verification | intelligence |
| creative_direction, visual_design, poster_design, web_visual_design, ui_design, brand_identity | designer |
| desktop_control, app_operation, screenshot, visual_gui_automation, browser_gui_operation, office_document_automation | agent-tars |
| content_writing, planning, document_creation | pirlo |
| review, validation, risk_assessment | ambrosini |

### 4.2 执行模式判定（determine_execution_mode）

```python
def determine_execution_mode(compiled_intent, agent_registry):
    task_type = compiled_intent.get("task_type", "simple")
    preferred = compiled_intent.get("preferred_agent", "hermes-internal")
    risk = compiled_intent.get("risk_level", "low")
    subjectivity = compiled_intent.get("subjectivity_level", "low")

    if risk == "high" and subjectivity == "high":
        mode = "multi-agent"           # 高风险高主观 → 多 Agent 协作
    elif task_type == "multi-agent":
        mode = "multi-agent"
    elif preferred in ("claude", "deepseek-tui"):
        mode = "single-agent"          # 明确指定 → 单 Agent
    else:
        mode = "self"                  # 其他 → 马蒂尼自己处理
```

### 4.3 任务-工具匹配硬规则

三步规则只是兜底，不是主路由。收到任务后先检查是否存在精准匹配的 skill/service/Agent，若存在必须优先调用。典型映射：
- Markdown/文档 → HTML：必须优先使用 html-anything API (:14732)
- 商业方案/展示型内容 → Pirlo
- 代码修改 → Claude/DeepSeek Worker，Codex/Ambrosini 审查
- GUI/浏览器/截图验证 → TARS

---

## 5. 关键配置项

### 5.1 主模型和 Gateway

```yaml
model:
  provider: deepseek
  model: deepseek-v4-pro
  base_url: https://api.deepseek.com

agent:
  max_turns: 90
  gateway_timeout: 900
  restart_drain_timeout: 60
  api_max_retries: 3
  gateway_timeout_warning: 180
  clarify_timeout: 600
  gateway_notify_interval: 120
  image_input_mode: auto
```

### 5.2 委托/并发/深度

```yaml
delegation:
  model: deepseek-v4-flash
  provider: deepseek
  max_concurrent_children: 3
  max_spawn_depth: 1          # 不能嵌套委托
  child_timeout_seconds: 180
  orchestrator_enabled: false  # 不允许编排器模式
  subagent_auto_approve: false
  max_iterations: 150
```

### 5.3 记忆

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 3000      # MEMORY.md 上限
  user_char_limit: 1375        # USER.md 上限
  provider: hindsight
  flush_min_turns: 6
```

### 5.4 压缩和安全

```yaml
compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
  protect_last_n: 20
  hygiene_hard_message_limit: 400

tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: false
  warn_after: { exact_failure: 2, same_tool_failure: 3, idempotent_no_progress: 2 }
  hard_stop_after: { exact_failure: 5, same_tool_failure: 8, idempotent_no_progress: 5 }
```

### 5.5 MCP 服务

| 服务 | 状态 | 路径/命令 | 超时 |
|------|------|----------|------|
| codegraph | ✅ enabled | `codegraph serve --mcp` | 120s |
| openchronicle | ✅ enabled | `http://127.0.0.1:8742/mcp` | 8s |
| context7 | ✅ enabled | `npx @upstash/context7-mcp` | — |
| scrapling-fetch | ✅ enabled | `uvx scrapling-fetch-mcp` | 30s |
| playwright | ✅ enabled | `npx @playwright/mcp` | — |
| github | ✅ enabled | `npx @modelcontextprotocol/server-github` | 120s |
| minimax | ✅ enabled | `uvx minimax-coding-plan-mcp` | — |

### 5.6 工具集（飞书入口）

```yaml
platform_toolsets:
  feishu:
    - hermes-cli      # 完整工具集
    - desktop         # 桌面操作
    - mcp-codegraph   # CodeGraph
```

### 5.7 模型别名

| 别名 | Provider | Model |
|------|----------|-------|
| co / claude_opus | anthropic @ flashapi.top | claude-opus-4-7 |
| cs | anthropic @ flashapi.top | claude-sonnet-4-6 |
| dp / deepseek_pro | deepseek | deepseek-v4-pro |
| df / deepseek_flash | deepseek | deepseek-v4-flash |
| codex_cli | openai-codex | gpt-5.5 |
| tars_gpt54 | custom @ flashapi.top | gpt-5.4 |

---

## 6. 核心目录和关键文件索引

```
~/.hermes/
├── SOUL.md                          # Hermes 身份、边界、哲学
├── config.yaml                      # 主配置（634 行）
├── config/
│   ├── agent-registry.json          # Agent 编制 + 路由规则（927 行）
│   ├── managed-agents.yaml          # Managed Agents 定义（577 行，与 agents.yaml 不同步）
│   ├── models.yaml                  # 模型订阅
│   └── model-subscriptions.yaml     # 模型订阅详情
├── bin/
│   └── hermes-system-doctor.py      # 系统健康诊断（436 行）
├── scripts/                         # v2.8 任务管道
│   ├── compile-task.py              # 意图→任务卡
│   ├── verify-task.py               # outbox 验证
│   ├── dispatch-task.py             # Agent 派遣
│   ├── review-task.py               # 交付审查
│   ├── gate-policy.py               # 策略决策
│   ├── run-ledger.py                # 生命周期日志
│   ├── task-status.py               # 任务状态查询
│   └── opencode-agent.py            # 外部 Codex 审查
├── memories/
│   ├── MEMORY.md                    # 常驻记忆（1811/3000）
│   └── USER.md                      # 用户偏好（551/1375）
├── skills/                          # 77+ skill
│   ├── humanizer/                   # 英文去 AI 味
│   ├── humanizer-zh/                # 中文润色
│   └── hyperframes/                 # 视频生成
├── hermes-agent/                    # Hermes Agent 本体
│   ├── run_agent.py                 # AIAgent 核心循环（~12k LOC）
│   ├── model_tools.py               # 工具编排+发现
│   ├── toolsets.py                  # 工具集定义
│   ├── tools/                       # 150+ 工具实现
│   ├── gateway/                     # 飞书/Telegram/Discord 等平台适配
│   ├── hermes_cli/                  # CLI + 配置
│   └── configs/managed_agents/agents.yaml  # 源码 Agent 定义（10 个 Agent）
└── logs/
    ├── gateway.log
    ├── gateway.error.log
    └── errors.log
```

---

## 7. 已启用与未启用的能力

### 已启用

| 能力 | 说明 |
|------|------|
| 飞书入口 | DM + Home 频道 + 技术频道（3 条绑定了 persona 的频道） |
| 9 个编制 Agent | hermes-internal, claude, deepseek-tui, codex, pirlo, intelligence, designer, tars, ambrosini |
| 7 个 MCP 服务 | codegraph, openchronicle, context7, scrapling-fetch, playwright, github, minimax |
| v2.8 Task Card Pipeline | compile → verify → dispatch → review → gate-policy → revision loop |
| Memory | MEMORY.md + USER.md，hindsight provider |
| Session Search | FTS5 全文搜索 |
| Compression | 0.5 阈值 / 0.2 压缩比 |
| Tool Loop Guardrails | 警告模式（未启用 hard_stop） |
| Checkpoints | 最多 50 个快照 / 500MB |
| Kanban | dispatch_in_gateway: true |
| Cron | 支持 |
| CodeGraph | ~/.hermes 已索引（387 nodes, 369 edges） |
| Claude Code Mailbox | 已启用插件 |
| Image Gen | gpt-image-2-medium |

### 未启用/受限

| 能力 | 状态 | 说明 |
|------|------|------|
| orchestrator_enabled | ❌ | 不允许 Agent 编排器模式 |
| max_spawn_depth | 1 | 不能嵌套委托 |
| subagent_auto_approve | ❌ | 子 Agent 操作需确认 |
| Tool Search | ❌ 未合入 | 在 `origin/main`，当前分支滞后 |
| hyperframes | 未安装 | 已评估，等待实际需求 |
| opencode Agent | ⚠️ 仅 agents.yaml | agent-registry.json 中缺失 |
| hard_stop_enabled | ❌ | 工具循环仅警告，不硬停 |

---

## 8. 最近一次系统诊断（2026-06-01T22:12 CST）

### 通过项

| 检查 | 结果 |
|------|------|
| Core processes | ✅ gateway, dashboard:9119, openchronicle, codegraph_mcp 全部运行 |
| Local ports | ✅ 8642(API), 9119(dashboard), 8742(openchronicle), 7890(clash) 全部通 |
| API server auth | ✅ no-key=401, keyed=200 |
| Built-in memory | ✅ MEMORY.md 1811/3000, USER.md 551/1375 |
| Agent registry coverage | ✅ registry 和 agents.yaml 各 10 个 Agent，ID 一致 |
| Agent registry consistency | ✅ 无字段不匹配 |
| Agent model_refs | ✅ 所有 model_ref 值有效且未弃用 |

### 告警项

| 检查 | 结果 |
|------|------|
| Managed agents mirror | ❌ **FAIL**: source=10 agents; mirror=9 agents; missing_in_mirror=['opencode'] |
| Historical log signals | ⚠️ STALE: opencode_404=1, api_key_warning=1（历史信号，不代表当前故障） |
| Hermes config git state | ⚠️ WARN: 27 changed/untracked entries |

### 诊断结论

**FAIL** — managed agents mirror 不同步。`hermes-agent/configs/managed_agents/agents.yaml` 有 10 个 Agent，`config/managed-agents.yaml` 只有 9 个。缺少 `opencode`。

---

## 9. 已知问题和常见失败模式

| 问题 | 分类 | 状态 |
|------|------|------|
| Managed agents mirror drift（opencode 缺失） | 配置漂移 | 🔴 当前活跃 |
| 27 个未提交的 git 变更 | 配置管理 | 🟡 待处理 |
| M1 8GB 内存偏紧（渲染/长对话压力） | 硬件限制 | 🟡 持续关注 |
| Claude Code sandbox-exec 阻止 Chrome 子进程 | 平台限制 | 🟡 已知，无修复 |
| opencode_404 历史信号 | 历史日志 | ⚪ 仅记录，非当前故障 |
| Tool Search feature 未合入当前分支 | 版本滞后 | 🔵 等待下次 update |
| agent-registry.json skills 数组未完全填充（部分 Agent 缺 skills 声明） | 配置不完整 | 🟡 低优先级 |
