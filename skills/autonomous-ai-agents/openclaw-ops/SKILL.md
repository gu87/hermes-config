---
name: openclaw-ops
description: OpenClaw (ArkClaw/Gateway) 运维操作 — 配置修复、状态检查、常见报错处理、exec 权限管理。OpenClaw 是 builderz-labs/mission-control 的核心网关组件，跑在端口 18789。
tags: [openclaw, gateway, builderz, agentic]
category: autonomous-ai-agents
---

# OpenClaw 运维手册

## 核心进程

- **Gateway**: PID 233, 端口 18789, LaunchAgent 管理
- **Dashboard**: `http://127.0.0.1:18789/`
- **配置文件**: `~/.openclaw/openclaw.json`

## 状态检查

```bash
openclaw status
```

## ⚠️ `openclaw status` 命令超时（2026-05-07 发现）

**症状**：`openclaw status` 执行后挂起，>15s 无响应，最后 timeout

**原因**：不明（可能与 Gateway 内部组件阻塞有关），但 **Gateway 本身可能完全正常运作**

**替代检查方法**（绕过 CLI 直接验证 Gateway 健康）：
```bash
# 1. 检查 Gateway 进程是否存活
lsof -i :18789 | head -5
# 期望输出：node PID ... TCP localhost:18789 (LISTEN)

# 2. 检查 Dashboard 是否响应
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/
# 期望输出：200

# 3. 检查新版 PID（与 CLI 无关）
openclaw --version              # CLI 本身能用
ps aux | grep openclaw | grep -v grep | grep -v tail
# 看 node ... gateway --port 18789 进程在不在

# 4. 检查日志有无异常
tail -5 /tmp/openclaw/openclaw-*.log | rg -i "error|warn"
```

**要点**：`openclaw status` 超时 ≠ Gateway 挂了。优先用 lsof + curl 快速验证。

## 认证：Token 缺失报错

症状：
```
unauthorized: gateway token missing (open the dashboard URL and paste the token in Control UI settings)
```

解决：从配置文件读 token 并粘贴到 Dashboard 的 Control UI Settings：
```bash
node -e "const fs=require('fs'); console.log(JSON.parse(fs.readFileSync(process.env.HOME+'/.openclaw/openclaw.json','utf8')).gateway.auth.token)"
```

## ⚠️ 配置损坏：elevated key 导致 CLI 完全失效

症状：
```
Invalid config at /Users/gu/.openclaw/openclaw.json:
- <root>: Unrecognized key: "elevated"
[openclaw] Failed to start CLI: Error: Invalid config...
```

**原因**: 旧版 OpenClaw 留下的 `elevated` 字段，新版本（2026.4.27）不认。`openclaw doctor --fix` 无法修复自己（因为 CLI 本身就起不来）。

**修复**（Node.js 绕过，不依赖 openclaw CLI）：
```bash
node -e "
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.env.HOME + '/.openclaw/openclaw.json', 'utf8'));
delete cfg.elevated;
fs.writeFileSync(process.env.HOME + '/.openclaw/openclaw.json', JSON.stringify(cfg, null, 2));
console.log('Done: elevated key removed');
"
```

验证：`openclaw status`

## ⚠️ Gateway 只能用 127.0.0.1 访问

配置文件默认 `"bind": "loopback"`，所以：
- ❌ `http://192.168.x.x:18789/` — 不通
- ✅ `http://127.0.0.1:18789/` — 正常

这是设计如此，不是故障。Gateway 默认不对外暴露。

## 🔒 Exec 权限管理（2026-05-03 补充）

### 架构：两层策略

OpenClaw 的 exec 安全由两层叠加：

| 层 | 位置 | 字段 | 作用 |
|----|------|------|------|
| Requested policy | `openclaw.json` → `tools.exec.*` | security / ask | 配置请求的策略 |
| Host approvals | `~/.openclaw/exec-approvals.json` | defaults / agents.* | 实际生效的批准策略 |

**有效策略 = 两者取严格值**。例如 config 设 `security: full` 但 approvals 设 `security: allowlist` → 实际生效 **allowlist**。

### 症状：exec 被静默拒绝

Agent 执行任何命令都失败，`openclaw status` 看起来正常，但 agent 报告"exec 权限被禁"。

**原因**：`openclaw.json` 中 `tools.exec.security = "allowlist"`，但 `exec-approvals.json` 里 allowlist 为空 → 没有命令被允许。

### 诊断

```bash
cat ~/.openclaw/exec-approvals.json
# 检查 defaults 和 agents.<name>.allowlist 是否为空
openclaw exec-policy show   # 查看当前生效策略
openclaw approvals get      # 查看批准文件状态
```

### CLI 修复（推荐）

通过 `openclaw approvals set --stdin` 用 heredoc 写入完整配置，无需手动编辑 JSON：

```bash
openclaw approvals set --stdin <<'EOF'
{
  "version": 1,
  "defaults": {
    "security": "allowlist",
    "ask": "on-miss",
    "askFallback": "deny",
    "autoAllowSkills": true
  },
  "agents": {
    "main": {
      "security": "allowlist",
      "ask": "on-miss",
      "askFallback": "deny",
      "autoAllowSkills": true,
      "allowlist": [
        {"pattern": "pwd", "source": "allow-always"},
        {"pattern": "ls", "source": "allow-always"},
        {"pattern": "cat", "source": "allow-always"},
        {"pattern": "echo", "source": "allow-always"},
        {"pattern": "python3", "source": "allow-always"},
        {"pattern": "node", "source": "allow-always"},
        {"pattern": "git", "source": "allow-always"},
        {"pattern": "curl", "source": "allow-always"},
        {"pattern": "open", "source": "allow-always"},
        {"pattern": "ps", "source": "allow-always"}
      ]
    }
  }
}
EOF
```

### 策略字段说明

| 字段 | 可选值 | 含义 |
|------|--------|------|
| `security` | `deny` / `allowlist` / `full` | deny=全部阻止, allowlist=仅白名单, full=全部允许 |
| `ask` | `off` / `on-miss` / `always` | off=不询问, on-miss=白名单未命中时询问, always=每次询问 |
| `askFallback` | `deny` / `allowlist` / `full` | 需要询问但 UI 不可达时的兜底行为 |
| `autoAllowSkills` | boolean | 自动放行技能中引用的 CLI（便利选项） |

### Allowlist 格式

每条 allowlist 条目：
```json
{
  "pattern": "pattern-goes-here",
  "source": "allow-always"
}
```

- **命令名**（如 `git`、`python3`）— 通过 PATH 解析匹配
- **路径 glob**（如 `/opt/homebrew/bin/*`、`~/Projects/**/bin/rg`）— 精确路径匹配
- 管道/链式命令（`echo ok && pwd`）需要每个顶层段都满足 allowlist

### 用户偏好记录

- Gu 偏好 `full`（unrestricted），不想管理 allowlist。两步到位：
  1. `openclaw exec-policy preset yolo`（改 config）
  2. `openclaw approvals set` 把 `agents.main.security` 也设为 `full`
- `autoAllowSkills: true` 保持默认
- `ask` 设为 `off` 免打扰

### 重启 Gateway 生效

```bash
openclaw gateway restart
```

### 参考

- 完整 allowlist 参考：`references/exec-allowlist-reference.md`
- Terminal 故障排查（CWD 被删除）：`references/terminal-troubleshooting.md`
- OpenClaw 官方文档：https://docs.openclaw.ai/zh-CN/security/exec-approvals
- CLI help：`openclaw approvals --help`

## ⚠️ Agent 报 "No API key found for provider X"

症状：
```
No API key found for provider "minimax". Auth store: /Users/gu/.openclaw/agents/main/agent/auth-profiles.json
Configure auth for this agent (openclaw agents add <id>) or copy auth-profiles.json from the main agentDir.
```

**原因**: OpenClaw agent 的 `auth-profiles.json` 是空的（或不存在），但 `models.json` 里配置了 provider。

**修复**: 从 Hermes 的 auth.json 拿 MiniMax key，手动写入 auth-profiles.json。**注意**: MiniMax key 在 OpenClaw 里对应的 provider 名是 `openclaw`（不是 `minimax`）：
```bash
node -e "
const fs = require('fs');
const hermesAuth = JSON.parse(fs.readFileSync(process.env.HOME + '/.hermes/auth.json', 'utf8'));
const minimaxKey = hermesAuth.credential_pool?.minimax?.[0]?.access_token || hermesAuth.credential_pool?.['minimax-cn']?.[0]?.access_token;
const authProfiles = { 'openclaw': { 'api_key': minimaxKey } };
fs.writeFileSync(process.env.HOME + '/.openclaw/agents/main/agent/auth-profiles.json', JSON.stringify(authProfiles, null, 2));
console.log('Done');
"
```

路径: `~/.openclaw/agents/main/agent/auth-profiles.json`

## ⚠️ Agent 报 \"No API key found for provider\" + 模型名不匹配

症状：Agent 启动时报 `No API key found for provider "openai"` 或 `"minimax"`，同时 `openclaw.json` 里的 agent 默认模型是 `minimax/MiniMax-M2.7`。

**原因**: `openclaw.json → agents.defaults.model.primary` 和 `models.json` 里的 provider/model 名字对不上。OpenClaw 的 provider 标识符是 `openclaw`（在 `models.json` 里定义），不是 `minimax`。

**修复** — 改 `~/.openclaw/openclaw.json` 里的 agent defaults：
```json
"agents": {
  "defaults": {
    "model": {
      "primary": "openclaw/MiniMax-M2.7-highspeed"
    },
    "models": {
      "openclaw/MiniMax-M2.7-highspeed": {
        "alias": "MiniMax"
      }
    }
  }
}
```

然后重启 Gateway：`openclaw gateway restart`

## 常见警告（可忽略）

- `chokidar@^5.0.0 (used by memory-core)` — 兼容性提示，不影响功能
- `OAuth dir not present (~/.openclaw/credentials)` — 未配置 OAuth，不影响
- `Gateway service PATH includes version managers` — PATH 信息提示，不影响

## ⚠️ 升级流程（2026-05-05 补充）

从 `2026.5.x` 升到 `2026.5.x+1` 的标准流程：

### Step 1: 检查当前版本和最新版

```bash
openclaw --version                           # 当前版本
npm view openclaw version                    # 最新版
npm view openclaw --json | python3 -c "
import sys, json; d = json.load(sys.stdin)
print(f'{d[\"name\"]} v{d[\"version\"]}')
print(f'Repo: {d.get(\"repository\",{}).get(\"url\",\"\")}')
"
```

### Step 2: 审阅 Changelog（找 breaking changes）

```bash
curl -sL "https://raw.githubusercontent.com/openclaw/openclaw/main/CHANGELOG.md" | grep -i -B2 -A3 "breaking\|migration\|BREAKING\|⚠\|deprecat"
```

重点排查领域：
| 你的配置 | 查什么 |
|---------|--------|
| 飞书（Feishu） | 插件 API 变化、配置格式变更 |
| 微信（WeChat/openclaw-weixin） | 插件兼容性、登录协议变化 |
| Exec Policy（yolo/full） | 审批系统 breaking change |
| Gateway 配置格式 | `openclaw.json` schema 变化 |
| 已安装插件 | Plugin API 兼容性声明 |

### Step 3: 判断是否可升

- CalVer 修正版（如 `2026.5.3-1`）→ 通常安全，官方声明「满足 base plugin API 范围」
- 主版本号变化 → 必须看 migration guide
- mini 版本号变化（如 `2026.4.x` → `2026.5.x`）→ 审阅 changelog，重点查 breaking changes

### Step 4: 升级

```bash
npm install -g openclaw@latest    # 或 npm update -g openclaw
openclaw --version                # 验证新版本
```

### Step 5: 升级后验证

```bash
# 检查配置兼容性
openclaw plugins list | head -20

# 检查关键插件状态（微信/飞书等）
openclaw plugins list | grep -E "weixin|feishu"

# 运行 doctor
openclaw doctor 2>&1 | grep -E "✓|✗" | head -10
```

### Pitfalls

- `npm update -g openclaw` 可能超时（尤其 node_modules 大时），用 `npm install -g openclaw@latest` 替代
- 升级过程会移除并重建 node_modules（`removed X packages, added Y packages`），不影响 `~/.openclaw/` 下的配置和数据
- 升级后微信/飞书可能会报 config warnings（如 `channelConfigs metadata`、`compiled runtime output`）— 这些是预存警告，不影响功能
- 升级后必须重新检查 exec approvals 是否正常：`openclaw exec-policy show`

## 频道管理（Channel）

### 禁用飞书

```bash
# 方式1：直接改 config，设 enabled: false
node -e "
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.env.HOME + '/.openclaw/openclaw.json', 'utf8'));
if (cfg.channels?.feishu) cfg.channels.feishu.enabled = false;
fs.writeFileSync(process.env.HOME + '/.openclaw/openclaw.json', JSON.stringify(cfg, null, 2));
console.log('Feishu disabled');
"
openclaw gateway restart
```

### 连接微信（WeChat）

微信接入使用腾讯官方插件 `@tencent-weixin/openclaw-weixin`：

```bash
# 1. 停止 Gateway
openclaw gateway stop
pkill -f openclaw

# 2. 安装微信插件（首次需要，已安装则跳过）
openclaw plugins install "@tencent-weixin/openclaw-weixin@latest"

# 3. 启动 Gateway
openclaw gateway start

# 4. 扫码登录（终端显示二维码）
openclaw channels login --channel openclaw-weixin
```

**扫码方式**：
- 终端直接显示 ASCII 二维码，用手机微信扫一扫
- 如果终端二维码渲染异常，fallback 链接也会打印在终端：`https://liteapp.weixin.qq.com/q/...`
- 二维码过期后会自动刷新（通常 ~3 次后仍无人扫码则命令超时退出）

**proxy 路由提示**：
- 首次运行 `channels login` 时输出 `[proxy] routing process HTTP traffic through external proxy http://127.0.0.1:7890`
- 这是正常行为，通过本地代理（Clash/V2ray）路由请求到微信服务器
- 如果本地没有跑代理，需检查 ~/.openclaw/openclaw.json 中 channels 配置

**注意事项**：
- 安装时会出现 `channelConfigs metadata` 配置警告 → 可忽略，不影响功能
- 插件安装时会自动修改 `~/.openclaw/openclaw.json`，备份在 `.bak`
- 扫码完成后微信里会出现一个 **ClawBot** 会话，直接发消息即可与 OpenClaw 对话
- 鸿蒙手机暂时不支持，苹果/安卓需更新到最新版微信
- 扫码命令 `channels login` 默认有 120s 超时，扫码完成前不要关闭终端

**扫码命令的输出时序**：
- 首次运行 `channels login` 时，前 ~18-20s 在初始化插件（输出 Config warnings + plugin loading），之后才显示二维码和 fallback URL
- 如果命令行超时未扫码，重新运行第二次就会快很多（插件已初始化）
- fallback URL 格式：`https://liteapp.weixin.qq.com/q/...?qrcode=...&bot_type=3`

**通过脚本/Hermes 工具获取扫码链接的 Pitfalls**：
- `--no-color` 不是 openclaw 的有效选项（会报错 `unknown option '--no-color'`）
- 标准终端工具（`stdbuf` / `script -c`）在 macOS 上不可用或行为不同
- 推荐用 Python `subprocess.Popen` 捕获输出并搜索 URL 正则，而不是用终端 background 进程
- 二维码（ASCII art）在终端渲染良好，但通过工具捕获时可能包含 ANSI 控制码；**fallback URL 更可靠**

**微信掉线症状**：Gateway 日志持续出现：
```
WARN getUpdates: fetch rejected response headers, retrying with node http client
```
这是微信端的长轮询 session 过期，需要重新扫码。处理流程：停 Gateway → pkill → 重启 Gateway → channels login。

**停止 Gateway 时的注意**：
- `openclaw gateway stop` 可能用 launchctl 不完全停止进程，建议补一刀：`pkill -f "openclaw.*gateway"`
- 验证：`ps aux | grep openclaw | grep -v grep` 应无结果

### 查看频道状态

```bash
openclaw channels list
openclaw channels status --probe
```

### 解绑/删除频道

```bash
openclaw channels remove --channel <channel-name>
# 或在 config 里直接设 enabled: false
```

## 与 Hermes 通信（Mailbox 协议）

OpenClaw 通过 `~/.claude/teams/ai-team/` 目录的 JSON inbox 文件与 Hermes 通信。协议文档在 `~/.openclaw/skills/mailbox/SKILL.md`。

### 快速发消息给 Hermes

```bash
python3 -c "
import json, fcntl
from datetime import datetime, timezone
msg = {
    'from': 'openclaw',
    'text': '你的消息内容',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'read': False,
    'color': 'green',
    'summary': '消息摘要'
}
with open('/Users/gu/.claude/teams/ai-team/inboxes/hermes.json', 'r+') as inbox:
    fcntl.flock(inbox, fcntl.LOCK_EX)
    data = json.load(inbox)
    data.append(msg)
    inbox.seek(0); inbox.truncate()
    json.dump(data, inbox, indent=2, ensure_ascii=False)
print('✓ Sent to Hermes')
"
```

### 读 Hermes 回复

```bash
python3 -c "
import json, fcntl
with open('/Users/gu/.claude/teams/ai-team/inboxes/openclaw.json', 'r+') as inbox:
    fcntl.flock(inbox, fcntl.LOCK_EX)
    data = json.load(inbox)
    for i, m in enumerate(data):
        if not m.get('read'):
            print(f'[{i}] From {m[\"from\"]}: {m[\"text\"][:300]}')
    for m in data:
        m['read'] = True
    inbox.seek(0); inbox.truncate()
    json.dump(data, inbox, indent=2, ensure_ascii=False)
"
```

### 消息类型

| 类型 | 用途 |
|------|------|
| `task_dispatch` | 委派任务给 Hermes |
| `review_request` | 请求代码审查 |
| `plan_approval_request` | 请求方案审批 |
| `task_report` | 汇报任务完成 |
| `idle_notification` | 空闲信号 |
