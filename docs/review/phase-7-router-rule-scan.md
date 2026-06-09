# Phase 7 Executor Router 初始规则扫描

> 检查 v0.5 `ExecutorRouter` 的关键词规则定义的合理性。

扫描日期：2026-06-04
扫描范围：
- `hermes-agent/executors/router.py` — Router 核心逻辑 + 规则
- `hermes-agent/executors/registry.py` — ExecutorManifest 定义
- `hermes-agent/executors/types.py` — 类型定义
- `hermes-agent/executors/deepseek_tui_adapter.py` — DeepSeek TUI adapter（stub）
- `hermes-agent/executors/claude_code_adapter.py` — Claude Code adapter
- `hermes-agent/executors/codex_adapter.py` — Codex adapter
- `hermes-agent/executors/opencode_adapter.py` — OpenCode adapter

---

## 问题总览

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | executor_id 不一致：router 用 codex-cli，registry 用 codex | 🔴 高危 | codex 路由永远无效 |
| 2 | deepseek-tui 规则高置信度指向 stub | 🔴 高危 | 大量任务被推荐给不可用的 executor |
| 3 | hermes-local 被边缘化 | 🟡 中危 | 多数工程任务路由不到 hermes-local |
| 4 | 关键词匹配阈值过低 | 🟡 中危 | 单个单词即可触发高置信度路由 |
| 5 | stub executor 无特殊标记 | 🟡 中危 | 路由层不感知适配器实际状态 |
| 6 | fallback 顺序不合理 | 🟡 中危 | 不可用的 codex-cli 排第一 |
| 7 | 推荐理由未提及 executor 真实能力限制 | 🟡 中危 | 用户可能误选低能力 executor |
| 8 | alternatives 列表不包含 hermes-local | 🟢 低危 | 通用后备缺失 |
| 9 | opencode 与 deepseek-tui 规则轻微重叠 | 🟢 低危 | 低影响 |

---

## 1. executor_id 不一致：codex-cli vs codex 🔴 高危

### 位置

`router.py` 第 68 行 vs `registry.py` 第 166 行

```python
# router.py 中：
RouteRule(executor="codex-cli", keywords=[...], ...)

# registry.py 中注册为：
"codex": ExecutorManifest(id="codex", ...)
```

### 问题

Router 的所有引用使用 `"codex-cli"`，但 Registry 注册的 key 是 `"codex"`。这意味着：

1. **`router.route()` 永远不会推荐 codex** — 所有匹配「implement」、「refactor」、「build」等关键词的任务都指向一个不存在的 executor_id
2. **unavailable 降级始终触发** — `"codex-cli" not in available` 始终为 True
3. **fallback 死循环** — `_FALLBACK_ORDER` 中 `"codex-cli"` 也排第一，同样不可用

### 建议

```python
RouteRule(executor="codex", ...)
_FALLBACK_ORDER = ["codex", "claude-code", ...]
```

---

## 2. deepseek-tui 规则高置信度指向 stub 🔴 高危

### 位置

`router.py` 第 91-102 行

```python
RouteRule(
    executor="deepseek-tui",
    keywords=["bug", "fix", "quick", "small", "simple",
              "patch", "hotfix", "typo", "lint",
              "scan", "audit", "find", "locate",
              "trivial", "minor", "cosmetic"],
    priority=7,
    confidence=0.88,
    reason_template="...DeepSeek TUI is fast and low-cost",
)
```

### 对比：实际 adapter 状态

`deepseek_tui_adapter.py`：

```python
# v0.3 status: **STUB** — ... check_health() reports UNAVAILABLE ...
# The adapter does NOT attempt to launch the TUI...
```

### 问题

- `confidence=0.88` 是规则中第二高的置信度
- 关键词覆盖了大量常见场景：bug、fix、quick、scan、lint、typo
- 但 deepseek-tui 是 **STUB**，永不工作

### 影响

所有匹配这个规则的常见任务（修复 bug、快速扫描、lint）都会：
1. 先推荐 deepseek-tui
2. 发现 unavailable，降级到 alternatives
3. 最终落到 claude-code 或 codex

**高价值 executor 被低价值任务占用**。

### 建议

```python
RouteRule(
    executor="deepseek-tui",
    confidence=0.40,    # 大幅降低基准置信度
)
```

同时将低成本任务类关键词加入 hermes-local 规则。

---

## 3. hermes-local 被边缘化 🟡 中危

### 位置

`router.py` 第 103-116 行

```python
RouteRule(
    executor="hermes-local",
    keywords=["hermes", "gateway", "adapter", "scheduler",
              "orchestrator", "dispatcher", "agent router",
              "internal", "admin", "config", "configuration",
              "cron", "batch", "pipeline", "workflow",
              "telegram", "feishu", "lark", "webhook"],
    priority=5,
)
```

### 问题

hermes-local 的关键词只匹配 **Hermes 内部运维场景**。对通用工程任务（测试、调试、搜索代码、格式化等）没有任何匹配。

但实际上，**hermes-local 是 v0.5 唯一确认可用的 executor**（同进程 Python，无需安装额外 CLI）。

### 建议

扩展 hermes-local 的关键词覆盖通用工程任务：

```python
RouteRule(
    executor="hermes-local",
    keywords=[
        "test", "testing", "debug", "logging",
        "format", "reformat", "cleanup",
        "search", "grep", "find", "inspect",
        "dependency", "update", "upgrade",
        "document", "readme", "comment",
    ],
    priority=6,
    confidence=0.80,
)
```

---

## 4. 关键词匹配阈值过低 🟡 中危

### 位置

`router.py` 第 152 行

```python
return min(0.3 + ratio * 0.7, 1.0)  # 任意命中至少 0.3
```

### 问题

单个关键词命中获得 `text_score=0.3`。结合 deepseek-tui 的 `confidence=0.88`，最低组合得分为 `0.3 × 0.88 = 0.264`。fallback 的固定置信度只有 `0.40`。

**单个常见单词的误触率很高**：

| 标题 | 命中 | 路由结果 | 是否合理 |
|------|------|---------|---------|
| "Add find feature" | "find" → deepseek-tui | 0.26 | ❌ 应是 codex |
| "Scan the code" | "scan" → deepseek-tui | 0.26 | ❌ 应是 hermes-local |
| "Small change" | "small" → deepseek-tui | 0.26 | ❌ 应是 hermes-local |

### 建议

```python
return min(0.5 + ratio * 0.5, 1.0)  # 地板从 0.3 提升到 0.5
```

---

## 5. Stub Executor 无特殊标记 🟡 中危

### 位置

`router.py` 第 230-256 行（unavailable 处理）

### 问题

所有 `check_health()` 返回 `UNAVAILABLE` 的 executor 在 router 看来是一样的。但实际上 deepseek-tui 即使安装了也返回 UNAVAILABLE（因为 stub 故意不启动），而 codex 未安装也返回 UNAVAILABLE。Router 无法区分"已安装但 stub"和"未安装"。

### 建议

在 `ExecutorManifest` 中增加 `stub: bool = False` 标记。Router 在评分时对 stub executor 额外降权：

```python
@dataclass
class ExecutorManifest:
    stub: bool = False  # 新增字段
```

```python
# router.py
manifest = registry.get_manifest(best_rule.executor)
if manifest.stub:
    confidence *= 0.1  # stub 几乎不推荐
```

---

## 6. Fallback 顺序不合理 🟡 中危

### 位置

`router.py` 第 119-121 行

```python
_FALLBACK_ORDER = [
    "codex-cli", "claude-code", "opencode", "hermes-local", "deepseek-tui",
]
```

### 问题

1. `"codex-cli"` 根本不存在（应为 `"codex"`）
2. `"deepseek-tui"` 是 stub，排在最后也无意义
3. `"hermes-local"`（唯一确认可用）排第四

### 建议

```python
_FALLBACK_ORDER = [
    "hermes-local",  # 总是可用
    "codex",         # 注册名为 codex
    "claude-code",
    "opencode",
]
# 移除 deepseek-tui
```

---

## 7-9：低优先级项 🟢

| # | 问题 | 建议 |
|---|------|------|
| 7 | reason_template 不反映真实能力 | 从 manifest 读取描述，stub 标记为 "not implemented yet" |
| 8 | alternatives 缺失 hermes-local | 追加 `alternatives.append("hermes-local")` |
| 9 | opencode 与 deepseek-tui 规则重叠 | 低影响 — 优先级排序后 opencode 优先，可忽略 |

---

## 附录：P0 修复清单

| 优先级 | 修复项 | 文件 | 行数 |
|--------|--------|------|------|
| **P0** | `"codex-cli"` → `"codex"` 统一命名 | `router.py` L69, L75, L121 | 3 处 |
| **P0** | deepseek-tui confidence 0.88 → 0.40 | `router.py` L101 | 1 行 |
| **P1** | hermes-local 关键词扩展 | `router.py` L105-116 | +15 行 |
| **P1** | fallback 顺序调整 | `router.py` L119-121 | 1 行 |
| **P1** | alternatives 追加 hermes-local | `router.py` L222 | 3 行 |
| **P2** | 文本评分地板 0.3 → 0.5 | `router.py` L153 | 1 行 |
| **P2** | stub 支持（manifest + 降权） | `types.py` + `router.py` | ~15 行 |
