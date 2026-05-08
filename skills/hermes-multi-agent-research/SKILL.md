---
name: hermes-multi-agent-research
description: "UMBRELLA: 多Agent研究确认 + Agent路由决策 + Claude Code委托协议 + 常驻Worker + GitHub调研 + 竞品情报研究 + Web工具链。合并了 agent-routing-guide 和 hermes-claude-code-delegation。"
category: autonomous-ai-agents
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
  ├─ Step 1: 百度搜索两个品牌
  │   browser_navigate(url="https://www.baidu.com/s?wd=蒙牛+2026世界杯+营销+最新")
  │   browser_navigate(url="https://www.baidu.com/s?wd=伊利+2026世界杯+营销+最新")
  │   注意：URL 需要手动 URL encode 中文
  │
  ├─ Step 2: 阅读搜索结果页面，识别关键文章
  │   browser_snapshot() 查看结果列表
  │   优先阅读：品牌官网、新华网/海报新闻等正规媒体、行业分析文章
  │   注意：搜索"大家还在搜"区域提示了用户真实需求
  │
  ├─ Step 3: 深入阅读关键文章
  │   browser_click(ref='@eXX') 点击文章链接
  │   browser_snapshot(full=true) 获取全文
  │   注意：很多文章需要多次 snapshot 才能看完（百度页面截断）
  │
  ├─ Step 4: 多轮搜索（细化方向）
  │   根据第一步结果中的新发现，做二次搜索
  │   例如：从"容声冰箱×蒙牛官宣"发现跨界合作 → 专门搜这个方向
  │
  ├─ Step 5: 交叉验证
  │   多个来源交叉验证同一事实（如版权报价数字）
  │   注意区分：AI生成内容、自媒体观点 vs 官方媒体
  │
  └─ Step 6: 汇编报告 → 存入 Obsidian
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
| 代码修改/文件操作 | 当前最适合的代码执行者 | 其他可用代码 Agent | 不固定 Codex/Claude 分工，按任务和验证选择 |
| 代码审查/实现方案 | Codex 或 Claude Code | Hermes 内部 | 可混合使用，避免写死流水线 |
| 桌面操作/自动化 | 当前桌面控制工具 | 浏览器/CLI 替代路径 | 先确认实时可用性 |
| 搜索/调研 | 权威源 + 当前可用工具 | Kimi/浏览器/CLI/API | 以可验证和可访问为准 |
| 分析/决策/方案 | Hermes-internal | 领域 Agent | 需要策略判断力和上下文理解 |
| 后台常驻任务 | 当前异步 Worker/调度器 | 手动分批执行 | 必须可追踪、可验收 |

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
