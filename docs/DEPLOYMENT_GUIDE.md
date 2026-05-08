# Hermes 智能助手系统 — 傻瓜部署教程

> 适用对象：任何人
> 目标：从零开始在任意 Mac/Linux 上部署一套完整的 Hermes 智能体系统

---

## 一、这是什么？

**Hermes** 是一个 AI 助手框架，主控由 MiniMax M2.7 驱动（也可切换其他模型），通过「技能」（Skill）体系扩展能力。

你的这套系统核心特点：

| 组件 | 作用 |
|------|------|
| **Hermes 主控** | 接收你的指令，理解需求，协调子 Agent |
| **Claude Code** | 作为子 Agent，执行复杂编码任务 |
| **170 专家角色库** | 营销、工程、项目管理等专业角色，按需调用 |
| **飞书集成** | 通过 Bot 接收/发送指令，消息推送到手机 |
| **定时任务** | 自动执行周期性工作（如 GitHub 热榜推送） |
| **Mailbox 架构** | 多 Agent 通信机制，避免记忆污染 |

**典型工作流：**
```
你（飞书发消息）
    ↓
Hermes 主控（理解需求，选择模式）
    ↓
L1: 直接处理 / L2: 并行派给子 Agent / L3: Agent Team 讨论
    ↓
结果通过飞书返回给你
```

---

## 二、快速部署（30 分钟完成）

### 第一步：安装 Hermes

```bash
# 1. 确保有 Python 3.11+ 和 uv
python3 --version   # 确认 >= 3.11
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装 hermes-agent
uv tool install hermes-agent

# 3. 确认安装成功
hermes --version
```

### 第二步：安装 Claude Code（子 Agent 引擎）

```bash
# 需要 Node.js >= 18
node --version   # 确认 >= 18
npm install -g @anthropic-ai/claude-code

# 确认安装成功
claude --version
```

### 第三步：初始化配置目录

```bash
# 创建必要的目录结构
mkdir -p ~/.hermes
mkdir -p ~/.claude/skills
mkdir -p ~/.claude/teams

# 创建空的 config.yaml（后面填充）
touch ~/.hermes/config.yaml
touch ~/.hermes/.env
```

### 第四步：配置 config.yaml

将以下内容写入 `~/.hermes/config.yaml`：

```yaml
model:
  default: MiniMax-M2.7-highspeed
  provider: minimax-cn
  base_url: https://api.minimaxi.com/v1

providers: {}
fallback_providers: []

toolsets:
  - hermes-cli

mcp_servers:
  minimax:
    command: uvx
    args: ["minimax-coding-plan-mcp", "-y"]
    env:
      MINIMAX_API_KEY: "你的API密钥"
      MINIMAX_API_HOST: "https://api.minimaxi.com"

agent:
  max_turns: 90
  gateway_timeout: 1800

terminal:
  backend: local

delegation:
  max_iterations: 50
  max_concurrent_children: 5

cron:
  wrap_response: true

logging:
  level: INFO

FEISHU_HOME_CHANNEL: "你的飞书频道ID"
```

### 第五步：配置 .env 文件

将以下内容写入 `~/.hermes/.env`：

```bash
# MiniMax API（国内版）
MINIMAX_CN_API_KEY=你的MiniMax密钥
MINIMAX_CN_BASE_URL=https://api.minimaxi.com/v1

# API Server
API_SERVER_ENABLED=true
GATEWAY_ALLOW_ALL_USERS=true

# 飞书（可选，有飞书 Bot 才需要）
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxx
FEISHU_BOT_NAME=Hermes
```

### 第六步：安装 Token Plan MCP（图片理解）

```bash
# Token Plan MCP 提供图片理解能力
uv tool install minimax-coding-plan-mcp

# 或使用 npm
npm install -g minimax-coding-plan-mcp
```

### 第七步：克隆技能库

**方法 A：从头创建（推荐先这样做）**

技能库不在一个文件夹里，需要按需安装。以下是核心技能安装：

```bash
# 进入 hermes skills 目录
cd ~/.hermes/skills

# 安装多 Agent 协作核心技能（自动从 GitHub 下载）
git clone https://github.com/nickclyde/hermes-skills.git autonomous-ai-agents 2>/dev/null || true

# 如果没有现成的，从各 skill 网站手动复制
# 飞书相关技能需要单独从 NickClyde/hermes-lark-skills 获取
```

**方法 B：直接从 Gu 的电脑复制**

如果你能访问 Gu 的电脑，最快的方式是：

```bash
# 在 Gu 的电脑上执行（需要两台电脑在同一网络）
rsync -avz ~/.hermes/skills/ 目标电脑:~/.hermes/skills/
rsync -avz ~/.claude/skills/ 目标电脑:~/.claude/skills/
rsync -avz ~/.hermes/config.yaml 目标电脑:~/.hermes/config.yaml
rsync -avz ~/.hermes/.env 目标电脑:~/.hermes/.env
```

### 第八步：启动 Hermes Gateway

```bash
# 启动后台服务
hermes gateway run --replace &

# 验证服务运行
sleep 3
hermes gateway status
```

看到类似输出说明启动成功：
```
✓ Gateway running on http://localhost:18272
```

### 第九步：连接飞书（可选）

1. 打开[飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用，添加「机器人」能力
3. 获取 App ID 和 App Secret，填入 `.env`
4. 在飞书群里添加机器人
5. 将机器人的 Chat ID 填入 `FEISHU_HOME_CHANNEL`

---

## 三、核心技能说明

### 必须了解的技能

| 技能名 | 作用 | 位置 |
|--------|------|------|
| `multi-agent-project-workflow` | 多 Agent 项目标准流程 | `~/.hermes/skills/autonomous-ai-agents/` |
| `hermes-claude-code-delegation` | 如何派任务给 Claude Code | 同上 |
| `dongqiudi-resource-policy` | 懂球帝资源包销售政策 | `~/.hermes/skills/media/` |
| `dongqiudi-resource-package-workflow` | 懂球帝资源包制作流程 | `~/.hermes/skills/media/` |
| `feishu-sheets` | 飞书表格操作 | `~/.hermes/skills/productivity/` |
| `prompt-optimizer` | 优化 delegation prompt | `~/.hermes/skills/productivity/` |

### 170 专家角色库

位置：`~/.hermes/skills/autonomous-ai-agents/agency-experts-team/agents/`

常用角色：

| 角色 | 路径 | 用途 |
|------|------|------|
| 内容创作者 | `marketing/content-creator.md` | 写方案、文案 |
| KOL 合作经理 | `marketing/kol-collaboration-manager.md` | KOL 合作方案 |
| 项目牧羊人 | `project/project-shepherd.md` | 项目总协调 |
| 增长黑客 | `marketing/growth-hacker.md` | 市场增长策略 |

---

## 四、日常使用

### 通过飞书使用

在飞书给 Hermes Bot 发消息即可，格式随意，Hermes 会理解并执行。

**常用指令：**
- "帮我整理一下腾讯FC世界杯的营销方案"
- "做一张资源包报价表"
- "今天 GitHub 有什么热点项目"
- "把这个文案改一下"

### 通过命令行使用

```bash
# 直接对话
hermes

# 查看状态
hermes gateway status

# 重启服务
hermes gateway restart
```

---

## 五、故障排查

### Hermes 启动不了

```bash
# 1. 检查 Python 版本
python3 --version  # 需要 >= 3.11

# 2. 检查 hermes 安装
which hermes
hermes --version

# 3. 查看日志
cat ~/.hermes/logs/gateway.log
```

### 飞书消息收不到

```bash
# 1. 确认 Bot 已添加到群
# 2. 确认 FEISHU_HOME_CHANNEL 正确（是 Chat ID 不是群名）
# 3. 检查 .env 配置
cat ~/.hermes/.env
```

### 子 Agent 不执行

```bash
# 1. 确认 Claude Code 已安装
which claude
claude --version

# 2. 检查 mailbox 目录
ls ~/.claude/teams/

# 3. 检查 delegate_task 是否正常
hermes
# 在 hermes 里输入：测试 delegate
```

### 图片理解失效

```bash
# 1. 确认 Token Plan MCP 已安装
uvx --version

# 2. 确认 API Key 有效
# 3. 检查 config.yaml 里的 MINIMAX_API_KEY 是否完整（没有被截断）
```

---

## 六、进阶配置

### 添加定时任务

```python
# 在 hermes 对话框输入：
/cron "0 10 * * *" "访问 github.com/trending，把热榜发给我"
```

### 使用 Agent Team 模式

当任务复杂、需要多个子 Agent 讨论时：

```bash
# 在 hermes 里说：
"你需要一个增长黑客和一个内容创作者一起帮我策划这个活动，你们先讨论一下再给我结论"
```

### 扩展技能

新技能放在 `~/.hermes/skills/` 目录下，格式：

```
~/.hermes/skills/我的技能/
├── SKILL.md        # 必须：技能说明
├── references/     # 可选：参考文档
├── templates/     # 可选：模板
└── scripts/       # 可选：脚本
```

---

## 七、架构参考图

```
┌─────────────────────────────────────────────────────┐
│                     你（飞书）                        │
└─────────────────────┬───────────────────────────────┘
                      │ 消息
                      ↓
┌─────────────────────────────────────────────────────┐
│              Hermes 主控（MiniMax M2.7）              │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐    │
│  │需求澄清  │  │模式选择   │  │质量仲裁        │    │
│  │L1/L2/L3 │  │边界守护   │  │结果检查        │    │
│  └─────────┘  └──────────┘  └────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
┌──────────────┐ ┌──────────┐ ┌───────────────┐
│  子Agent 1   │ │ 子Agent 2│ │  子Agent 3    │
│ Claude Code  │ │ 角色专家  │ │  角色专家     │
│ （技术推理）  │ │（内容/策略）│ │（数据/分析）  │
└──────────────┘ └──────────┘ └───────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ↓
              Mailbox 通信
          ~/.claude/teams/{project}/
```

---

## 八、一键部署脚本

把以下内容保存为 `deploy-hermes.sh`，在目标机器上运行即可：

```bash
#!/bin/bash
set -e

echo "🚀 开始部署 Hermes 智能助手系统..."

# 1. 安装 Hermes
echo "📦 安装 Hermes Agent..."
if ! command -v hermes &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv tool install hermes-agent
fi

# 2. 安装 Claude Code
echo "📦 安装 Claude Code..."
if ! command -v claude &> /dev/null; then
    npm install -g @anthropic-ai/claude-code
fi

# 3. 创建目录
echo "📁 创建配置目录..."
mkdir -p ~/.hermes ~/.claude/skills ~/.claude/teams

# 4. 初始化配置
if [ ! -f ~/.hermes/config.yaml ]; then
    echo "⚠️  请手动创建 ~/.hermes/config.yaml"
    echo "   参考：https://github.com/nickclyde/hermes-config"
fi

# 5. 启动服务
echo "🚀 启动 Hermes Gateway..."
hermes gateway run --replace &

sleep 3
echo "✅ 部署完成！访问 http://localhost:18272 查看状态"
```

运行：
```bash
chmod +x deploy-hermes.sh
./deploy-hermes.sh
```

---

## 九、参考链接

- Hermes 官方文档：https://github.com/nickclyde/hermes
- Claude Code：https://docs.anthropic.com/claude-code
- 飞书 Bot 开发：https://open.feishu.cn/document/

---

**有任何问题，在飞书给 Hermes 发消息即可。**
