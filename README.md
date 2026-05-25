# Hermes 多Agent系统 — 配置仓库

一键部署 Gu 的 Hermes 多Agent 系统，包含 8 个专职 Agent 编制、skills 知识库、模型路由和飞书入口。

## 快速部署（换机即用）

```bash
# 1. 克隆配置仓库
git clone https://github.com/gu87/hermes-config.git ~/.hermes

# 2. 运行部署脚本
cd ~/.hermes && bash bin/setup.sh

# 3. 填写 API 密钥
cp ~/.hermes/.env.example ~/.hermes/.env
vim ~/.hermes/.env

# 4. 启动网关
bash ~/.hermes/bin/start-gateway.sh
```

## 前置依赖

| 依赖 | 说明 |
|------|------|
| Hermes Agent | `pip install hermes-agent` 或克隆源码到 `~/.hermes/hermes-agent/` |
| Python 3.11+ | Hermes Agent 运行环境 |
| Node.js 24+ | MCP 服务器（CodeGraph, Playwright 等） |
| OpenChronicle | 可选，本地记忆 MCP 后端 |

## 仓库结构

```
~/.hermes/
├── SOUL.md                    # Hermes 身份定义
├── config.yaml                # 主配置（模型、gateway、delegation）
├── config/
│   ├── agent-registry.json    # Agent 编制、能力、skills、路由
│   ├── models.yaml            # 模型路由和认证
│   └── managed-agents.yaml    # Managed Agents 策略配置
├── memories/                  # 记忆和用户画像
├── skills/                    # 129+ 个 skill 知识库
├── bin/
│   ├── setup.sh               # 一键部署脚本
│   └── start-gateway.sh       # 启动飞书网关
├── launchd/                   # macOS 开机自启 plist
└── docs/                      # 运行手册、设计文档
```

## Agent 编制

| Agent | 模型 | 角色 |
|-------|------|------|
| Hermes 技术翻译官 | deepseek-v4-pro | 需求拆解、策略判断 |
| Claude 主程执行官 | claude-opus-4-7 | 代码执行、git 操作 |
| Codex 代码审查官 | gpt-5.5 | 只读代码审查 |
| DeepSeek 低成本快工 | deepseek-v4-pro | 小改、小测试 |
| Intelligence 情报员 | deepseek-v4-flash | 调研、竞品 |
| Pirlo 商业策划师 | deepseek-v4-pro | 方案、PPT |
| TARS 桌面操作员 | gpt-5.4 | macOS GUI、截图 |
| Ambrosini 质量门卫 | deepseek-v4-pro | 高风险验收 |
