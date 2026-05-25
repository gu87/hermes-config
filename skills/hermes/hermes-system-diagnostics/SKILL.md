---
name: hermes-system-diagnostics
description: Hermes Agent 系统诊断 — 健康快照、模型配置排障、常见错误模式识别。覆盖进程/端口/资源检查、agent-registry model_ref 与 config.yaml model_aliases 对齐诊断、Anthropic 401/402 根因分析。
category: hermes
tags: [hermes, diagnostics, troubleshooting, system-health, model-config]
triggers:
  - "系统状态"
  - "agent有什么问题"
  - "检查一下"
  - "自我检查"
  - "系统快照"
  - "health check"
  - "model_ref"
  - "Claude 认证失败"
  - "401"
  - "402"
  - "ANTHROPIC_API_KEY"
---

# Hermes 系统诊断

两类诊断场景：例行健康快照 + 模型配置排障。

## 一、系统健康快照

### 触发条件
- 用户说"检查一下系统"、"agent状态"、"自我检查"、"系统快照"

### 标准流程（6 步）

```bash
# 1. 进程检查
ps aux | grep -E 'hermes|gateway|openchronicle' | grep -v grep

# 2. 端口检查
lsof -iTCP -sTCP:LISTEN -P -n | grep -E '8742|8787|8642|7890'

# 3. 资源检查
vm_stat | head -5
df -h /
```

```python
# 4. Agent 注册表 — read_file /Users/gu/.hermes/config/agent-registry.json
# 重点关注：agent 数量、类型、model_ref 字段

# 5. 错误日志 — tail -30 /Users/gu/.hermes/logs/errors.log
# 重点关注：AuthenticationError、ConnectionError、keepalive failed、chain depth exceeded

# 6. 定时任务 — cronjob(action='list')
```

### 输出格式
```
进程表 | Agent注册表 | 端口映射 | 问题列表 | 定时任务表
```

### 常见预警项及判定

| 日志关键词 | 问题 | 严重度 | 行动 |
|-----------|------|--------|------|
| `AuthenticationError` / `401` / `402` | API Key 或模型路由问题 | 高 | 进入「模型配置诊断」流程 |
| `NameResolutionError` / `Failed to resolve` | 代理/DNS 波动 | 低-中 | 检查 Clash Verge 状态 |
| `keepalive failed, triggering reconnect` | MCP 服务短暂失联 | 低 | 通常自愈，观察是否持续 |
| `chain depth exceeded` / `BLOCKING loop` | Agent 互相 @ 触发循环 | 低 | 系统已自动阻断 |
| `SIGTERM` / `Shutdown context` | Gateway 重启 | 中 | 检查飞书连接是否恢复 |
| `OPENROUTER_API_KEY not set` | OpenRouter 备用路由不可用 | 低 | 不影响主路由 |

---

## 二、模型配置诊断

### 触发条件
- Claude 子 Agent 认证失败（401/402）
- 用户反馈 Agent 模型路由不对
- 新增/修改 Agent 后验证路由

### 排查管线

#### 第 1 层：Claude Code 配置（用户端，已验证可用）
```
文件：~/.claude/settings.json
关键字段：
  - ANTHROPIC_BASE_URL → 实际中转地址（如 https://ai.flashapi.top）
  - ANTHROPIC_AUTH_TOKEN → 中转 API Key
  - ANTHROPIC_MODEL → 模型名（如 claude-opus-4-7）
```

#### 第 2 层：Hermes model_aliases（Agent 端）
```
文件：/Users/gu/.hermes/config.yaml
关键字段：model_aliases 段
  - 每个别名包含：base_url, model, provider
  - 所有 Agent 通过 model_ref 引用这里的别名
```

#### 第 3 层：Agent 注册表 model_ref（路由层）
```
文件：/Users/gu/.hermes/config/agent-registry.json
关键字段：每个 Agent 的 subagent_profile.model_ref
  - 必须与 model_aliases 中的某个别名精确匹配
  - 不匹配 → 回退到 provider 默认 endpoint → 大概率 401
```

### 诊断决策树

```
Agent 认证失败 401/402
  ├─ model_ref 在 model_aliases 中存在？
  │   ├─ 是 → 检查该别名的 base_url 和 API Key 是否有效
  │   └─ 否 → 根因确认：别名缺失
  │         → 修复：在 model_aliases 添加别名，对齐 Claude Code 配置
  │         → base_url 用 Claude Code 的 ANTHROPIC_BASE_URL
  │         → model 用 Claude Code 的 ANTHROPIC_MODEL
  └─ API Key 格式检查
      ├─ sk-ant-* → Anthropic 原生格式，直连 api.anthropic.com
      └─ sk-*（非 ant） → 中转格式，必须配 base_url
```

### 经典病例：model_ref 别名缺失

**症状**：Claude 子 Agent 报 `Error code: 401 - invalid x-api-key`

**根因**：`agent-registry.json` 中 `model_ref: "claude_opus"` 在 `config.yaml` 的 `model_aliases` 中不存在 → 系统回退到 provider 默认 endpoint（`api.anthropic.com`） → 用中转 Key 直连 Anthropic → 401

**修复**：在 `model_aliases` 添加缺失别名，对齐 Claude Code 的 `settings.json`：
```yaml
  claude_opus:
    base_url: https://ai.flashapi.top
    model: claude-opus-4-7
    provider: anthropic
```

### 注意事项
- Hermes 的 `ANTHROPIC_API_KEY` env var 和 Claude Code 的 `ANTHROPIC_AUTH_TOKEN` 可能是同一个值，但名字不同
- `model_aliases` 中已有别名（如 `co`, `cs`）可能与 Agent 注册表的 `model_ref` 用的不是同一套命名
- 修改 `config.yaml` 后需重启 Gateway 生效

---

## 三、Token/成本效率审计

### 触发条件
- 用户问「多Agent费Token吗」「设计合理吗」「自查一下」
- 系统运行一段时间后做成本复盘
- 新增/修改 Agent 后验证是否有浪费

### 审计清单（6 项）

```bash
# 1. delegation 模型分级 — 是否所有子Agent用同一个模型？
grep -A 3 "delegation:" ~/.hermes/config.yaml | grep -E "model|provider"

# 2. managed_persistence — 子Agent是否持久化？（false = 每次冷启动）
grep "managed_persistence" ~/.hermes/config.yaml

# 3. orchestrator + spawn_depth — 是否存在死能力？
grep -E "orchestrator|max_spawn_depth" ~/.hermes/config.yaml

# 4. Memory 用量 — 是否接近上限？
# 在 memory 工具返回的 USER PROFILE 和 MEMORY 段查看百分比

# 5. agent-registry.json 是否存在？
ls -la ~/.hermes/config/agent-registry.json 2>/dev/null || echo "MISSING"

# 6. SOUL.md Agent 列表 vs delegate_task agent_id enum — 是否存在漂移？
# 对比 SOUL.md 中列出的 Agent 名称和 delegate_task 实际可用的 agent_id
```

### 常见浪费模式

| 发现 | 影响 | 严重度 |
|------|------|--------|
| `managed_persistence: false` | 每次 delegate 冷启动子Agent，重载 system prompt + tools | 高 — 每次派活多烧 ~5-15K tokens |
| delegation 所有子Agent统一模型 | 调研/推理任务和机械小改用同一模型，贵的用不起便宜的干不好 | 中 |
| `orchestrator_enabled: true` + `max_spawn_depth: 1` | orchestrator 永远无法派活，死能力增加判断分支 | 低 |
| Memory 超限 (>3000 chars) | 每次对话都硬塞超限内容进 system prompt | 中 |
| agent-registry.json 不存在 | Agent 路由定义散落在 SOUL.md 和 channel prompt 中，无机器可读注册表 | 中 — 维护风险 |
| SOUL.md 列出的 Agent 不在 delegate_task enum 中 | 文档与实际代码不一致，如 claude-code-opus/claude-code-deepseek | 低 — 只有文档漂移时触发 |

### 修复指引

- **managed_persistence** → 改为 `true`（需确认 Hermes 版本支持）
- **模型不分级** → 为不同 Agent 类型配不同 delegation 模型（调研用 Pro，机械用 Flash）
- **orchestrator 死能力** → 要么关掉 `orchestrator_enabled: false`，要么 `max_spawn_depth: 2`
- **Memory 超限** → 按 `hermes-knowledge-architecture` 技能做内存瘦身，把长内容迁到 Obsidian

## 参考文档
- `references/model-config-field-map.md` — Gu 的机器实际三层配置映射表，含已验证别名和诊断命令
- `references/token-efficiency-audit-2026-05-25.md` — 2026-05-25 架构自检实录：配置项发现、浪费模式、修复建议
