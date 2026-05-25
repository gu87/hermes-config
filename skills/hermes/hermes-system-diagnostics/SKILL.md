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

### 标准流程（8 步）

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
# 关注：agent 数量、类型、toolsets、skills、model_ref 字段

# 5. Managed Agents 配置 — read_file /Users/gu/.hermes/hermes-agent/configs/managed_agents/agents.yaml
# 交叉验证：toolsets、skills、permission 与 agent-registry.json 一致

# 6. 模型路由 — read_file /Users/gu/.hermes/config/models.yaml
# ⚠️ 权威源是 models.yaml，不是 config.yaml 的 model_aliases 段
# 解析每个 agent 的 model_ref → 查 models.yaml 的 provider/base_url/model

# 7. 错误日志 — tail -30 /Users/gu/.hermes/logs/errors.log
# 重点关注：AuthenticationError、ConnectionError、keepalive failed、chain depth exceeded

# 8. 定时任务 — cronjob(action='list')
```

### 输出格式
```
进程表 | Agent注册表(含skills审计) | 模型路由表(models.yaml) | 端口映射 | 问题列表 | 定时任务表
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

#### 第 2 层：models.yaml（Agent 模型路由权威源）
```
文件：/Users/gu/.hermes/config/models.yaml
关键字段：models 段
  - 每个 model_ref 定义：provider、base_url、model、status
  - deepseek_pro/deepseek_flash 用原生 deepseek provider（api.deepseek.com）
  - claude_opus 用 anthropic provider（flashapi.top 代理）
  - codex_cli 用 openai-codex provider（外部 CLI，base_url 为空）
  - tars_gpt54 用 custom provider（flashapi.top/v1）
  - models.yaml 是 model_ref → 实际模型/端点的单一权威源
  - config.yaml 的 model_aliases 段已废弃 / 仅保留兼容，不作为自检依据
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
  ├─ model_ref 在 models.yaml 中存在？
  │   ├─ 是 → 检查该 model_ref 的 provider、base_url、status 是否有效
  │   └─ 否 → 根因确认：model_ref 缺失
  │         → 修复：在 models.yaml 添加 model_ref 定义
  └─ API Key 格式检查
      ├─ sk-ant-* → Anthropic 原生格式，直连 api.anthropic.com
      └─ sk-*（非 ant） → 中转格式，必须配 base_url
```

### 经典病例：model_ref 在 models.yaml 中缺失

**症状**：子 Agent 报 `Error code: 401 - invalid x-api-key`

**根因**：agent-registry.json 中 `model_ref: "xxx"` 在 `models.yaml` 中未定义 → 系统回退到 provider 默认 endpoint → 用中转 Key 直连 → 401

**修复**：在 `models.yaml` 添加缺失 model_ref 定义，含 provider、base_url、model 字段。

### 注意事项
- Hermes 的 `ANTHROPIC_API_KEY` env var 和 Claude Code 的 `ANTHROPIC_AUTH_TOKEN` 可能是同一个值，但名字不同
- **model_ref 权威源是 models.yaml，不是 config.yaml 的 model_aliases**。自检时不要读 model_aliases 来判断 Agent 实际使用的模型
- 修改 `config.yaml` 后需重启 Gateway 生效

---

## 四、Agent Skills 合理性审计

### 触发条件
- 用户问「skills 合理吗」「检查一下 skills 分配」
- 新增/移除 skill 后验证
- 系统自检的一部分

### 审计方法（三层交叉验证）

对每个 Agent 的每个 skill，执行：

```
skill_view(name) → 读 SKILL.md frontmatter 的 agents: 声明
                 → 读 skill 描述中的工具需求（terminal/npx/browser/curl）
       ↓
对比 agent-registry.json 中该 Agent 的 toolsets
       ↓
判断：Agent 能否执行 skill 描述的完整工作流？
```

### 输出格式

```
| Agent | Skill | 匹配? | 问题 |
|-------|-------|-------|------|
| Pirlo | comfyui | ❌ | 需要 terminal，Pirlo 只有 [file] |
| Ambrosini | playwright-mcp | ❌ | 需要 browser，Ambrosini 无此工具集 |
```

### 修复原则（保守方案）

1. **不为 skill 改 Agent 能力** — 不给只读/策划 Agent 加 terminal，不破坏角色边界
2. **skill frontmatter `agents:` 以实际能执行该 skill 的 Agent 为准**
3. **修复优先级**：移除不匹配 skill > 重分配 skill 到有能力的 Agent > 给 Agent 加工具集（不推荐）

### 常见不匹配模式

| 模式 | 示例 | 修复 |
|------|------|------|
| 只读 Agent 有需要 terminal 的 skill | Pirlo × comfyui, Hermes-internal × design-md(lint) | 移除或重分配到 Claude |
| 质量门卫有需要浏览器操作的 skill | Ambrosini × playwright-mcp | 移除 |
| Agent 有 skill 但缺对应 MCP 工具集 | Codex × playwright-mcp (无 mcp-playwright) | 移除 skill 或补工具集 |

---

## 五、自检常见错误（Pitfalls）

### 1. 用系统 prompt 注入标签判断字符数

**❌ 错误**: 从 system prompt 的 `[99% — 1,364/1,375 chars]` 标签判断 User Profile 容量
**✅ 正确**: `wc -m /Users/gu/.hermes/memories/user-profile.md` 读源文件实际字符数。系统注入标签是压缩/截断版本，不代表源文件状态。

### 2. 用 config.yaml model_aliases 判断 Agent 模型

**❌ 错误**: 读 config.yaml 的 model_aliases 段 → 推断 deepseek_pro 走 Anthropic 兼容层
**✅ 正确**: models.yaml 是权威源。deepseek_pro/deepseek_flash 用原生 deepseek provider（api.deepseek.com）。model_aliases 仅保留兼容，不作为自检依据。

### 3. 凭 authority-map 旧结论推断 Skills 状态

**❌ 错误**: 读 authority-map.md 说「当前未填充 subagent_profile.skills」→ 报告 skills 未注册表化
**✅ 正确**: 读 agent-registry.json 的 subagent_profile.skills 数组。当前 8/8 Agent 都已填充。

### 4. 不交叉验证 agent-registry.json 和 agents.yaml

**❌ 错误**: 只读一个文件就下结论
**✅ 正确**: 两个文件逐 Agent 对比 toolsets 和 skills，不一致时报告具体行号差异

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

## 六、交叉文件一致性验证（agent-registry.json ↔ agents.yaml）

### 触发条件
- 系统自检
- toolsets 或 skills 变更后
- 发现 Agent 行为异常

### 验证流程

```python
# 1. 读取两个文件
registry = read_file('/Users/gu/.hermes/config/agent-registry.json')
agents_yaml = read_file('/Users/gu/.hermes/hermes-agent/configs/managed_agents/agents.yaml')

# 2. 逐 Agent 对比
for agent_id in ['claude', 'codex', 'pirlo', 'agent-tars', 'deepseek-tui', 'ambrosini', 'hermes-internal', 'intelligence']:
    compare(registry[agent_id].subagent_profile.toolsets, agents_yaml[agent_id].tools)
    compare(registry[agent_id].subagent_profile.skills, agents_yaml[agent_id].skills)
    compare(registry[agent_id].subagent_profile.model_ref, agents_yaml[agent_id].model_ref)
    compare(registry[agent_id].subagent_profile.permission_mode, agents_yaml[agent_id].permission)
    
# 3. 报告差异
# 有差异 → 列出具体 Agent、字段、两个文件各自的值的行号
# 无差异 → toolset_mismatches = 0, skill_mismatches = 0
```

### 已知陷阱

- **agents.yaml 和 registry.json 的 tools 字段名不同**: registry 用 `toolsets`，agents.yaml 用 `tools`
- **permission 字段名不同**: registry 用 `permission_mode`，agents.yaml 用 `permission`
- **git 工具集**: registry 用 `"git"`，agents.yaml 用 `"git"` 也在 tools 列表中。两者必须一致
- **authority-map.md 声明两者都是权威源**: 必须在自检时都读，不能偏废

---

## 七、部署就绪性验证

### 触发条件
- 用户问「换个电脑能部署吗」「推送到 GitHub 了吗」
- 准备在新机器上重建系统

### 部署必备文件清单

| 文件 | 路径 | 是否在 git？ | 备注 |
|------|------|-------------|------|
| 主配置 | `config.yaml` | 需白名单 | 含 model/delegation/gateway 配置 |
| Agent 注册表 | `config/agent-registry.json` | 需白名单 | Agent 编制、skills、routing |
| 模型路由 | `config/models.yaml` | 需白名单 | model_ref → provider/endpoint 映射 |
| Managed Agents | `config/managed-agents.yaml` | 需白名单 | 从 hermes-agent/configs/ 复制出来 |
| 身份定义 | `SOUL.md` | ✅ 已在 | Hermes 人格与边界 |
| 记忆 | `memories/` | ✅ 已在 | MEMORY.md, user-profile.md |
| 技能 | `skills/` | ✅ 已在 | 所有 SKILL.md |
| 文档 | `docs/` | ✅ 已在 | runbook, authority-map |
| 部署脚本 | `bin/setup.sh` | 需白名单 | 一键部署 |
| API 密钥 | `.env` | ❌ 不入库 | 手动填写 |
| 平台认证 | `auth.json` | ❌ 不入库 | 飞书等平台 token |
| Agent 软件 | `hermes-agent/` | ❌ 不入库 | 需单独安装 |

### .gitignore 白名单模式

当前 `.gitignore` 以 `*` 开头（拒绝全部），只显式放行少数路径。部署就绪需要追加：

```gitignore
# 配置文件
!config.yaml
!config/
!config/*.yaml
!config/*.json

# 部署脚本
!bin/
!bin/setup.sh
```

### 部署流程（新机器）

```bash
# 1. 安装 Hermes Agent
pip install hermes-agent
# 或: git clone https://github.com/NousResearch/Hermes-Agent ~/hermes-agent

# 2. 克隆配置仓库
git clone https://github.com/gu87/hermes-config ~/.hermes

# 3. 运行部署脚本
cd ~/.hermes && bash bin/setup.sh
# → 检测 hermes-agent 安装位置
# → 复制 config/managed-agents.yaml 到 hermes-agent/configs/managed_agents/agents.yaml
# → 创建 .env 模板

# 4. 填写 API 密钥
vim ~/.hermes/.env
# DEEPSEEK_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# 5. 启动
hermes gateway start
```

## 参考文档
- `references/model-config-field-map.md` — Gu 的机器实际三层配置映射表，含已验证别名和诊断命令
- `references/token-efficiency-audit-2026-05-25.md` — 2026-05-25 架构自检实录：配置项发现、浪费模式、修复建议
- `references/system-audit-2026-05-25.md` — 2026-05-25 全量系统自检实录：5 个关键发现、修复方法、最终状态快照
- `references/deployment-verification-2026-05-25.md` — 2026-05-25 部署就绪性审计实录：仓库结构、.gitignore 缺口、launchd plist 清单
