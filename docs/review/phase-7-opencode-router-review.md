# Phase 7 半自动 Executor Router Review

> 复核 Hermes Desktop v0.5 半自动 Executor Router 的设计（`docs/architecture/semi-auto-executor-router.md`）与实现（`hermes-agent/executors/router.py` · `cli.py` · `types.py` · `registry.py` · `opencode_adapter.py`），重点是 opencode 作为 executor 候选的定位与推荐边界。

复核日期：2026-06-04
复核范围：
- `docs/architecture/semi-auto-executor-router.md`（设计）
- `docs/architecture/agent-adapter-layer.md`（adapter 层）
- `hermes-agent/executors/router.py`（v0.5 关键词路由实现，301 行）
- `hermes-agent/executors/cli.py`（`_cmd_route` + `--accept`/`--executor` flag）
- `hermes-agent/executors/types.py`（`RouterRecommendation` / `TaskCreateContext` / `ExecutorManifest`）
- `hermes-agent/executors/registry.py`（5 个默认 manifest）
- `hermes-agent/executors/opencode_adapter.py`（OpenCodeAdapter 子进程包装）

不修改业务代码。

---

## 一、复核结论速览

| 维度 | 评价 |
|---|---|
| opencode 作为 executor 候选定位 | ✅ 正确：5 个 executor 之一，不替代 Hermes Desktop 控制面 |
| opencode 推荐的任务边界 | ⚠️ 偏宽：keyword 集合 "local/offline/prototype/experiment" 触发面太大 |
| Hermes 内部任务优先外推 | 🔴 **P0 倒挂**：设计要求最高优先级，实现 priority=5（最低） |
| Executor 不可用时降级 | ⚠️ 行为正确，但 `unavailableReason` / `fallback` 字段缺失 |
| 推荐理由透明度 | ⚠️ 一句话模板，不展示命中了哪些 keyword |
| 用户覆盖推荐 | ✅ CLI / 数据层都支持 override；不持久化到 DB |
| 自动执行风险 | ⚠️ CLI 提供 `--accept` 自动接受 flag，与"必须用户确认"语义有偏差 |
| 绕过 worktree / diff review | ✅ Router 纯数据；不创建 run、不创建 worktree |
| 设计与实现一致性 | 🔴 多处 schema/语义不一致（详见 §4.3） |

---

## 二、同意的规则

### 2.1 opencode 是 executor 候选，不是 Hermes Desktop 替代品 ✅

设计 §1 明确："用户创建 Task 后，Router 根据任务内容**推荐合适的 executor**"，"Router 不自动发起 run"；架构图（`agent-adapter-layer.md` §9）把 opencode 列为 `OpenCodeAdapter ──► opencode CLI 子进程`，与 Claude/Codex/Hermes-Local/DeepSeek 并列。OpenCodeAdapter 也只实现 `AgentExecutorAdapter` Protocol，不直接操作 Hermes 内部状态（session、memory、kanban、events）。**这条边界守得对**，Hermes Desktop 仍是控制面，opencode 只是可选的后端之一。

### 2.2 opencode 推荐为「验证 / 备选实现 / 本地实验」后端 ✅

设计 §四 表格 + roadmap Phase 7 验收条都对齐把 opencode 定位成「轻量级本地二审 / 备选实现 / 廉价 QA」角色。OpenCodeAdapter 的 `default_model="deepseek-v4-flash"` + `capabilities.review_gate=False` + `ui_fidelity="full"` 体现"廉价、可观察、不卡 review"的定位。和 DeepSeek TUI（`ui_fidelity="low"`，仅 log）的分工也清楚：**opencode 是结构化的、DeepSeek TUI 是非结构化的**。

### 2.3 Router 输出纯数据，不触发 run 创建 ✅

`router.route(ctx)` 只返回 `RouterRecommendation`，没有 asyncio / subprocess / DB 副作用。CLI `_cmd_route` 也只 print + 写 JSON（不调 `createRun`）。这条不变，**是整个半自动设计的根本前提**。

### 2.4 用户覆盖推荐的入口齐备 ✅

- `TaskCreateContext` → `RouterRecommendation` → `args.executor` override → `rec.override=True, source="manual"`
- 交互式 prompt：`[推荐/No/manual]` 三选一
- `RouterRecommendation.override: bool` 字段记录"是否被用户覆盖"
- 不持久化（"session 内存，不写 DB"符合"不悄悄学习"的约束）

### 2.5 Router 不绕过 worktree / diff review ✅

`RouterRecommendation` 不含 worktree 决策字段。`AgentExecutorAdapter.start()` 由 Orchestrator 调，Orchestrator 在 v0.4 已规定 `WorktreeAllocation` 状态机。Router 只产生 `recommended_executor`，**无法**直接 `adapter.start`。这条边界守住了。

---

## 三、不合理的规则

### 3.1 🔴 P0 Hermes 内部任务的 priority 实现倒挂

**设计意图**（`semi-auto-executor-router.md` §四"规则匹配顺序"）：

> 1. 精确匹配 Hermes 内部关键词 → `hermes-local`（**最高优先级**，避免用外部 executor 改 Hermes 自身）

**实现现状**（`router.py:54-116`）：

```python
RouteRule(executor="claude-code",  priority=10, ...),
RouteRule(executor="codex-cli",    priority=9,  ...),
RouteRule(executor="opencode",     priority=8,  ...),
RouteRule(executor="deepseek-tui", priority=7,  ...),
RouteRule(executor="hermes-local", priority=5,  confidence=0.82, ...),  # ← 最低
```

而且**主排序是 combined score，不是 priority**：

```python
combined = text_score * rule.confidence
scored.sort(key=lambda x: (-x[0], -x[1].priority))   # x[0] 是 combined score
```

### 实证：用真实 router 跑 18 个 prompt 验证

```
'review the hermes adapter design'   -> claude-code   conf=0.31   ← 设计要求 hermes-local
'refactor the hermes gateway'        -> hermes-local  conf=0.31
'build a local prototype for hermes'-> opencode      conf=0.31   ← 设计要求 hermes-local
'implement an offline backup feature'-> opencode      conf=0.31   ← 设计要求 codex
'experiment with new feature for hermes' -> opencode  conf=0.28   ← 设计要求 hermes-local
```

具体评分细节（手工重现算法）：

| prompt | claude combined | codex combined | hermes combined | 胜者 |
|---|---|---|---|---|
| `review the hermes adapter design` | **0.312** | 0 | 0.306 | **claude** ❌ |
| `refactor the hermes gateway` | 0 | 0.290 | **0.306** | hermes ✅（偶然） |
| `migrate the hermes dispatcher` | 0 | 0.290 | **0.306** | hermes ✅（偶然） |
| `design a new internal admin tool` | 0 | 0 | **0.306** | hermes ✅（偶然） |

**根因**：claude-code 命中 "review" 的 combined（0.312）压过 hermes-local 命中 "hermes"+ "adapter" 的 combined（0.306）。priority 只在 combined score 相等时做 tiebreaker，对排序结果无实际影响。

**风险**：

1. claude-code 改 `hermes/agent/`、`hermes/executors/` 等 Hermes 内部代码——绕过 design 第 1 条"避免用外部 executor 改 Hermes 自身"
2. Hermes 内部任务用外部 executor → 可能改完不被 review_gate 拦截（`hermes-local.review_gate=True` 而 `claude-code.review_gate=False`，见 `registry.py:142-145, 158-161`）
3. 现状能跑通仅是 confidence 数值巧合，**任何 keyword 调整都会破坏**

### 3.2 🔴 P0 opencode 关键词过宽，造成 over-recommend

`router.py:79-90` 的 opencode 规则：

```python
keywords=[
    "opencode", "open source", "open-source", "oss",
    "validate", "validation", "backup", "alternative",
    "compare", "comparison", "experiment", "prototype",
    "local", "offline", "self-hosted",     # ← 这五个过宽
],
```

实证：

| prompt | 命中 keyword | 错误推荐 opencode |
|---|---|---|
| `build a local prototype for hermes adapter` | "local" + "prototype" | ❌ 应该是 hermes-local |
| `implement an offline backup feature` | "offline" | ❌ 应该是 codex |
| `experiment with new feature for hermes` | "experiment" | ❌ 应该是 hermes-local |
| `describe how to test local performance` | "local" | ⚠️ 边界（任务含糊） |
| `review the local opencode adapter` | "opencode" + "local" | ✅ 正确（虽然靠"opencode"胜出） |

**问题不是 opencode 不该出现，是触发面过宽导致"任何带 local/实验/原型的任务都被甩给 opencode"，掩盖了真正的意图。**

### 3.3 🟡 P1 关键词碰撞：`implement` 击败 `alternative implementation`

`router.py` 关键词表里：

- `codex-cli` 包含 `"implement", "implementation"`
- `opencode` 包含 `"alternative"` 但**不包含** `"alternative implementation"` 短语

实证 `alternative implementation of codex adapter` → opencode ✅（侥幸）
但 `implement alternative auth flow`：

- codex: 命中 "implement" → combined ≈ 0.295
- opencode: 命中 "alternative" → combined ≈ 0.278

codex 胜。**用户问"备选实现"被甩给 codex，是设计意图的反向错误**。

### 3.4 🟡 P1 `verify` 不在 opencode 关键词中

设计 §四 用 "验证"（validate）作为 opencode 触发词，但实现遗漏了常见同义词 `verify`、`test`、`check`、`sanity-check`。实证 `verify that opencode works offline` → opencode ✅ 是因为 "opencode" 触发，不是 "verify"。

**结果**：用户写"verify X with opencode"时靠"opencode"字面命中，而不是靠"verifying this"语义命中。这对"备选/二审"场景是脆弱的。

### 3.5 🟡 P1 推荐理由是黑盒：不展示命中了哪些 keyword

```python
reason_template="Task involves open-source agent validation/alternative implementation — OpenCode is a good fit"
```

`reason` 是单一固定字符串模板，不说明"因为命中 'opencode' 和 'offline'"，也不说明 confidence 是怎么算的。CLI 输出也没有"理由来源"字段。

对用户的影响：
- 不知道是 keyword 命中还是 fallback，无法判断"为什么是这个"
- 用户难以学习"我下次怎么描述会让 router 更准"
- 调试/审计困难（没有 keyword trace）

### 3.6 🟡 P1 CLI `--accept` flag 与"必须用户确认"语义有偏差

`cli.py:325`：

```python
route_p.add_argument("--accept", "-a", help="Auto-accept the recommendation (skip user confirmation)")
```

设计 §六 明确："必须由用户确认"、"用户选择始终优先于系统推荐"。CLI 提供 `--accept` 本意是 scripting/CI，但代码里没有限制这个 flag 的使用上下文：

- 没有 log 记录"通过 --accept 跳过确认"
- 没有任何模块强制 `--accept` 必须配合 `source="cli_auto_accept"` 写入 run metadata
- desktop UI 是否会复用这个 flag 还不确定

**风险**：如果 desktop 后续 wire 进来一个"记住上次选择"功能，可能无意中调用 `--accept` 把"用户已确认" 静默写进 run history。

### 3.7 🟡 P1 备选列表无 per-executor 原因 / 可用性

设计 §二 schema：

```typescript
interface AlternativeExecutor {
  executor: ExecutorType
  reason: string
  available: boolean
}
```

实现 `types.py:244-252`：

```python
@dataclass
class RouterRecommendation:
    alternatives: List[ExecutorId] = field(default_factory=list)   # 只有 id
```

用户看到 "Alternatives: claude-code, hermes-local" 时：
- 不知道这两个分别"凭什么"是备选
- 不知道 claude-code 当前是否健康
- 切换时 `reason` 文字不会更新（设计 §六明说"切换时 reason 文字更新"）

### 3.8 🟡 P1 `RouterRecommendation` 缺 `unavailableReason` / `fallback` 字段

设计 §二 schema：

```typescript
unavailableReason?: string
fallback?: ExecutorType
```

实现 `types.py:244-252`：

```python
recommended_executor: ExecutorId
confidence: float
reason: str
alternatives: List[ExecutorId]
source: str
override: bool
# 缺：unavailable_reason, fallback
```

`router.py:235-256` 虽然处理了"推荐 executor 不可用 → 降级到备选"的逻辑，但只把原因拼到 `reason` 字符串里，没有结构化字段。调用方无法直接 query "这个推荐是否被降级过"。

### 3.9 🟡 P1 `confidence` 类型与设计不一致

设计：`confidence: 'high' | 'medium' | 'low'`
实现：`confidence: float`（0.0–1.0）
CLI：`f"{rec.confidence:.0%}"`（显示成百分比）

带来的具体问题：
- 设计说的"fallback 应该是 low"，实现给 fallback 0.40（按 design 阈值是 medium）
- 没有枚举 → UI 没法做"low → 显式提示用户" / "high → 默认接受" 不同展示
- 阈值分散在 router.py 三个地方（0.3、0.4、0.70、0.82、0.85、0.88、0.90），没有常量集中

### 3.10 🟢 P2 fallback 顺序与设计不一致

- 设计 §四："无匹配 → `claude-code`（默认 fallback，confidence: low）"
- 实现 `_FALLBACK_ORDER = ["codex-cli", "claude-code", "opencode", "hermes-local", "deepseek-tui"]`

codex-cli 排第一，与设计不一致。同时实现用 `codex-cli` 这个 id，registry 用 `codex`（`registry.py:166`），类型注释用 `codex`（`types.py:43`）——**id 命名不统一**。这个 id 不一致在 router 自身可能不影响（fallback 列表里的字符串不会和 manifest 对上），但调用方 `registry.get("codex-cli")` 会 KeyError。

### 3.11 🟢 P2 router 完全没用到 `TaskCreateContext.prefer_worktree`

`types.py:262` 字段存在，`router.py` 整文件 grep 不到 `prefer_worktree` 引用。`project_path` 字段同样未使用。**router 的输入维度比设计 §七描述的窄**：实际只用了 `title` + `goal` 文本，丢了结构化 context。

---

## 四、建议新增的规则

### 4.1 新增 M1（必须）：Hermes-internal 短路规则

在 router 入口处（`route()` 方法第一行）加一个**先于所有 RouteRule 评估的硬短路**：

```python
HERMES_INTERNAL_INDICATORS = [
    "hermes/", "hermes_agent/", "hermes-agent/",
    "/hermes/core", "/hermes/executors", "/hermes/hermes_state",
    ".hermes/config.yaml", ".hermes/managed-agents",
]

def _is_hermes_internal(ctx: TaskCreateContext) -> bool:
    text = f"{ctx.title} {ctx.goal} {ctx.project_path or ''}"
    return any(ind in text for ind in HERMES_INTERNAL_INDICATORS)
```

命中即强制推荐 `hermes-local`，无论 keyword 评分如何。理由模板固定为："任务涉及 Hermes 自身源码/配置，必须由 hermes-local 执行以避免外部 executor 改 review gate 看不到的文件"。

**这是修 §3.1 的根本方案**——不能依赖 priority / confidence 数值巧合。

### 4.2 新增 M2：opencode 关键词收紧 + 增补

**移除**（过宽）：
- `"local"` — 几乎所有任务都说 "local"
- `"offline"` — 同上
- `"self-hosted"` — 极少用
- `"prototype"` — 与 codex 的 "implement" 冲突
- `"experiment"` — 同上

**保留**（语义准确）：
- `"opencode"`, `"open source"`, `"open-source"`, `"oss"`
- `"validate"`, `"validation"`
- `"backup"`, `"alternative"`, `"compare"`, `"comparison"`

**增补**（设计遗漏）：
- `"verify"`, `"test"`, `"check"`, `"sanity"`, `"smoke"`, `"QA"`

**新增子规则**（避免与 codex 碰撞）：

```python
# 短语优先：把 "alternative implementation" 作为整体关键字
RouteRule(
    executor="opencode",
    keywords=[
        "opencode", "open source", "open-source", "oss",
        "validate", "validation", "verify", "sanity", "smoke", "QA",
        "backup", "alternative implementation", "alternative approach",
        "compare", "comparison", "second opinion", "second pair of eyes",
    ],
    ...
)
```

加 `keyword_match_phrase` 标记：用 `re.search(r"\balternative\s+(implementation|approach)\b", text)` 而非简单 substring。

### 4.3 新增 M3：reason 字段必须包含 keyword trace

```python
@dataclass
class RouterRecommendation:
    recommended_executor: ExecutorId
    confidence: float
    reason: str
    matched_keywords: List[str] = field(default_factory=list)   # ← 新增
    scoring_detail: str = ""                                     # ← 新增，例如 "3/15 keywords matched, base=0.30, scaled=0.39"
    alternatives: List[AlternativeExecutor] = field(default_factory=list)  # ← 改为结构化
    unavailable_reason: Optional[str] = None                     # ← 新增
    fallback_executor: Optional[ExecutorId] = None               # ← 新增
    source: str = "keyword"
    override: bool = False
```

UI 展示："推荐 opencode（高置信度）｜命中关键词：opencode, validate ｜评分：3/15 keyword, base 0.30, scaled 0.39"。

### 4.4 新增 M4：confidence 改回 design 定义的枚举

```python
class Confidence(str, Enum):
    HIGH = "high"      # combined >= 0.7  或 命中 ≥ 2 keyword 且任务范围明确
    MEDIUM = "medium"  # combined >= 0.4
    LOW = "low"        # fallback 或推荐不可用

@dataclass
class RouterRecommendation:
    confidence: Confidence
    confidence_score: float   # 同时保留原始 0-1 分值，供未来 LLM routing 参考
```

UI 按 enum 分级：
- `high` → 默认接受（仍需用户点确认）
- `medium` → 推荐 + "是否考虑 X 备选"
- `low` → "无法确定，请手动选择"

### 4.5 新增 M5：硬约束（绝不推荐）

```python
# 这些条件命中时，router 不返回任何推荐，要求用户手动选
HARD_BLOCK_CONDITIONS = [
    ("prompt", r"(?i)\bdelete\s+(all|everything)\b"),       # 模糊删除
    ("prompt", r"(?i)\breset\s+(all|state|db)\b"),          # 模糊重置
    ("prompt", r"(?i)\bdrop\s+(table|database)\b"),
    ("prompt", r"(?i)\bforce\s+push\s+(to\s+)?(main|master)\b"),
    ("prompt", r"(?i)\brm\s+-rf\b"),
    ("prompt", r"(?i)\bsend\s+.*\bto\s+(everyone|all)\b"),
]
```

命中任一 → 返回 `RouterRecommendation(recommended_executor="", confidence=Confidence.LOW, reason="检测到潜在破坏性操作，请手动选择 executor 并人工 review prompt")`。

**这是 v0.5 缺失的安全网**，比 §3.6 的 `--accept` 问题更优先。

### 4.6 新增 M6：router 必须在 orchestrator 链路下游

明确 router 在 orchestrator 流程图中的位置：

```
用户提交 prompt
   │
   ▼
[Router 评估]                    ← v0.5：本 review 范围
   │
   ▼
[Orchestrator 检查]              ← v0.6+ 责任
   ├─ worktree 是否存在/需要
   ├─ review gate 是否需要
   ├─ permission gate
   │
   ▼
[adapter.start()]                 ← 由 orchestrator 调用
```

**router 不应承担 worktree / permission / review gate 决策**——v0.5 的"不绕过"是靠 router 纯数据实现的，但 design §七没有显式画出这个分层关系。

### 4.7 新增 M7：opencode 适用边界声明（详见 §五）

明确写入 design 文档：

> opencode **不可**用于以下场景：
> - 修改 Hermes 内部代码（用 hermes-local）
> - 涉及 production 数据库 / secrets 的修改（用 hermes-local with review gate）
> - 大范围重构（用 codex）
> - 架构变更（用 claude-code）
> - 任何 review_gate 必需的任务（opencode.review_gate=False）

### 4.8 新增 M8：禁用 executor 的"硬约束"

`AdapterRegistry` 加方法：

```python
def disabled(self, executor_id: ExecutorId, reason: str) -> None:
    """Mark an executor as disabled for the current session."""
```

`router.route()` 入口检查 `disabled` 集合，跳过这些 executor（不仅 UNAVAILABLE，还要显式区分"uninstalled" vs "user-disabled"）。

---

## 五、opencode Executor 适用边界

### 5.1 设计定位（来自设计 + 仓库历史）

从 `docs/architecture/agent-adapter-layer.md` 和 `docs/releases/hermes-v2.8.1-core-stabilization.md`：

- `opencode` = "外部 OpenCode CLI 适配器；**窄范围**代码复核、**廉价**二审、失败样本采集、**协作链路 smoke**"
- 默认模型 `deepseek-v4-flash`（cheap）
- `review_gate=False`（无 approval 拦截）
- `native_diff_events=False`（adapter 端从 `git diff snapshot` 后期生成）

### 5.2 推荐适用场景 ✅

| 场景 | 理由 |
|---|---|
| 本地 smoke test（"<executor> 是否能跑起来"） | cheap, fast, 失败即可丢弃 |
| 廉价二审（"看看另一个 agent 的 diff 有没有明显问题"） | 不需要 review gate；失败可接受 |
| 备选实现 / 对照实验（"用 opencode 写一个 X 试试"） | 探索性，结果不直接进主分支 |
| 失败样本采集（"主 run 失败了，让 opencode 再试一次收集日志"） | 隔离的 sub-run |
| OpenCode CLI 自身相关任务（"opencode 这个工具如何"） | 工具自检 |
| QA scan 作为 codex 失败的 fallback | "用 opencode 再扫一遍" |
| 离线场景（Claude/Codex API 不可用） | opencode 本地优先 |

### 5.3 不适用场景 ❌

| 场景 | 理由 |
|---|---|
| 修改 Hermes 内部代码（hermes/、hermes-agent/、.hermes/config.yaml） | review_gate 不可用 + 改动需要 Hermes 自身感知 |
| Production 路径改动 | opencode.review_gate=False，无 approval 拦截 |
| 架构 / 设计决策 | opencode 的 "validation" 角色是 verify，不是 design |
| 大范围重构（> 5 文件估计） | opencode 不擅长大规模 refactor（设计就让 codex 做） |
| 涉及 secrets / token / 凭证 | 任何 executor 都该被 review，但 opencode 特别脆弱（review_gate=False） |
| 关键 bug 修复需要 merge 到 main | 走 codex/claude + worktree + diff review |
| 需要 long-running streaming 的任务 | opencode.streaming="line-buffered"，不如 hermes-local 的 "realtime" |
| 用户没明确说"用 opencode"或"二审"的初次主任务 | opencode 是 backup，不是 primary |

### 5.4 opencode 自身能力的真实约束

来自 `registry.py:196-210` 和 `opencode_adapter.py`：

```python
ExecutorManifest(
    id="opencode",
    capabilities=ExecutorCapabilities(
        structured_tool_calls=True,    # 子进程 JSON lines 半结构化
        native_diff_events=False,       # adapter 用 git diff 后期补
        reasoning_blocks=True,          # 子进程 --reasoning
        review_gate=False,              # ⚠️ 无 approval
        streaming="line-buffered",      # 非 realtime
    ),
    default_model="deepseek-v4-flash",  # ⚠️ cheap，可能漏判
    ui_fidelity="full",
    supports_worktree=False,            # ⚠️ adapter 不强制 worktree
)
```

**结论**：opencode 是"协作链路中的一个低风险实验节点"，不是"主生产 executor"。Router 把它和 codex/claude 平级推荐是危险的——`review_gate=False` + `supports_worktree=False` 这两个 False 应该影响 router 评分。

### 5.5 建议的边界声明文本（写入 design §4 表格注释）

```markdown
> ⚠️ opencode 的能力约束：
> - `review_gate=False`：无 approval 拦截，prompt 风险由 router 负责拦
> - `supports_worktree=False`：adapter 不创建 worktree，run workspace 由 orchestrator 决定
> - `default_model=deepseek-v4-flash`：cheap，可能漏判
> - 推荐任务必须在 §5.2 列表内；超出的任务即使 keyword 命中，UI 应展示 "opencode 不适合此任务" 警告
```

---

## 六、P0 / P1 / P2 问题清单

### 🔴 P0（必须先修，否则影响生产可用性）

| # | 主题 | 位置 | 修复建议 |
|---|---|---|---|
| P0-1 | Hermes 内部任务推荐倒挂 | `router.py:54-116` | §4.1 M1：加 `_is_hermes_internal()` 硬短路，先于所有 RouteRule |
| P0-2 | opencode 关键词过宽 over-recommend | `router.py:79-90` | §4.2 M2：移除 local/offline/prototype/experiment/self-hosted |
| P0-3 | `RouterRecommendation` 缺 `unavailable_reason` / `fallback_executor` / `matched_keywords` 字段 | `types.py:244-252` | §4.3 M3：补齐设计 §二 schema |
| P0-4 | `alternatives` 缺 per-executor reason/availability | `types.py:250` | §4.3 M3：改为 `List[AlternativeExecutor]` 结构化 |
| P0-5 | `confidence` 类型与设计不一致 | `types.py:248` vs `router.py` 多处 | §4.4 M4：改回 `Confidence` enum + 保留 float score |

### 🟡 P1（影响推荐质量与可观察性，建议 Phase 7.1 修）

| # | 主题 | 位置 | 修复建议 |
|---|---|---|---|
| P1-1 | CLI `--accept` flag 与"必须用户确认"语义有偏差 | `cli.py:325` | `--accept` 必须配 `--audit-log` 写明 "cli auto-accept"，禁止 desktop UI 调用此 flag |
| P1-2 | 推荐理由不展示命中 keyword | `router.py:63, 75, 87, 99, 112` | reason_template 改为动态：`f"命中关键词: {matched}（{n}/{total}）— OpenCode 适合本地/备选验证"` |
| P1-3 | `verify`/`test`/`check`/`sanity`/`smoke`/`QA` 不在 opencode 关键词 | `router.py:79-90` | §4.2 M2 增补 |
| P1-4 | 关键词碰撞：`implement` 击败 `alternative implementation` | `router.py:67-78` | §4.2 M2：加短语 regex 优先匹配 |
| P1-5 | Hermes 内部规则的 confidence 0.82 + priority 5 是脆弱的"数值偶然" | `router.py:103-115` | P0-1 修完后这个可以依赖 hard short-circuit，不必再调数值 |
| P1-6 | 用户上次选择不记忆（design §六明说"同一 session 记忆"） | 全局 | `Router` 状态加 `last_user_choice: Optional[ExecutorId]`，`route()` 入口若 `ctx.title` 与上次相似则预填 |
| P1-7 | opencode `capabilities.review_gate=False`，router 推荐后没有二次提示 | `registry.py:204` + `router.py` | router 评分时给 `review_gate=False` 的 executor 加 -0.1 惩罚分（可被 keyword 命中抵消） |
| P1-8 | 缺硬约束（破坏性操作）规则 | `router.py` | §4.5 M5：HARD_BLOCK_CONDITIONS |
| P1-9 | opencode `supports_worktree=False`，但 `prefer_worktree` 字段未使用 | `types.py:262` + `router.py` | router 评估时若 `ctx.prefer_worktree=True` 且推荐 executor 不支持 worktree，confidence 扣 0.2 并 reason 注明 "该 executor 不支持 worktree" |
| P1-10 | executor id 命名不统一（`codex` vs `codex-cli`） | `types.py:43` vs `router.py:119-121` vs `cli.py` 注释 | 统一为 `codex`（与 `registry.py:166` 对齐），并加 `codex-cli` alias |

### 🟢 P2（实现细节 / 文档 / 后续阶段）

| # | 主题 | 位置 | 修复建议 |
|---|---|---|---|
| P2-1 | fallback 顺序与设计不一致 | `router.py:119-121` | 改 `["claude-code", "codex", "opencode", "hermes-local", "deepseek-tui"]` |
| P2-2 | `TaskCreateContext.project_path` / `prefer_worktree` 未使用 | `router.py:202-205` | `route()` 加入这两个字段到 scoring（暂时不参与 score，仅写进 reason 让 UI 可见） |
| P2-3 | 阈值分散（0.3、0.4、0.7、0.82、0.85、0.88、0.90） | `router.py` 多处 | 抽常量 `CONFIDENCE_HIGH = 0.7, MEDIUM = 0.4, LOW = 0.2` |
| P2-4 | reason 字符串拼接混乱（"Best match was X (unavailable). Falling back to Y: Z"） | `router.py:248-251` | 改用结构化 `RouterRecommendation` 字段，UI 自己拼 |
| P2-5 | 缺 "router-policy.yaml" 团队规则覆盖（roadmap §Phase 11） | `router.py:175-184` 初始化 | 留到 v1.0 决策，本期不动 |
| P2-6 | 缺 `Router` 单元测试 | `hermes-agent/tests/managed_agents/test_router.py` 是另一个 router | 建议 `hermes-agent/tests/executors/test_router.py`：覆盖 §3.1 / §3.2 / §3.3 / §4.1 / §4.2 五个核心场景 |
| P2-7 | design §八扩展点提到"haiku/flash 分析复杂 prompt"，但 router 当前 100% 关键词 | `semi-auto-executor-router.md §八` | 留到 v1.0；本期确认 LLM routing **不**在 v0.5 范围 |
| P2-8 | OpenCodeAdapter 自身没有 retry / circuit breaker | `opencode_adapter.py:83-129` | 现状仅 try/except，3 次 OpenCode 404 重试建议在 adapter 层加（参考 `docs/reports/hermes-v2.8.1-agent-sync-audit.md` 的 opencode 404 历史） |

---

## 七、复核检查表对应结论

| 用户的检查点 | 结论 |
|---|---|
| 1. opencode 是否被正确作为 executor 候选，而不是替代整个 Hermes Desktop 控制台 | ✅ 正确（§2.1） |
| 2. Router 是否把 opencode 推荐给合适任务：local agent verification / review / alternative implementation / lightweight QA | ⚠️ 偏宽：local/offline/prototype 过宽（§3.2）；review 实际是 claude-code 命中（opencode 没在 keyword 里）；lightweight QA 实际是 deepseek-tui 命中（§3.4） |
| 3. 是否有过度推荐 opencode 的情况 | 🔴 有：5 个过宽 keyword 导致 over-recommend（§3.2） |
| 4. 是否有 executor unavailable 时仍然推荐的问题 | 🟡 推荐时正确降级到备选，但 `unavailableReason` 字段缺失，调用方无法结构化查询（§3.8） |
| 5. 推荐理由是否足够透明 | 🔴 不够：reason 是固定模板，不展示命中 keyword（§3.5） |
| 6. 用户是否可以覆盖推荐 | ✅ 可以：CLI / 数据层 / 字段都齐（§2.4） |
| 7. Router 是否有自动执行风险 | 🟡 自身无；但 CLI `--accept` 提供 auto-accept 路径，desktop 复用需警惕（§3.6） |
| 8. Router 是否绕过 worktree / diff review | ✅ 不绕过：Router 纯数据（§2.5）；但 `prefer_worktree` 字段未被 router 评估，缺 P1-9 提示 |

---

## 八、不修改业务代码的承诺

本次复核只输出本 review 文档，不修改：
- `hermes-agent/executors/router.py`
- `hermes-agent/executors/cli.py`
- `hermes-agent/executors/types.py`
- `hermes-agent/executors/registry.py`
- `hermes-agent/executors/opencode_adapter.py`
- `docs/architecture/semi-auto-executor-router.md`

P0 修复建议（§六 P0-1 ~ P0-5）建议作为 Phase 7.1 单独 PR 处理，不混入当前 Phase 7 验收。

---

## 附录 A：实证测试结果（18 prompt）

```
review the hermes adapter design                         -> claude-code    conf=0.31   src=keyword   ❌ 设计要求 hermes-local
refactor the hermes gateway                              -> hermes-local   conf=0.31   src=keyword   ✅（偶然）
build a local prototype for hermes adapter               -> opencode       conf=0.31   src=keyword   ❌ 设计要求 hermes-local
alternative implementation of codex adapter              -> opencode       conf=0.28   src=keyword   ✅
local experiment with new validation approach            -> opencode       conf=0.35   src=keyword   ❌ 设计无此规则
verify that opencode works offline                       -> opencode       conf=0.31   src=keyword   ✅（靠 "opencode" 命中）
fix typo in adapter file                                 -> deepseek-tui   conf=0.34   src=keyword   ✅
design a new internal admin tool                         -> hermes-local   conf=0.31   src=keyword   ✅（偶然）
audit the opencode fallback path                         -> deepseek-tui   conf=0.30   src=keyword   ⚠️ 应是 opencode（任务含 opencode）
implement an offline backup feature                      -> opencode       conf=0.31   src=keyword   ❌ 设计要求 codex
experiment with new feature for hermes                   -> opencode       conf=0.28   src=keyword   ❌ 设计要求 hermes-local
review the local opencode adapter                        -> opencode       conf=0.31   src=keyword   ✅
small typo fix in pipeline config                        -> deepseek-tui   conf=0.38   src=keyword   ✅
migrate the hermes dispatcher code                       -> hermes-local   conf=0.31   src=keyword   ✅（偶然）
compare the codex and opencode adapters                  -> opencode       conf=0.31   src=keyword   ✅
quick patch to fix a hermes scheduler bug                -> deepseek-tui   conf=0.42   src=keyword   ⚠️ 应是 hermes-local（任务含 hermes scheduler）
describe how to test local performance                   -> opencode       conf=0.28   src=keyword   ⚠️ 边界
should I add a new hermes feature                        -> hermes-local   conf=0.28   src=keyword   ✅
```

✅ 正确 9 / ❌ 错 5 / ⚠️ 边界 4 = 18

---

## 附录 B：关键代码引用

- 路由规则表：`hermes-agent/executors/router.py:54-116`
- 评分算法：`hermes-agent/executors/router.py:137-153`
- 主排序逻辑（priority 仅 tiebreaker）：`hermes-agent/executors/router.py:208-216`
- 不可用降级逻辑：`hermes-agent/executors/router.py:235-256`
- Fallback 顺序与 id 不一致：`hermes-agent/executors/router.py:119-121, 287`
- CLI `--accept` flag：`hermes-agent/executors/cli.py:325`
- `RouterRecommendation` 缺字段：`hermes-agent/executors/types.py:244-252`
- `executor_id` 命名约定（types.py 注释用 `codex`）：`hermes-agent/executors/types.py:43`
- Registry 用 `codex`：`hermes-agent/executors/registry.py:166`
- opencode manifest 能力（review_gate=False / supports_worktree=False）：`hermes-agent/executors/registry.py:196-210`
- OpenCodeAdapter 无 retry：`hermes-agent/executors/opencode_adapter.py:83-129`
