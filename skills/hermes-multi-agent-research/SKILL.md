---
name: hermes-multi-agent-research
description: "UMBRELLA: 多Agent研究确认 + Agent路由决策 + Claude Code委托协议 + 常驻Worker + GitHub调研 + 竞品情报研究 + Web工具链。合并了 agent-routing-guide 和 hermes-claude-code-delegation。"
category: autonomous-ai-agents
agents: [hermes, nesta]
---

# Hermes 多Agent研究确认执行工作流 + 委托模式（UMBRELLA）

## 适用场景
- 用户给了一个模糊任务，需要先研究再确认方向
- 不确定产品特性/市场信息，需要先调研
- 需要拆解成多个并行的子任务，分别由不同Agent处理

## 核心原则
1. **先自己探索**：搜索、读文件、查资料，至少2-3轮
2. **形成假设**：给出多个可能的方向选项（而不是问用户该怎么做）
3. **等用户确认**：方向确认后再拆分执行，不自己瞎判断
4. **执行后汇报**：子Agent跑完后主控汇总，给用户完整结果

## 工作流步骤

### Step 1：任务接收
用户给出一个任务，提取关键信息：
- 客户/品牌是什么
- 核心目标是什么
- 有没有参考材料

### Step 2：自主研究（不问用户）
- 搜索相关信息（终端/web/文件）
- 读取用户提供的参考资料
- 分析产品/品牌的核心差异点
- 识别潜在风险或逻辑漏洞（如：套用竞品方案）

### Step 3：形成假设方案
输出多个可能的方向假设，每个包含：
- 方向名称/主题
- 核心逻辑
- 关键创意点
- 潜在风险

### Step 4：用户确认方向
展示假设方案，问用户："这个方向对吗？可以往下走吗？"

### Step 5：任务拆分与派发
确认方向后，拆成N个并行子任务，写入 mailbox：
```
~/.claude/teams/{project}/inbox/task_{name}.json
```
派发给子Agent（delegate_task 并发执行）

### Step 6：结果汇总
读取 outbox 中的结果，主控整合成完整方案文档

## Mailbox 格式
```json
{
  "task_id": "task_xxx",
  "agent": "角色（researcher/creative/resource）",
  "description": "任务描述",
  "context": "背景信息+参考文件路径",
  "status": "pending"
}
```

## 项目目录结构
```
~/.claude/teams/{project_name}/
├── inbox/
│   ├── task_a.json
│   ├── task_b.json
│   └── task_c.json
└── outbox/
    ├── task_a_result.json
    ├── task_b_result.json
    └── task_c_result.json
```

## 注意事项
- 子Agent没有当前对话记忆，所有context必须通过任务文件传递
- 子Agent完成后必须写结果到 outbox，主控读取 outbox 汇总
- 记忆隔离靠Mailbox实现，每个子Agent独立上下文

---

## §A — Hermes → 代码/文件任务委托模式

> Absorbed from `hermes-claude-code-delegation`. Use when the task involves file modification, script execution, or code changes that benefit from delegated execution via the mailbox protocol.

#### When to delegate code/file work
- Task requires **modifying files** (code, config, docs)
- Task requires **running shell commands** or scripts
- Task requires **local file system operations**
- Task has **clear file boundaries** and **testable acceptance criteria**
- The work is large enough that delegation is useful

**Do NOT** route to Claude Code when:
- The task is small enough for the current Agent to complete directly
- Pure research / information gathering → use the best currently available research path: browser, CLI, Kimi, web tools, or other verified sources
- Task has no file outputs → use Hermes internal reasoning or a research-oriented Agent when available
- Task scope is too vague to define `allowed_files` → clarify assumptions or ask one focused question if the risk is material

#### Delegation protocol (v2.6)

**Step 1: Create inbox** — write `~/.claude/teams/{project}/inbox/{task_id}.json`:
```json
{
  "schema_version": "2.6",
  "task_id": "{project}_{YYYYMMDD}_{序号}",
  "agent": "claude",
  "status": "pending",
  "goal": "一句话描述要交付什么",
  "allowed_files": ["必须指定具体文件或glob，不允许为空"],
  "acceptance_criteria": {
    "auto_checkable": ["系统可自动验证的条件"],
    "human_review": ["需要人工判断的条件"],
    "evidence_required": ["Agent必须提交的证据"]
  },
  "safety": {
    "allowed_paths": ["白名单路径"],
    "denied_commands": ["rm -rf", "sudo", "curl | sh", "chmod -R", "git push --force"]
  },
  "output_contract": {
    "path": "~/.claude/teams/{project}/outbox/{task_id}_result.json",
    "format": "json"
  }
}
```

**Step 2: Dispatch** using `delegate-v26.sh`, the current delegation tool, or an appropriate live Agent profile. Claude Code is one option, not the only code executor.

**Step 3: Always include in Claude Code prompt**:
```
你正在执行一个 v2.6 任务。任务描述和约束见 inbox 文件。
完成后，请将结果写入 outbox 文件（路径见 inbox.output_contract.path）。
outbox 必须是合法 JSON...
```

**Step 4: Verify** — after completion, run `verify-task.py` and `git diff --name-only` to detect changed files.

**Step 5: Human review** — all tasks end in `waiting_for_verification`. Only human moves to `completed`.

#### Safety rules
- Never delegate with empty `allowed_files`
- Never skip `verify-task.py` on execution tasks
- Changed files are detected by `git diff`, not by Agent self-reporting

#### v2.6 changes from v2.5
| v2.5 | v2.6 |
|------|------|
| `files` field could be empty | `allowed_files` required, no blanks |
| `changed_files` from Agent self-report | Detected by `git diff --name-only` |
| Wrapped output had `passed: true` | Marked `format_wrapped_unverified` |
| `acceptance_criteria` flat list | Split into `auto_checkable`/`human_review`/`evidence_required` |
| No evidence requirement | `evidence.outputs` required |

---

## §B — Hermes 常驻 Worker (Staam模式)

> Absorbed from `hermes-persistent-worker`. Use when creating a persistent Hermes sub-agent Worker that runs continuously in the background, receiving tasks via Mailbox.

#### Architecture
```
主 Hermes ←→ Mailbox (inbox/outbox) ←→ Worker (后台常驻)
```

#### 关键经验
**不能调用 `hermes chat`** — 它是交互式的，不接受 stdin pipe。必须直接调 DeepSeek REST API。

#### 目录结构
```
~/.claude/teams/{worker_name}/
├── inbox/          # 任务入口
├── outbox/         # 结果输出
├── logs/           # 日志
└── {worker_name}_daemon.py  # 主脚本
```

#### Daemon 核心逻辑要点

1. **轮询 inbox** 每 3 秒检查一次 `~/.claude/teams/{worker_name}/inbox/task_*.json`
2. **直接调 DeepSeek API**，不通过 hermes chat：
   ```python
   DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
   MODEL = "deepseek-v4-pro"
   ```
3. **工具调用**：在 daemon 内实现 `read_file`, `search_files`, `terminal` 工具，供 Agent 调用
4. **任务处理完**写入 outbox，移动任务文件到 `inbox/done/`

#### 任务格式
```json
// inbox/task_xxx.json
{
  "id": "task_xxx",
  "prompt": "让 Worker 做的事情",
  "created_at": "2026-04-29T12:00:00"
}
```

#### 已知坑

| 坑 | 原因 | 解法 |
|----|------|------|
| `hermes version` 输出被 TTY 吃掉 | stdout 被截断 | 用 `bash -c "hermes version 2>&1"` 包裹 |
| hermes update 没有 preview 命令 | 无此功能 | `hermes backup` 备份后再升级 |

#### 验证 Worker 状态
```bash
ps aux | grep hermes | grep -v grep   # 确认进程存在
cat ~/.hermes/gateway_state.json        # gateway_state 应为 running
lsof -p $(pgrep -f hermes-gateway) -i -P -n | grep LISTEN  # 确认监听端口
```

---

## §C — GitHub 项目研究技巧

> 当需要研究一个 GitHub 项目时，优先用 GitHub API 而不是 web search。Web search 结果经常被污染（如 "crshdn mission-control" 搜到的是 eslintrc.json 元数据和百度百科相关内容）。

### 可靠的 GitHub 调研路径

```bash
# 1. 项目概览（stars/language/description/最后更新时间）
curl -s https://api.github.com/repos/{owner}/{repo}

# 2. README 全文
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"

# 3. 目录结构
curl -s "https://api.github.com/repos/{owner}/{repo}/contents/"

# 4. 最新 release
curl -s "https://api.github.com/repos/{owner}/{repo}/releases/latest"

# 5. 关键文档（如 ORCHESTRATION.md, AGENTS.md）
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/main/{doc_name}"
```

### 调研顺序原则
1. GitHub API（快、准、无污染）→ 2. 读 README/关键文档 → 3. Web search（补充背景）→ 4. 实际部署测试

### 重要发现：crshdn/mission-control (Autensa)

**项目名**: Autensa（crshdn/mission-control）
- **定位**: 全球首个自主产品引擎（APE），AI 自动完成调研 → 创意生成 → Swipe 审批 → 代码构建 → PR
- **架构**: Next.js + SQLite + OpenClaw Gateway（WebSocket）
- **核心功能**: Autopilot / Convoy Mode（多Agent并行DAG）/ Operator Chat / Crash Recovery / 成本追踪 / Knowledge Base / Workspace 隔离
- **Stars**: 1974，v2.5.1（2026-04-29），MIT
- **对比 builderz-labs**: Autensa 面向代码研发全链路自动化；builderz-labs 更通用
- **对 Gu 的价值**: 提供了多Agent编排平台的完整实现参考（特别是 Convoy Mode + Crash Recovery 的组合）

---

## §D — Autensa (crshdn/mission-control) 部署指南

> 部署前先确认端口占用：4000（Autensa）、18789（OpenClaw Gateway）
> 与 Hermes/皮尔洛机器人完全不冲突。完整配置见 `references/autensa-deployment-configs.md`

### 部署顺序

**Step 1: 安装 OpenClaw Gateway**
```bash
npm install -g openclaw
```

**Step 2: 配置 OpenClaw（关键坑）**
- Token 路径是 `gateway.auth.token`，不是 `gateway.token`
- 错误配置会导致 `Config valid` 但 Gateway 实际无法认证
```json
// ~/.openclaw/openclaw.json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "auth": {
      "token": "<openssl rand -hex 32 生成>"
    }
  },
  "secrets": {
    "providers": {
      "anthropic": { "source": "env", "allowlist": ["ANTHROPIC_API_KEY"] },
      "minimax-cn": { "source": "env", "allowlist": ["MINIMAX_CN_API_KEY"] }
    }
  }
}
```
- 验证配置：`openclaw config validate`
- 启动 Gateway：`openclaw gateway run`（前台）或 `openclaw gateway start`（daemon）
- 健康检查：`openclaw gateway health`

**Step 3: 克隆并配置 Autensa**
```bash
cd ~
git clone https://github.com/crshdn/mission-control.git
cd mission-control
cp .env.example .env.local
```
编辑 `.env.local`：
```env
PORT=4000
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=<上面生成的 token>
MC_API_TOKEN=local_<openssl rand -hex 16>
WEBHOOK_SECRET=local_<openssl rand -hex 16>
```

**Step 4: 安装依赖并启动**
```bash
cd ~/mission-control
npm install
npm run dev
```

**Step 5: 验证部署**
- Autensa 健康检查（无需认证）：`curl http://localhost:4000/api/health`
- API 调用（需认证 Header）：`-H "Authorization: Bearer <MC_API_TOKEN>"`
- Gateway 健康检查：`openclaw gateway health`
- 查看可用模型：`OPENCLAW_GATEWAY_TOKEN=<token> openclaw capability model list`

### 关键坑

| 坑 | 原因 | 解法 |
|----|------|------|
| `gateway.token` 配置无效 | OpenClaw 新版路径是 `gateway.auth.token` | 用 `openclaw config validate` 验证 |
| Autensa API 返回 401 Unauthorized | MC_API_TOKEN 未设置或 Header 格式错误 | 用 `Authorization: Bearer <token>` |
| Autensa WebSocket 连接失败 | Gateway 未启动或 Token 不匹配 | 先确认 `openclaw gateway health` |
| Autensa 模型列表为空 | OpenRouter Token 未配置或 MODEL_DISCOVERY=local | 检查 `.env.local` 中 OpenClaw Gateway 连接状态 |
| 模型列表有 OpenRouter 模型但实际调用失败 | OpenRouter Token 未配置 | 在 OpenClaw 配置 OpenRouter API Key |

### MiniMax 在 Autensa 中的可用模型
通过 OpenRouter provider 发现：
- `MiniMax-M2.7` | `minimax-cn`
- `MiniMax-M2.7-highspeed` | `minimax-cn`

Autensa 的 AI Provider 选择在**产品级别**设置，不在全局配置。

---

## §E — Agent Web Research 工具链（四层架构）

> 当 Agent 需要从网页采集信息时，不要只依赖基本 curl/grep。以下是四层递进工具链，按「可用性优先」原则选择。

### 发现路径：npm CLI 代替浏览器搜索

当 Chrome CDP 不可用（浏览器工具无法连接）时，通过 npm CLI 发现和评估工具：

```bash
# 搜索工具
npm search <keyword>

# 查看 README
npm view <package-name> readme

# 查看元数据（版本、依赖、关键词、仓库）
npm view <package-name>

# 查看仓库链接
npm view <package-name> repository
```

优势：无需浏览器、无需登录、结果结构化、速度快。

### 四层工具链

| 层 | 工具 | 定位 | 适用场景 |
|----|------|------|----------|
| **L1** 公开网页 | **Trafilatura** (`trafilatura`, Python) | 正文提取 CLI，0.07s | 新闻/博客/百科等无登录网页；搜索层用 DuckDuckGo Search |
| **L2** 平台API | **AutoCLI** (`@vk007/autocli`) | 119 providers 的终端统一入口 | 有 API 或 CLI 的平台（GitHub, X, LLM） |
| **L3** 去中心化Agent | **Agent-Reach** (`openclaw-agent-reach`) | Nostr 网络 Agent 发现 | 需要发现/调用其他 Agent |
| **L4** 浏览器即API | **bb-browser** (`bb-browser`) | 复用真实 Chrome 登录态，126 个社区 adapter | 无 API / 反爬 / 复杂登录的平台 |

### L2 — AutoCLI (`autocli`)

**仓库**: https://github.com/vkop007/autocli
**安装**: `npm install -g @vk007/autocli` 或 `bun install -g @vk007/autocli`

核心能力：
- **108 providers**, 14 分类（llm, social, developer, devops...）
- 共享浏览器 profile：`autocli login --browser` → 一次登录全复用
- 全部支持 `--json` 输出，对 Agent 友好
- Bun 构建，依赖 Playwright-core + WhatsApp Baileys + Telegram
- 常见平台：GitHub, X/Twitter, Qwen, Reddit, Jira

典型流程：
```bash
autocli login --browser                          # 初始化共享浏览器
autocli developer github login --browser         # 登录 GitHub
autocli social x login --browser                 # 登录 X
autocli developer github me --json               # 免密使用
autocli social x post "Title"                    # 发帖
autocli llm qwen text "prompt"                   # 调 LLM
```

### L4 — bb-browser (`bb-browser`)

**仓库**: https://github.com/epiral/bb-browser
**生态 (社区 Adapter)**: https://github.com/epiral/bb-sites
**安装**: `npm install -g bb-browser`

核心理念：**Your browser is the API.** 在真实 Chrome tab 内执行 eval/fetch，带上 cookies，网站以为就是你。

优势对比：
| | Playwright/Selenium | 采集库 | bb-browser |
|---|---|---|---|
| 浏览器 | 无头、隔离 | 无浏览器 | 你的真实 Chrome |
| 登录态 | 无，需重登 | Cookie 提取 | 已有 |
| 反爬 | 易检测 | 猫鼠游戏 | 不可见（就是用户本人） |

能力：
- **103 个命令**，覆盖 **36 个平台**（Twitter, 知乎, B站, 小红书, YouTube, GitHub, Reddit, 雪球, BOSS直聘, arXiv...）
- 支持 **MCP Server** 模式 → 直接接入 Claude Code / Cursor
- 支持 **OpenClaw 模式**：`bb-browser site reddit/hot --openclaw`
- 社区驱动，Adapter 在 bb-sites 仓库

示例：
```bash
bb-browser site twitter/search "AI agent"        # 搜推文
bb-browser site zhihu/hot                        # 知乎热搜
bb-browser site youtube/transcript VIDEO_ID      # YouTube 字幕
bb-browser site reddit/hot --openclaw            # OpenClaw 模式
```

MCP 配置 (Claude Code / Cursor)：
```json
{
  "mcpServers": {
    "bb-browser": {
      "command": "npx",
      "args": ["-y", "bb-browser", "--mcp"]
    }
  }
}
```

### L3 — Agent-Reach (`openclaw-agent-reach`)

**安装**: OpenClaw 插件，从 `~/.openclaw/extensions/agent-reach/`
**依赖**: Nostr 频道配置

核心能力：
- Service Card 发布到 Nostr 网络 (kind 31990)
- 心跳检测 (kind 31991)
- 按能力发现 Agent：`discover_agents({ capability: "coding" })`
- 动态更新：`update_service_card({ capabilities: [...] })`，免重启

同一生态工具：**`xreach-cli`** — X/Twitter 专用 CLI

### 安装验证（各工具当前状态）

```bash
# L1 — Trafilatura (已安装 v2.0.0)
trafilatura --version

# L2 — AutoCLI (已安装 v0.1.3)
autocli --version
autocli doctor

# L4 — bb-browser (已安装 v0.11.3)
bb-browser --version
bb-browser site update   # 首次需拉取社区 adapter
bb-browser site list     # 查看可用 adapter

# Agent-Reach 是 OpenClaw 插件，通过 OpenClaw 管理
```

### 选择策略

```bash
有登录态需要复用  → bb-browser 优先          # 小红书/B站/知乎/微博…
有 API/CLI 可调   → AutoCLI 优先             # GitHub/X/Reddit/LLM…
需要发现其他 Agent → Agent-Reach             # Nostr 网络
纯公开网页         → Trafilatura (推荐)       # 新闻/博客/百科
竞品情报搜索       → 百度浏览器搜索            # 中国品牌营销动态
```

---

## §F — 竞品情报研究：浏览器搜索法

> 当需要搜集中国品牌的当前营销动作（如蒙牛/伊利的世界杯营销活动），使用百度搜索 + 浏览器点击阅读全文，而不是依赖 web_search 工具（如果不可用）。

### 工作流

```text
用户指令 (如 "搜集蒙牛和伊利关于世界杯的营销动作")
  │
  ├─ Step 1: 5维并行搜索（优于逐个搜索）
  │   同时打开多个搜索标签页，覆盖以下维度：
  │   ① 品牌直接搜索："懂球帝 品牌 营销 产品 最新"
  │   ② 行业趋势："体育营销 2026 最新 足球"
  │   ③ 赛事专题："世界杯 营销 最新 2026"
  │   ④ 竞品动态："足球APP 竞品 直播吧 虎扑 最新动态"
  │   ⑤ 行业投融资："体育互联网 行业 投融资 2026"
  │   注意：URL 需要手动 URL encode 中文；并行 browser_navigate 效率最高
  │
  ├─ Step 2: 阅读搜索结果页面，识别关键文章
  │   browser_snapshot() 查看结果列表
  │   优先阅读：品牌官网、新华网/海报新闻等正规媒体、行业分析文章
  │   注意：搜索"大家还在搜"区域提示了用户真实需求
  │   注意：百度搜索结果中可能包含 AI 摘要（标注"AI导读"），内容需核实
  │
  ├─ Step 3: 深入阅读关键文章
  │   browser_click(ref='@eXX') 点击文章链接
  │   browser_snapshot(full=true) 获取全文
  │   注意：很多文章需要多次 snapshot 才能看完（百度页面截断）
  │   常见坑：点击搜索结果链接后可能被重定向到 Baidu 的信息聚合页
  │         → 解法：重新在搜索结果页找下一个可信来源的链接，或换关键词搜该文章标题
  │
  ├─ Step 4: 多轮搜索（细化方向）
  │   根据第一步结果中的新发现，做二次搜索
  │   例如：从"蒙牛世界杯版权僵局"发现新数据 → 专门搜该方向获取更多信源
  │
  ├─ Step 5: 交叉验证
  │   多个来源交叉验证同一事实（如版权报价数字）
  │   注意区分：AI生成内容、自媒体观点 vs 官方媒体
  │   交叉验证技巧：同一事件找 3+ 独立来源（正规媒体 > 行业媒体 > 自媒体）
  │
  └─ Step 6: 汇编报告 → 按简报模板输出
```

### 扩展：Cron Job 情报自动化模式（H 情报官）

当本流程作为 Cron Job 定时执行（无用户交互）时，工作流自动化为以下模式：

```text
Cron 触发
  │
  ├─ Step 1: 5维并行搜索（与上述 Step 1 相同）
  │   自动发起 5 个 browser_navigate 调用
  │   不等待，全部并行发出
  │
  ├─ Step 2: 结果扫描与筛选
  │   每个搜索结果页用 browser_snapshot() 获取快照
  │   自动识别关键文章：优先选品牌/平台原创、正规媒体、行业垂直媒体
  │   原则：筛出 3-5 条最有价值的情报
  │
  ├─ Step 3: 深入阅读（自主决策）
  │   无需用户确认，直接点击最有价值的文章
  │   用 browser_snapshot(full=true) 获取全文
  │   注意文章可能被 Baidu 重定向 → 换来源
  │
  ├─ Step 4: 自主判断
  │   - 所有信息必须标注来源链接 + 时间 + 可信度
  │   - 重复情报不推送，除非出现新数据
  │   - 无有价值情报时输出 "[SILENT]"（静默模式）
  │
  └─ Step 5: 按简报模板自动输出
       Cron 的最终输出会被自动投递到斯塔姆群
       不要额外调用 send_message
```

### 百度搜索结果页解析要点

- 使用 `browser_snapshot()` 获取页面快照，重点关注 `<heading>` 元素内的标题和 `<link>` 内的链接
- 结果的 ref 编号（如 `@e40`、`@e42`）就是可点击的链接
- 不要被"相关搜索"区域分散注意力，但留意它揭示的用户搜索模式
- 搜索结果通常只显示前 10 条，需要翻页可通过 `browser_click(ref='@e17')` 点击"下一页"

### 页面内容获取注意事项

- `browser_snapshot(full=false)`（默认）会截断内容 — **使用 `full=true` 获取完整内容**
- 大量长文章时 snapshot 可能仍被截断（如文章有 400+ 行被 truncate）— 需要多读几个来源交叉补充
- 注意百度搜索结果页中的**AI 摘要**（标注"AI导读""内容由AI智能生成"）— 内容可能不精确，需核实
- 标注"作品含AI生成内容"的文章权威性低，优先读正规媒体

### 竞品情报报告结构（可复用模板）

```markdown
# <品牌A> vs <品牌B>：<赛事>营销动作梳理

> 搜集时间：<日期>
> 数据来源：<来源清单>

## 一、行业背景

赛事/活动概况、关键信息、重大不确定性

## 二、品牌A：<定位描述>

### 2.1 整体战略
预算规模、赞助级别、核心主张

### 2.2 营销动作清单
按时间线或活动类型列出，每条包含：
- 活动名称/类型
- 时间
- 合作方
- 形式（TVC/线下/跨界/社交）
- 目标人群

### 2.3 风险/挑战

## 三、品牌B：<定位描述>

（同上结构，注意两者策略对比）

## 四、对比分析表

| 维度 | 品牌A | 品牌B |
|------|-------|-------|
| 官方身份 | ... | ... |
| 预算规模 | ... | ... |
| 核心策略 | ... | ... |
| 主要风险 | ... | ... |

## 五、对 XX 的启示与机会

## 六、数据来源

- 百度搜索公开结果
- <具体文章来源>
```

### 实测数据（2026-05-05 蒙牛vs伊利世界杯营销）

| 指标 | 数据 |
|------|------|
| 搜索轮次 | 7 次（蒙牛3次 + 伊利2次 + 容声1次 + 通用1次） |
| 深入阅读文章 | 3 篇（广告门方法论、版权争端、容声×蒙牛） |
| 关键发现数 | 蒙牛8项活动 + 伊利4项策略 + 1个重大风险（版权僵局） |
| 报告大小 | ~8.7KB |
| 关键信息来源 | 海报新闻、百度百家号、禹唐体育、蒙牛官网 |

### 局限性和注意事项

- **这种方法只能找到已发布的公开信息** — 品牌未公布的策略无法获取
- **百度搜索排序受竞价影响** — 前几条可能是广告，往下翻找正规新闻
- **自媒体文章可靠度低** — 优先选品牌官网、央媒、行业垂直媒体
- **版权/合同细节无法确认** — 金额多为行业推测而非官方确认

### 通用性说明

这四个工具都是**通用 CLI 工具**，不绑定任何特定 Agent。Hermes 可用 `terminal()` 调用，Claude Code / Cursor 可在终端直接使用，bb-browser 还支持 MCP Server 模式零配置接入。

详细调研记录见 `references/web-research-toolchain-discovery.md`。

---

## §H — Profile-Based Multi-Bot Isolation (多 Agent 独立上下文)

> 适用场景：只有一个飞书 Bot，但需要多个独立 Agent 上下文（如全栈总控 + 纯编码助手），且不想在同一个会话里串上下文。

### 问题背景

Hermes Feishu 适配器目前是**单 Bot 模式**（`feishu.py` 第 40 行注释）。一个飞书 Bot = 一个 gateway 连接 = 一个会话上下文。如果所有任务都走同一个 Bot，主控和编码/营销任务的会话历史会互相污染。

### 方案：Hermes Profiles

Hermes 原生支持 Profiles，每个 profile 是一个完全独立的 Hermes Agent：

```bash
# 创建 profile（--clone 复制主配置，省去重配 API key）
hermes profile create pirlo --clone

# 起第二个 gateway（绑定不同飞书 bot）
pirlo gateway
```

每个 profile 拥有自己独立的：

| 组件 | 主控 Hermes | pirlo profile |
|------|-------------|---------------|
| 飞书 Bot | 马蒂尼 app_id/secret | 皮尔洛 app_id/secret |
| config.yaml | 全栈 system prompt | 纯编码 system prompt |
| .env | 马蒂尼凭据 | 皮尔洛凭据 |
| SOUL.md | 总助人格 | 编码助手人格 |
| ~/.hermes/skills/ | 主控白名单 ~10 个 | 仅 coding skills |
| sessions/ | 全栈对话历史 | 纯编码对话历史 |
| memories/ | 全栈记忆 | 编码专用记忆 |

### 创建步骤

```bash
# 1. Clone 主配置文件
hermes profile create pirlo --clone

# 2. 换飞书 Bot 凭据
# ~/.hermes/profiles/pirlo/.env
# FEISHU_APP_ID=皮尔洛的app_id
# FEISHU_APP_SECRET=皮尔洛的app_secret

# 3. 换系统提示词
# ~/.hermes/profiles/pirlo/config.yaml 中修改 feishu.feishu_system_prompt

# 4. 裁剪 skills（只保留编码相关）
# 在 pirlo profile 的 skills/ 下只放 coding skills

# 5. 启动
pirlo gateway
```

### 与 Agent-Scoped Skills 的关系

两者是互补而非替代关系：

| 维度 | Profiles（多 Bot） | Agent-Scoped Skills（单 Bot 内） |
|------|-------------------|--------------------------------|
| 上下文隔离 | 完全独立（不同会话、不同记忆） | 共享上下文，仅 skill 不同 |
| 用户使用 | 飞书里两个不同联系人 | 同一个人，slash 命令切换 |
| 实现复杂度 | 开箱即用（`hermes profile create`） | 需改源码（skill_commands.py + delegate_tool.py） |
| 部署成本 | 多一个飞书 Bot（需申请权限） | 无需额外 Bot |
| 适用场景 | 上下文需要完全隔离（如工作/个人） | 上下文可共享但功能要分流 |

### 推荐策略

```
只有一个飞书 Bot
  ├─ 上下文污染不明显 ──→ 先用 slash 命令 + channel_skill_bindings 分流
  └─ 上下文污染严重 ──→ 建第二个 Profile + 第二个飞书 Bot
       ├─ 原始仓库克隆链接可以用 https://github.com/pingan8787/image2prompt.git
       └─ 等实现 Agent-Scoped Skills 后可以合并回单 Bot
```

## §I — 多 Agent 团队架构设计（2026-05-12 最终锁版）

> 适用场景：设计或讨论 Agent 团队分工，决定每个 Agent 的角色、模型、skillset、通信方式。

### 架构原则

1. **角色优先，再配 Agent** — 先搭角色框架，再根据角色要求选 Agent。不要跳步。每确认一个角色就固定下来，不再重复讨论。
2. **角色分工铁律 — 已被区分出去的角色绝不合并回去** — 当用户表达了明确的角色分工意愿后，任何试图合并/缩编角色的建议都会引起用户不满。如果某个角色功能有重叠，重新分配职责（如 OpenClaw 从 C 桌面操作员改为 E+H 双角色），而不是把角色删掉合并给别人。**"我目的是分工"** 是用户的明确诉求。
3. **先定灵魂（soul/persona），再配技术** — 每个角色必须先定义人格定位、性格特点、工作习惯、边界范围，再去配置 Agent 和模型。灵魂定义是技术落地的前置步骤，不能跳过或想当然自行添加。
4. **总控（Coordinator）+ 专家（Specialist）** — 一个总控 Agent（马蒂尼）负责日常沟通、意图理解、任务分配；专业任务派给对应的专家 Agent。
5. **上下文隔离** — 每个 Agent 独立的会话、记忆、skills，不跨 Agent 污染上下文。
6. **摘要汇报，记忆不膨胀** — 子 Agent 干完活，总控只记结果摘要，不记执行过程。追问时知道找谁补细节。
7. **参考架构：三省六部制 (edict)** — 开源项目 `github.com/cft0808/edict`（15.7k star）是一个基于 OpenClaw 的多 Agent 编排系统，采用唐代三省六部制架构。完整研究笔记见 `references/edict-architecture-notes.md`。

### 最终角色框架（8 角色确认锁版）— 已全部实现 ✅

| 角色 | 用户名 | Agent | 模型/工具 | 职责 | 通信方式 | 状态 |
|------|-------|-------|-----------|------|---------|------|
| **A 总助** | 马蒂尼 | Hermes | DeepSeek V4 Flash | 任务判断、分派、协调、轻量读取 | 马蒂尼 DM（用户对话入口） | ✅ 已运行 |
| **B 技术专员** | 内斯塔 | `agent_id='nesta'` | DeepSeek V4 Pro（预处理）→ Claude Code（执行） | 技术任务预处理+复审，delegate 给 Claude Code 执行编码 | 马蒂尼 delegate | ✅ 已注册 named agent，含 soul 人格 |
| **C 桌面操作员** | — | `agent_id='agent-tars'` | DeepSeek V4 Pro（视觉模型，CLI 参数配） | macOS 桌面操作、截图、打开 App | 马蒂尼 delegate（`agent-tars run --headless --input ... --format json`） | ✅ 已注册 named agent，CLI 已安装 |
| **D 代码审查员** | — | `agent_id='codex'` | default（继承父级） | 审查代码、评审方案、质量把关 | 马蒂尼 delegate | ✅ 已修正（type: code_reviewer，去掉 file_modification）|
| **E 调研专员** | — | `agent_id='openclaw'` | zai/glm-5-turbo（Chrome + DuckDuckGo） | 信息搜集、网页浏览、竞品调研、资料整理（不做分析） | 马蒂尼 delegate | ✅ 已修正（type: researcher，路由从桌面操作改为调研）|
| **F 方案策划** | 皮尔洛 | `agent_id='pirlo'` | DeepSeek V4 Pro | 基础方案框架、卖点提炼、竞品对比、排期初稿 | 马蒂尼 delegate 或用户直接 | ✅ 已注册 named agent，含 soul 人格 |
| **G 质量审核角色（安布罗西尼）** | 安布罗西尼 | `agent_id='hermes-internal'` | DeepSeek V4 Pro，type: quality_gate | 把关复杂任务质量（审方案逻辑、情报准确性、代码安全） | delegate_task （内部质检，非独立 Bot） | ✅ 已运行，2026-05-13 更名为安布罗西尼
| **H 情报官** | — | `agent_id='openclaw'`（E 同实例）+ cron | zai/glm-5-turbo | 定时监控、竞品跟踪、情报简报推送至斯塔姆群（与 E 共用同一 OpenClaw 实例） | 后台独立运行 + cron（每天 09:00 首推） | ✅ cron 已创建，推斯塔姆群 |

**关键说明：**
- **A 总助**已锁版，不再讨论。后续所有角色讨论以 A 已确认为前提推进。
- **B 技术专员**：内斯塔负责「预处理 + 复审」，Claude Code 负责「最后一公里编码」。预处理=搜项目结构、定位文件、理解模糊需求；复审=检查输出质量。这个决策是在用户承认「不熟悉编程，给的需求一定不清晰」的背景下做出的——中间层在非技术用户场景下价值最大。
- **C 桌面操作员**：Agent TARS 通过 headless 模式 + JSON 输出与 Hermes 集成。详见 `references/agent-tars-integration.md`。OpenClaw 因桌面操作「不好用」被重新定位。
- **D 代码审查员**：codex 已有且 active，直接采用。
- **E 调研专员**：OpenClaw 重新定位为调研专员。利用其 Chrome 浏览器操控+DuckDuckGo 搜索+Canvas UI 生成的长板做信息搜集，避开桌面操作交互不好的短板。与 H 情报官共用同一 OpenClaw 实例。\n- **F 方案策划**：皮尔洛待创建 named agent。DeepSeek V4 Pro 做基础方案工作（框架、卖点提炼、竞品对比、排期初稿），用户核心创意走 ChatGPT 网页版。\n- **G 审核角色**：hermes-internal 已有且 active，read-only 模式适合质检。\n- **H 情报官**：OpenClaw 从 C 桌面操作员改为 H 情报官。与 E 调研专员共用同一 OpenClaw 实例。利用 Chrome 浏览器操控+Canvas UI 生成+独立后台进程的长板做情报监控。
- **推送渠道**：所有 cron 推送（早报、竞品监控等）走斯塔姆群（设为 home channel），不干扰马蒂尼 DM。

### 角色定义工作流

（同旧版，保留不变）

### 角色定义工作流

当需要为新团队角色定义灵魂（soul/persona）时，按以下顺序推进：

1. **起草定位** — 先写初稿，涵盖：角色定位、性格特点、工作习惯、能力边界
2. **用户细调** — 用户过目后逐条确认/修改，一个角色一个角色过
3. **锁版** — 双方确认后即固定，不再回归讨论
4. **再配技术** — 灵魂确认后，再去配置 Agent 注册表、模型、profile

**禁止偷步**：不要在用户未确认前自行添加用户没说的性格特征或工作习惯。灵魂定义必须经过用户过目和确认。

每个角色灵魂定义应包含：

```markdown
**定位：** 一句话说明这个角色是干什么的
**性格：** 2-3 个关键词 + 一句话解释
**工作习惯：** 3-5 条具体做事方式
**边界：** 明确写清这个角色不做什么
```

### 任务分级框架

马蒂尼（总助）遇到任务时，按以下 4 个维度判断难度级别：

| 维度 | 简单 | 中等 | 复杂 |
|------|------|------|------|
| **动作类型** | 读文件、搜网页、查知识库、问答 | 写方案、改文案、写代码、改配置 | 重要方案、跨部门任务 |
| **步骤数** | 1-2 步 | 3-5 步 | 5+ 步 |
| **风险** | 无风险（读操作） | 有风险（写操作） | 高风险（改系统配置、删文件） |
| **是否需要看成品** | 不需要 | 直接看 | 需要确认方向再动手 |

**对应处理方式：**
```
简单 → 马蒂尼自己处理
中等 → delegate 给对应角色直接执行
复杂 → 先规划 → 可选审核 → 执行 → 汇报摘要
```

> **原则**：不在规则上内耗。判断错了不致命，顶多多走一步，下次调整。判断框架给马蒂尼的 prompt 足够用。

### 记忆策略

- 马蒂尼只存**结果摘要**，不存执行日志
- 追问时知道找谁补细节
- 各子 Agent 执行过程的"脏东西"不进入马蒂尼的上下文

### edict (三省六部制) 参考映射

| 你的角色 | edict 三省对应 | edict 六部对应 |
|---------|---------------|---------------|
| 你 | **皇上** — 下旨 | — |
| A 总助 | **太子** — 分拣/闲聊直回 | — |
| F 方案策划 | **中书省** — 规划方案 | — |
| （缺审核角色） | **门下省** — 审议/封驳 | — |
| E 通用执行器 | **尚书省** — 派发/协调 | — |
| B 技术专员 | — | **兵部** — 代码实现 |
| C 桌面操作员 | — | **工部** — 基建操作 |
| D 代码审查员 | — | **（兵部内审+门下省外审）** |

### 通信模式

**同 gateway 内（马蒂尼 → 子 Agent）：**
- `delegate_task(agent_id='...', goal=..., context=...)` — 标准子 Agent 派发
- 上下文隔离（子 Agent 独立会话），父 Agent 只看结果摘要

**跨 gateway（马蒂尼 ↔ 皮尔洛 两个独立 Profile）：**
- 皮尔洛 profile 启动 api_server（OpenAI 兼容接口）
- 马蒂尼通过 HTTP/curl 调皮尔洛的处理能力
- 互不共享 memory/session，通过 HTTP 请求传递上下文
- 皮尔洛也可以有自己的飞书 Bot，用户能直接找他

### Agent Middleman 决策模式（新增 §J）

**场景**：CoS（马蒂尼）要派一个技术任务给执行者（如 Claude Code），是否需要在中间加一个中间层 Agent（如内斯塔/皮尔洛）？

**决策框架**：

```
马蒂尼收到技术任务
  │
  ├─ 直接委托：马蒂尼 → delegate(agent_id='claude') → 执行
  │   ✅ 最直接，一步到位
  │   ❌ Claude Code 每次全新会话，不做预处理
  │   ❌ 没有复审，结果直接返回
  │
  └─ 经过中间层：马蒂尼 → delegate(agent_id='nesta')
                   → 内斯塔预处理 + 复审 → delegate(agent_id='claude')
                   → 内斯塔审核 → 返回
      ✅ 预处理：搜文件、理解上下文、整理好再交给执行者
      ✅ 复审：执行者干完活，中间层先看质量把关
      ✅ 长期记忆：中间层记住项目偏好、常见坑、用户要求
      ❌ 多一层，增加开销和延迟
```

**判断标准**：

| 维度 | 直接委托 | 经过中间层 |
|------|---------|-----------|
| 任务类型 | 改已有代码、跑脚本、修已知 bug | 新项目调研、排查复杂问题、写大块代码 |
| 是否需要先了解背景 | 用户已说清楚，不需要预处理 | 需要先翻文件、看历史、理解项目结构 |
| 输出风险 | 低（改一行、跑个命令） | 高（可能破坏结构/引入 bug） |
| 用户与技术执行者的熟悉度 | 很熟（直接说就行） | 不太熟（需要中间层消化用户习惯） |

**如果中间层不能加值，就不要加。** 中间层必须有明确的增值点（预处理/复审/记忆积累），否则只是多一层传话。

**真实案例（2026-05-12 讨论）**：内斯塔（B 技术专员）是否应该作为 Claude Code 的中间层？用户承认「没想明白」。这个讨论本身就是典型案例——当中间层的增值点不明确时，先直接委托，后续如果需要预处理/复审再引入中间层。

**铁律**：这个决策不需要一次想明白。先走直接委托，当出现「每次都要重新说明上下文」「Claude Code 结果需要人检查才放心」时，再引入中间层。

### Profiles 详细配置

```bash
# 创建 profile（从主配置克隆）
hermes profile create pirlo --clone

# 皮尔洛的 .env — 换飞书 Bot 凭据
# FEISHU_APP_ID=皮尔洛的app_id
# FEISHU_APP_SECRET=皮尔洛的app_secret
# FEISHU_DOMAIN=feishu

# 起第二个 gateway
pirlo gateway
```

> ⚠️ **Profile 克隆后必须检查的陷阱**：
> 1. `feishu_system_prompt` 会被克隆（源人格覆盖新人格）→ 必须修改
> 2. `api_server` 端口冲突（默认 8642）→ 纯飞书 Bot 建议 `API_SERVER_ENABLED=false`
> 3. `channel_skill_bindings` 也会被克隆 → 删除无关绑定
> 4. `skills/` 目录有 150+ 无关技能 → 需按角色裁剪
> 5. OpenClaw 可能还连着该 Bot → 先禁掉 OpenClaw 频道
>
> 完整清单见 `hermes-subagent-delegation` skill 的「Profile 部署后检查清单」。

## 为 Agent 创建独立 Profile 的完整步骤

当用户希望 Agent 在飞书上有独立 Bot 并拥有自己的 persona 时（路径 B：独立 Gateway + SOUL.md），走以下流程：

### Step 1: 创建 Profile

```bash
hermes profile create {agent_name} --clone
```

这会创建 `~/.hermes/profiles/{agent_name}/`，包含克隆自 default 的：
- `config.yaml`，`.env`，`SOUL.md`，`skills/`
- 创建一个 wrapper 命令：`~/.local/bin/{agent_name}`

### Step 2: 编写 SOUL.md

```markdown
# {Agent名称} SOUL

## 身份
我是{Agent名称}，懂球帝多 Agent 团队的{角色}。{一句话描述核心职责}。

## 工作习惯
- {习惯 1}
- {习惯 2}
...

## 边界
- {不做什么 1}
- {不做什么 2}
...
```

### Step 3: 配置飞书 Bot 凭据

编辑 `~/.hermes/profiles/{agent_name}/.env`：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

**⚠️ app_secret 获取陷阱：**
- macOS Keychain 存的 secret 从命令行读不到（`security find-generic-password` 返回 item not found）
- 飞书开放平台的复制按钮会触发 browser clipboard write，但 browser JS 读 clipboard API 会被沙箱拦截（timeout）
- **最可靠方法**：让用户在飞书开放平台手动复制，粘贴给你

### Step 4: 启动 Gateway

```bash
{agent_name} gateway start       # 后台
# 或
{agent_name} gateway run --replace  # 前台替换
```

### Step 5: 验证

```bash
ps aux | grep "hermes.*profile.*{agent_name}" | grep -v grep
# 在飞书 DM 该 Bot 验证人格
```

### 马蒂尼的能力边界速查

| 操作 | 自留还是派出去 | 给谁 |
|------|--------------|------|
| 读文档/文件 | ✅ 自留 | — |
| 搜索/查资料 | ✅ 自留 | — |
| 日常对话 | ✅ 自留 | — |
| 管理记忆/待办 | ✅ 自留 | — |
| 派活 delegate_task | ✅ 自留 | — |
| 写文件/改代码 | ❌ 派出去 | 皮尔洛 / Claude / deepseek-tui |
| 执行终端命令 | ❌ 派出去 | 皮尔洛 / Claude |
| 桌面操作/截图 | ❌ 派出去 | OpenClaw |
| 代码审查 | ❌ 派出去 | Codex |
| 修改系统配置 | ❌ 派出去 | 皮尔洛 + 任务卡 |
| 深度调研（5+步）| ❌ 派出去 | Hermes 通用执行 |

- 每个 profile 需要独立的飞书自建应用（申请 10-15 分钟，权限配置 5 分钟）
- 多 gateway 进程增加内存和 CPU 开销（~500MB+ RAM / 额外进程）
- Profiles 之间不能共享记忆（如需共享需主动通过文件传递）
- 当前 Hermes Feishu 适配器不支持单 Bot 多上下文隔离（feishu.py 明确标注 "single-bot mode"）

### 现有基础设施参考

- `~/.hermes/hermes-agent/website/docs/user-guide/profiles.md` — Hermes Profiles 官方文档
- `~/.hermes/config/agent-registry.json` — 每个 agent 的 subagent_profile 配置
- `config.yaml` 中的 `channel_skill_bindings` — 已实现频道级 skill 绑定

---

## §J — 多Agent架构全链路测试协议

> 适用场景：部署或修改多Agent架构后，需要系统性验证所有角色是否功能正常、人格正确、链路通畅。

### 测试设计原则

1. **并行优先** — 独立 Agent 的测试任务并行派发（max_concurrent_children=3），减少总耗时
2. **分批递进** — 先测纯分析型 Agent（无副作用），再测需要外部资源（web/桌面）的 Agent
3. **人格验证** — 每个 Agent 的测试任务必须包括自我介绍，验证 soul 人格注入正确
4. **日志交叉检查** — 功能测试后扫 gateway 日志，定位隐性错误（断连、权限、超时）
5. **结果可追溯** — 每个子测试记录 agent_id、耗时、tokens、exit_reason、发现的异常

### 测试批次安排

```
批次 1（分析型，并行）→ 技术审计/代码审查/质量审核
  内斯塔(B) + Codex(D) + hermes-internal(G)

批次 2（内容型，并行）→ 方案策划/调研/桌面操作
  皮尔洛(F) + OpenClaw(E) + Agent TARS(C)

批次 3（基础设施验证）→ H 情报官 cron 手动触发 + gateway 日志扫描
```

### 每轮测试模板

```python
delegate_task(
    agent_id='<agent_id>',
    goal='<让 agent 展示其核心能力的任务，必须包含自我介绍>',
    context='<语言偏好、输出格式要求>'
)
```

### Agent 验证检查表

| Agent | 验证项 | 通过标志 |
|-------|--------|---------|
| **内斯塔(B)** | 读文件+结构分析+技术建议 | 回复中自称"B 技术专员"，分析有深度，引用了具体文件内容 |
| **Codex(D)** | Schema 完整性+P0/P1/P2 分级 | 输出按 P0/P1/P2 分级，明确指出缺少 soul 的 agent |
| **hermes-internal(G)** | 架构完整性审核 | 输出明确的「+1 通过」或「打回」结论，理由具体可追溯 |
| **皮尔洛(F)** | 方案框架输出 | 框架结构完整（8 个模块），[待补充] 标注规范，不编造数据 |
| **OpenClaw(E)** | 网页搜索 | 返回结构化结果（来源+摘要），不空跑 |
| **Agent TARS(C)** | 桌面操作 | 能开应用/截图/返回操作日志 |
| **H 情报官 cron** | 手动触发验证 | cron job 的 last_status=ok，内容可推送到飞书 |

### 常见失败模式

#### 1. OpenClaw 搜索超时/低效

**症状**：OpenClaw 用 DuckDuckGo HTML 版本搜索时，终端工具连续超时（`[Command timed out after 30s]`），或搜索转为大规模 shell 管道操作（`curl | python3`）触发安全审批。

**根因**：OpenClaw agent 被配置为 `toolsets: [terminal, file]`，没有 `browser` 或 `web_search` 工具集。它只能通过 shell 调用 `curl` + 手动 HTML 解析来搜索，而不是使用原生的 web_search 工具。

**影响**：一次简单搜索可能消耗 23 次工具调用、67 万输入 tokens、160 秒——效率极低。

**诊断**：
```python
# 检查 tool_trace 中的 terminal 调用次数
result['tool_trace'].count(lambda t: t['tool'] == 'terminal')
# 正常搜索应 3-5 次终端调用，>10 次说明工具链不对
```

**修复方向**：
- 给 OpenClaw 的 subagent_profile 加 `web_search`/`browser` toolsets
- 或通过 Hermes 主控直接用 web_search 工具搜索，把结果传给 OpenClaw 做结构化整理
- 或使用 autocli / bb-browser 等专用 CLI 工具替代 DuckDuckGo 页面爬取

#### 2. DeepSeek API 子Agent 推理超时

**症状**：子 Agent 工具调用执行成功（read_file 返回数据），但在模型生成大输出时中断：`exit_reason: "interrupted"`, `"waiting for model response (X s elapsed)"`。

**特征**：`tokens > 0`（不是 0 tokens 的配错模式），工具调用正常，模型推理阶段超时。

**修复**：换 provider（在 delegation 段改 model/provider）或把数据拆小分批。

详见 `hermes-subagent-delegation` skill 的「子Agent模型推理超时」pitfall。

#### 3. Feishu WebSocket 断连

**症状**：gateway.error.log 中出现 `ERROR Lark: receive message loop exit, err: sent 1011 (internal error) keepalive ping timeout` 或 `Failed to resolve 'open.feishu.cn'`。

**影响**：飞书 Bot 在断连期间不可用，消息丢失或延迟接收。

**诊断**：
```bash
grep -c "keepalive ping timeout" ~/.hermes/logs/gateway.error.log --count
grep -c "Failed to resolve 'open.feishu.cn'" ~/.hermes/logs/gateway.error.log --count
```

**临时缓解**：网关自动重连（日志显示 `trying to reconnect for the Xth time`），但断连窗口内消息丢失。

**根本解决**：DNS 服务器稳定性问题，考虑设本地 DNS 缓存或用 `dnsmasq` 兜底。

#### 4. Gateway 重启 drain 超时

**症状**：日志出现 `Gateway drain timed out after 60.0s with 1 active agent(s); interrupting remaining work.`

**原因**：`hermes gateway restart` 触发时，有活跃 agent 在运行，drain 无法完成。

**影响**：活跃任务被中断，重启后可能丢失状态。

**预防**：使用 `hermes gateway run --replace` 替代 `restart`，不依赖 launchd 生命周期管理。

### 测试完成后产出的报告模板

```markdown
## 📋 全链路测试报告

### ✅ 角色功能测试

| 角色 | 测试内容 | 结果 | 耗时 | 说明 |
|------|---------|------|------|------|
| B 内斯塔 | ... | ✅/❌ | Xs | ... |
| D Codex | ... | ✅/❌ | Xs | ... |
| ... | ... | ... | ... | ... |

### ⚠️ 发现的问题

**P1 — 建议修**
| 问题 | 影响面 | 详情 |
|------|--------|------|

**P2 — 可优化**
| 问题 | 详情 |
|------|------|

### 🔬 日志深层发现
gateway.error.log 输出的关键警告和错误。
```

### 测试实际结果归档

每次全链路测试的结果应存档为 `references/test-run-{YYYY-MM-DD}.md`，包含：
- 各 Agent 的测试摘要
- 发现的异常列表
- 修复/改进建议
- 测试环境状态快照（各服务进程、版本号）

参考文件：`references/test-run-2026-05-13.md` — 首次 8 Agent 全链路测试实录。

---

## §G — Agent 路由决策指南

> Absorbed from `agent-routing-guide` (archived). Use when deciding which agent to delegate a task to.

### 核心原则

1. **先编译意图，再路由** — 用户原话不能直接用于路由决策。先通过 Chief of Staff 理解真实意图，再决定派谁
2. **实时配置和实际验证优先** — 先看当前 agent-registry、工具权限、服务状态；SKILL.md 不硬编码能力矩阵
3. **复杂委托任务走 Task Card** — 多 Agent、长耗时、高风险、需审计的任务传完整 Task Card JSON；简单任务直接执行即可

### 决策树

```
收到任务
  │
  ├─ 0. 查 wiki 手册 —— 如果是架构/系统问题，先查 `个人知识库/3-知识/wiki/AI与Agent/Hermes/多Agent系统接入手册.md`
  │   └─ 手册是优先入口；当手册可能过期、要定位根因或需要验证当前状态时，继续查源码、日志、配置和运行结果
  │
  ├─ 1. 先进行意图编译（Chief of Staff）—— 参考 chief-of-staff SKILL.md
  │   └─ 理解真实意图；只有复杂委托任务才生成 Task Card
  │
  ├─ 需要修改文件？ —— YES → 在 Codex、Claude Code、Hermes 内部或其他可用执行者中选择
  │   └─ 复杂委托的 Task Card 必须包含 allowed_files、compiled_intent.must_avoid
  │
  ├─ 需要搜索/调研/阅读？ —— YES → 选择当前最可靠路径：浏览器、CLI/API、Kimi Agent、web 工具或权威源
  │   └─ 输出应结构化（findings / sources / unknowns）
  │
  ├─ 需要分析/决策/方案？ —— YES → Hermes 内部推理
  │   └─ 先编译意图，再做分析和决策
  │
  └─ 范围不明确？ —— 编译意图后判断 ambiguities，必要时向用户确认
```

### Agent 能力矩阵

能力矩阵以当前 `agent-registry.json`、Hermes 运行状态和实际试调用为准。此处只保留判断方法：
- 代码修改/文件操作：Codex、Claude Code、Hermes 内部都可能可用，按任务边界、上下文和验证能力选择。
- 代码审查/实现方案：Codex 和 Claude Code 可混合使用，不固定“谁实现、谁审查、谁修复”的流程。
- 搜索/调研：优先权威源和可验证工具，可用浏览器、CLI/API、Kimi 或其他当前可用 Agent。
- 桌面操作/自动化：以当前桌面控制工具的可用状态为准。
- 后台常驻任务：使用当前支持异步、可追踪、可验收的 Worker 或调度工具。

### 路由规则

| 任务类型 | 首选 | 备选 | 原因 |
|---------|------|------|------|
| 代码修改/文件操作 | claude（file_executor） | deepseek-tui | 有 file+terminal，改文件 |
| 代码审查/实现方案 | codex（代码审查员） | — | 只看不写 |
| 桌面操作/自动化 | agent-tars（桌面操作员） | openclaw（旧） | 新桌面操作 Agent |
| 搜索/调研 | openclaw（调研专员） | 浏览器/autocli | 已重新定位为 researcher |
| 情报监控 | openclaw（情报官） | cron 定时跑 | 同 openclaw 实例，cron 驱动 |
| 技术预处理+复审 | nesta（技术专员） | claude | 中间层，读项目+写任务包 |
| 方案策划/文档撰写 | pirlo（方案策划） | — | 纯文职，无 terminal |
| 分析/决策/方案审核 | hermes-internal（审核角色） | — | readonly，deepseek-v4-pro |
| 后台常驻任务 | deepseek-worker | 手动分批执行 | mailbobx 异步通信 |

### 反模式

| ❌ 不要 | ✅ 应该 |
|--------|--------|
| 看到"改文件"就固定派 Claude Code | 先判断复杂度和当前能力，再决定自己做、派 Codex、派 Claude 或混合使用 |
| 把用户原话传给子 Agent | 子 Agent 收到 compiled_intent（must_keep/must_avoid/success_criteria） |
| allowed_files 写 "请推断" | 让用户明确，或拒绝任务 |
| 跳过验收直接标 completed | 委托任务必须进入可验收状态；简单直做任务也要做最小验证 |
| 子 Agent 输出直接给用户 | 先过 Review Gate（语义检查） |
| 忽略反馈 | 分析反馈 → 按 USER.md / MEMORY.md / skill / Obsidian 分层沉淀 |
| deepseek-worker 用 CLI 调用 | deepseek-worker 只能通过 Mailbox 异步派发 |
