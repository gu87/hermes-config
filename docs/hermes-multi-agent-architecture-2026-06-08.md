# Hermes 多 Agent 体系全景图

> 生成日期: 2026-06-08 | CodeGraph 索引: 81,732 nodes, 198,181 edges

---

## 一、体系概览

你的多 Agent 体系由 **三层架构 + 两条调度链** 组成：

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层                                │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ CLI / TUI  │  │  Gateway  │  │  Desktop  │               │
│  │ hermes -z  │  │ 飞书/微信  │  │ Electron  │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │              │              │                      │
├────────┼──────────────┼──────────────┼──────────────────────┤
│        ▼              ▼              ▼                      │
│              Hermes Agent (主 Agent)                         │
│        ┌─────────────────┬──────────────────┐               │
│        │ delegate_task() │  kanban dispatch  │              │
│        │ (实时委托)       │  (任务队列调度)    │              │
│        └────────┬────────┴────────┬─────────┘              │
├─────────────────┼─────────────────┼─────────────────────────┤
│                 ▼                 ▼                          │
│           子 Agent 执行层                                      │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐         │
│  │Claude │ │DS-TUI │ │Codex  │ │Hermes │ │Agent  │ ...     │
│  │ 主程   │ │ 快工   │ │审查   │ │技术   │ │TARS   │         │
│  └───┬───┘ └───────┘ └───────┘ └───────┘ └───────┘         │
│      │       (9 个注册 Agent, 每种有独立模型/工具/权限)        │
│      │                                                       │
├──────┼───────────────────────────────────────────────────────┤
│      ▼              Gate / Review 层                          │
│  ┌──────┐  ┌───────┐  ┌────────┐  ┌────────┐               │
│  │Verify│→ │Review │→ │ Gate   │→ │Policy  │               │
│  │ 结构  │  │ 语义  │  │ 决策   │  │ 策略   │               │
│  └──────┘  └───────┘  └───┬────┘  └────────┘               │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │  approved   │                           │
│                    │ revision_   │                           │
│                    │ needed(返工) │                           │
│                    │ rejected    │                           │
│                    └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、Agent 注册表（Agent Registry）

### 2.1 9 个注册 Agent

| ID | 中文名 | 角色 | 运行时 | 主模型 | 权限 | 风险等级 |
|----|--------|------|--------|--------|------|----------|
| **claude** | Claude 主程执行官 | lead_implementer | Claude Code CLI | Sonnet → Opus | ask | R1-R3 |
| **deepseek-tui** | DeepSeek 低成本快工 | fast_worker | DeepSeek TUI CLI | Flash → Pro | ask | R0-R2 |
| **codex** | Codex 代码审查官 | principal_engineer | Codex CLI | codex_cli | read_only | R0-R4 |
| **hermes-internal** | Hermes 技术翻译官 | internal_reasoner | Hermes (本地) | GLM5.1 → DS Pro | read_only | R0-R3 |
| **intelligence** | Intelligence 情报研究员 | research_analyst | Hermes (本地) | Kimi2.6 → Qwen3.7 | ask | R0-R2 |
| **pirlo** | Pirlo 商业策划师 | planning_strategist | Hermes (本地) | Kimi2.6 → MiniMax | read_only | R0-R2 |
| **designer** | Designer 视觉设计师 | visual_designer | Hermes (本地) | Kimi2.6 → Qwen3.7 | ask | R0-R2 |
| **agent-tars** | TARS 桌面操作员 | desktop_operator | Hermes (本地) | Mimo2.5 → TARS | ask | R0-R2 |
| **ambrosini** | Ambrosini 质量门卫 | quality_gate | Hermes (本地) | GLM5.1 → DS Pro | read_only | R0-R4 |
| **opencode** | OpenCode 协作执行员 | external_collaboration_worker | OpenCode CLI | DS Flash → Pro | ask | R0-R2 |

### 2.2 Agent 分组（按角色）

```
🔧 执行层 (实施)
├── claude         ← 主实现，Claude Code CLI，Sonnet/Opus
├── deepseek-tui   ← 低成本小改/测试，DeepSeek TUI
└── opencode       ← 窄范围复核/失败样本采集

🧠 分析层 (决策)
├── hermes-internal ← 技术翻译官：需求拆解、策略判断
├── codex           ← 架构审查、代码审查
└── ambrosini       ← 高风险验收、最终质量门

🎨 创作层
├── designer        ← 海报/UI/品牌视觉
├── pirlo           ← 商业方案、PPT 提案
└── intelligence    ← 调研、竞品、资料收集

🖥️ 操作层
└── agent-tars      ← 桌面/GUI/浏览器操作
```

### 2.3 能力路由表（Capability Routes）

```yaml
# 每个 capability 自动路由到对应 agent
file_modification       → claude
script_execution        → claude
code_review             → codex
implementation_planning → codex
technical_decomposition → hermes-internal
web_research            → intelligence
creative_direction      → designer
desktop_control         → agent-tars
review                  → ambrosini
content_writing         → pirlo
```

---

## 三、两条调度链

### 3.1 调度链 A：实时委托（delegate_task）

**入口**: 主 Agent 工具调用 `delegate_task(agent_id="claude", goal="...", context="...")`

**流程**:
```
用户对话 → 主 Agent 决定委托 → delegate_task tool
    │
    ├── 选择 Agent (agent_id or auto-routing)
    ├── 创建子 AIAgent 实例
    │   ├── 隔离上下文（不继承父 agent 历史）
    │   ├── 限制工具集（block delegate/memory/send_message/execute_code）
    │   ├── 设置同意策略（auto-deny 或 auto-approve）
    │   └── 注入目标 + context
    │
    ├── ThreadPoolExecutor 执行（父 agent 阻塞等待）
    │   └── 子 agent 运行完整的 conversation_loop
    │
    └── 返回结果给父 agent（只有 summary，不展示子 agent 的中间过程）
```

**关键约束**:
- 最大并发子 agent：3（可配置）
- 最大嵌套深度：1（默认不允许多级委托）
- 被禁止的子 agent 工具：`delegate_task` `clarify` `memory` `send_message` `execute_code`
- 子 agent 运行在独立线程，通过 `threading.local()` 隔离 terminal/approval

**活跃状态追踪** (`tools/delegate_tool.py`):
```python
_active_subagents: Dict[str, Dict]  # subagent_id → {goal, model, status, ...}
_subagent_output_tail: List[Dict]   # 最近 N 个工具调用结果
```

### 3.2 调度链 B：看板调度（Kanban Dispatch）

**入口**: `hermes_cli/kanban_db.py` + 9 个 pipeline 脚本

**流程**:
```
kanban_dispatcher (定时 tick)
    │
    ├── 1. 扫描 kanban.db → 找到 "ready" 状态的任务
    ├── 2. CAS 原子抢占 (compare-and-swap on claim_lock)
    ├── 3. 启动 worker: hermes -p <profile> -z "<prompt>"
    │       注入: HERMES_KANBAN_TASK / HERMES_KANBAN_BOARD / HERMES_KANBAN_DB
    ├── 4. Worker 子进程执行 → 写入结果
    └── 5. Dispatcher 退出 → 下次 tick 释放

支持: BOARD (多项目隔离) + PROFILE (多角色隔离)
```

### 3.3 调度链 C：Task Card Pipeline（v2.8）

这是你在 `~/.hermes/scripts/` 下的 9 个脚本组成的 CI/CD 式流水线：

```
用户请求
  │
  ├── [1] compile-task.py     → 组装 Task Card (意图 + 记忆库 + Agent Registry)
  │
  ├── [2] dispatch-task.py    → 选择 agent，调用hermes -z 委派任务
  │        └── hermes -z → conversation_loop → write outbox.json
  │
  ├── [3] verify-task.py      → 结构验收 (JSON 格式/字段/文件存在性/changed_files 范围)
  │        ├── needs_human_review
  │        └── pass → 进入 review
  │
  ├── [4] review-task.py      → 语义验收 (goal 对齐/scope/evidence/acceptance_criteria)
  │
  ├── [5] gate-policy.py      → 策略决策 (auto_revision / hard_stop / timeout)
  │
  └── [6] run-task-gate.py    → 总闸: 协调 verify + review + policy → 最终决策
           ├── approved        → ✅
           ├── revision_needed → 生成 revision inbox → 返回步骤 2
           └── rejected        → ❌

辅助脚本:
  [7] task-status.py   → 查看所有任务状态快照
  [8] run-ledger.py    → 追加式运行账本 (JSONL lifecycle events)
  [9] opencode-agent.py → OpenCode CLI 适配器
```

**文件目录结构**:
```
~/.claude/teams/<project>/
├── inbox/               ← 待处理 Task Card (JSON)
├── outbox/               ← Agent 输出的结果文件
├── review/               ← Gate 审查记录
├── tasks/
│   └── index.jsonl       ← 任务状态快照索引
├── runs/
│   └── ledger.jsonl      ← 全生命周期运行账本
└── events.jsonl          ← 事件日志
```

---

## 四、Kanban 看板调度系统

### 4.1 架构

```
Kanban DB (SQLite, WAL mode)
├── tasks              ← 任务卡片 (status/priority/claim_lock/worker_id)
├── task_links         ← 任务依赖关系
├── task_comments      ← 任务评论 (含 swarm blackboard)
├── task_events        ← 任务事件 (status 变更审计)
├── workspaces/        ← 每个任务的 git worktree
└── logs/              ← 每个任务的运行日志

Dispatcher (独立进程)
├── 轮询 kanban.db → 找到 'ready' 任务
├── CAS claim → 抢占任务
├── 启动 worker 子进程
│    注入环境变量:
│    - HERMES_KANBAN_TASK
│    - HERMES_KANBAN_BOARD
│    - HERMES_KANBAN_DB
│    - HERMES_KANBAN_WORKSPACE
└── worker 退出 → 下次 tick 释放
```

### 4.2 Kanban Swarm（蜂群并行）

```
planning_root (completed immediately)
  ├─ worker A (ready)
  ├─ worker B (ready)
  ├─ worker C (ready)
  └─ verifier (todo → 等 A/B/C 完成)
       └─ synthesizer (todo → 等 verifier 完成)
```

- 轻量级实现：通过 `task_comments` 中的结构化 JSON 作为共享黑板
- 不需要新的调度器或服务
- 支持并行 worker + 串行依赖

### 4.3 多项目隔离

```
~/.hermes/kanban/
├── kanban.db                    ← default 看板
├── boards/
│   ├── atm10-server/            ← 独立看板
│   │   ├── kanban.db
│   │   ├── workspaces/
│   │   └── logs/
│   └── staam/                   ← 另一个独立看板
│       └── ...
└── current                      ← 当前活跃看板名
```

---

## 五、Gateway 多会话 Agent 管理

Gateway 进程内维护一个 Agent 缓存池：

```python
# gateway/run.py
_AGENT_CACHE_MAX_SIZE = 128        # 最多缓存 128 个 Agent 实例
_AGENT_CACHE_IDLE_TTL_SECS = 3600  # 1 小时空闲后驱逐

_agent_cache: OrderedDict[str, tuple]  # LRU 有序字典
# key = session_key (平台+用户)
# value = (AIAgent, last_activity_ts)
```

**生命周期**:
- 每新消息 → 从缓存获取或创建 AIAgent
- 对话结束 → 保留在缓存（LRU 淘汰 + 1h TTL 驱逐）
- Gateway 重启 → 缓存清空，但不影响已有对话（对话通过 Sessions DB 持久化）

**多平台并发**:
- 同一 Gateway 进程同时处理飞书/微信/Telegram/Slack 等所有平台的会话
- 每个会话有独立的 SessionKey → 独立的 Agent 实例
- 最多 128 个并发会话缓存

---

## 六、桌面端 Agent 监控

### 6.1 AgentsView 面板

```
AgentsView (apps/desktop/src/app/agents/index.tsx)
├── Tab: Roster        ← Agent Registry 静态列表
├── Tab: TaskFlow      ← 子 Agent 树（实时流式更新）
├── Tab: Running       ← 当前运行中子 Agent
└── Tab: System        ← Gateway 状态/版本/活跃会话数
```

### 6.2 子 Agent 状态流 (`subagents.ts`)

```
Gateway RPC 事件推送:
├── subagent.queued       → 入队
├── subagent.running      → 开始运行
├── subagent.progress     → 进度更新
├── subagent.thinking     → 思考流
├── subagent.completed    → 完成
├── subagent.failed       → 失败
└── subagent.interrupted  → 被中断

渲染:
├── buildSubagentTree()   → 构建父子树
├── statusGlyph()         → 状态图标 (● spinner / ✗ error / ✓ done)
├── stream 预览           → 最近 24 条流式条目
└── 文件读写列表           → filesRead / filesWritten
```

---

## 七、Agent 配置体系

### 7.1 配置源

```
agent-registry.json          ← 生成的 JSON 快照（9 agent）
  ↑
configs/managed_agents/agents.yaml  ← 主配置（YAML）
  ↑
managed-agents.yaml          ← 简化版（agent_id/name/tools/skills/risk）
  ↑
subagent_profile             ← 每个 agent 的运行时参数
  ├── model_ref + model_strategy (主模型 + failover 链)
  ├── toolsets                (file/terminal/git/web/browser/image_gen)
  ├── blocked_tools           (delegate/memory/send_message 等禁止工具)
  ├── permission_mode         (read_only / ask)
  ├── isolation               (readonly / shared)
  ├── skills                  (注入的 skill bundle)
  └── runtime                 (hermes / claude_code_cli / deepseek_tui_cli / codex_cli)
```

### 7.2 路由规则 (`managed-agents.yaml`)

```yaml
routing:
  # 按能力自动路由
  capability_routes:
    code_edit: claude
    architecture_review: codex
    web_research: intelligence
    visual_design: designer
    ...

  # 按场景规则路由
  rules:
    - when: {task_category: architecture_change}
      mode: pipeline
      agents: [hermes-internal, codex, claude, deepseek-tui]
      require_gate: review

    - when: {risk_level: R3}
      mode: pipeline
      agents: [hermes-internal, codex, claude, deepseek-tui]

    - when: {risk_level: R4}
      mode: pipeline
      agents: [hermes-internal, codex, claude, ambrosini]
      requires_human_approval: true
```

### 7.3 客户-项目映射

`config/client_directory_map.json` 维护客户名到本地项目目录的映射：
```json
{"蒙牛": "~/Documents/懂球帝工作/蒙牛", "百威": "~/Documents/.../百威", ...}
```
用于 Kanban dispatch 时自动切换到对应项目目录。

---

## 八、完整协作流程示例

```
用户: "帮我在 X 项目里加一个新 API 端点"
  │
  ├── [1] 意图编译 (主 Agent 判断)
  │      category=feature, risk=R2, preferred=claude
  │
  ├── [2] compile-task.py 组装 Task Card
  │      ├── goal, scope, allowed_files, acceptance_criteria
  │      └── execution_plan: mode=single-agent, primary=claude
  │
  ├── [3] dispatch-task.py
  │      └── hermes -z "delegate_task(agent_id=claude, goal=..., context=...)"
  │
  ├── [4] Claude Code CLI 子进程执行
  │      ├── 读取代码 → 实现 → 写 outbox.json
  │      └── 子进程退出
  │
  ├── [5] verify-task.py 结构验证
  │      ├── JSON 合法 ✓
  │      ├── task_id 匹配 ✓
  │      ├── changed_files 在 allowed_files 范围内 ✓
  │      └── pass → 进入 review
  │
  ├── [6] review-task.py 语义验证
  │      ├── goal 对齐 ✓
  │      ├── evidence 存在 ✓
  │      ├── must_avoid 符合 ✓
  │      └── approved
  │
  ├── [7] gate-policy.py
  │      └── auto_revision_allowed: true, decision: approved
  │
  └── [8] run-task-gate.py → ✅ APPROVED
```

---

## 九、关键文件索引

| 想找什么 | 文件 |
|----------|------|
| Agent 注册表 | `config/agent-registry.json` |
| Agent 配置 | `config/managed-agents.yaml` |
| 委托工具 (delegate_task) | `tools/delegate_tool.py` |
| Task Card 组装 | `scripts/compile-task.py` |
| 任务派发 | `scripts/dispatch-task.py` |
| 结构验收 | `scripts/verify-task.py` |
| 语义验收 | `scripts/review-task.py` |
| Gate 策略 | `scripts/gate-policy.py` |
| Gate 总闸 | `scripts/run-task-gate.py` |
| 运行账本 | `scripts/run-ledger.py` |
| 任务状态 | `scripts/task-status.py` |
| OpenCode 适配 | `scripts/opencode-agent.py` |
| Kanban 数据库 | `hermes_cli/kanban_db.py` |
| Kanban CLI | `hermes_cli/kanban.py` |
| Kanban Swarm | `hermes_cli/kanban_swarm.py` |
| Gateway Agent 缓存 | `gateway/run.py` (AGENT_CACHE) |
| 桌面监控面板 | `apps/desktop/src/app/agents/index.tsx` |
| 子 Agent 状态 | `apps/desktop/src/store/subagents.ts` |
| 客户-项目映射 | `config/client_directory_map.json` |
