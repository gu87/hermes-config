---
name: openclaw-ops
description: OpenClaw (ArkClaw/Gateway) 运维操作 — 配置修复、状态检查、常见报错处理、exec 权限管理。OpenClaw 是 builderz-labs/mission-control 的核心网关组件，跑在端口 18789。
tags: [openclaw, gateway, builderz, agentic]
category: autonomous-ai-agents
agents: [openclaw]
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

## 🖥️ 本地桌面/浏览器检查（通过 delegate_task）

OpenClaw 可以作为桌面控制 Agent，检查用户本地环境（Chrome 浏览器、Tampermonkey 脚本、扩展状态等）。

### 典型场景

- 用户问「检查我是不是装好了 X 脚本」
- 用户说「帮我看下我的浏览器」
- 需要查看用户本地的文件、截图、Chrome tabs 状态

### 工作流

```python
delegate_task(
    agent_id='openclaw',
    goal='<描述要检查的内容>',
    context='<环境上下文，如用户是 macOS，浏览器是 Chrome>'
)
```

### 检查 Tampermonkey 已安装脚本

OpenClaw 可以通过 Chrome 扩展的 LevelDB 存储直接读取已安装脚本的元数据：

```bash
# Tampermonkey 的 Local Extension Settings 路径
~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/dhdgffkkebhmkfjojejmpbldmpobfkfo/

# 从 LevelDB 日志提取脚本信息
cat 000003.log | strings | grep -E "header|enabled|name|author|version" | head -50
```

或直接用 `python3` 解析 LevelDB 的 `log` 文件：
```python
# Python: 解析 LevelDB 日志中的 JSON 数据
import re, json
with open(path_to_log, 'rb') as f:
    data = f.read()
    # 查找 JSON 块中的脚本配置
    matches = re.findall(rb'\{.*"enabled":(?:true|false).*\}', data)
    for m in matches:
        try:
            obj = json.loads(m.decode('utf-8', errors='replace'))
            print(f"Script: {obj.get('name')} v{obj.get('version')} by {obj.get('author')} — {'ENABLED' if obj.get('enabled') else 'DISABLED'}")
        except: pass
```

### 截图（macOS）

```bash
screencapture -T0 /Users/gu/screenshot.png
# 然后通过 MEDIA:/path/to/file 发送给用户
```

#### ⚠️ 用户要的是 App 窗口截图，不是全屏（2026-05-11 补充）

**症状**：OpenClaw 截了 2880×1800 的全屏，用户说「不能只截图app么？我不需要整个桌面的截图」。

**原因**：`screencapture -T0` 默认截全屏，而用户期望的是只看到 App 窗口本身。

**修复**：用 ImageMagick 的 `convert -crop` 或 Python Pillow 裁剪到 App 窗口区域。

```bash
# 方式1：screencapture + ImageMagick crop
screencapture -T0 /tmp/fullscreen.png
convert /tmp/fullscreen.png -crop 288x541+0+25 /Users/gu/懂球帝_第一屏.png

# 方式2：screencapture + Python Pillow（更可控）
python3 -c "
from PIL import Image
img = Image.open('/tmp/fullscreen.png')
# 裁取窗口区域 (left, top, right, bottom)
cropped = img.crop((0, 25, 288*2, 541*2))  # Retina屏×2
cropped.save('/Users/gu/懂球帝_第一屏.png')
"
```

**Pitfalls**：
- Retina 屏下物理像素是逻辑像素×2，裁剪时注意坐标缩放（逻辑 288×541 → 物理 576×1082）
- 窗口位置可能变化（用户拖动后），每次截图前先获取窗口位置
- 用 `screencapture -R<left,top,width,height>` 可直接截矩形区域，但坐标也是物理像素
- 子 Agent 截图后通过 `MEDIA:/path/to/file` 发送给用户，不要在文字描述里用 markdown image 语法（飞书用 MEDIA: 前缀）

### Pitfalls

- **第一次看到用户问本地浏览器时，别再说「我操作的是云端环境」** — OpenClaw 就是做这个的。第一反应应该是 delegate_task(agent_id='openclaw')
- Chrome 的 AppleScript JavaScript 注入需要手动在开发者菜单开启，不可靠。走 LevelDB 文件直接解析更稳定
- **CDP 调试**需要 Chrome 启动时加 `--remote-allow-origins=*`，用户手动打开的 Chrome 通常没有这个 flag，WebSocket 连接会被 403 拒绝
- **GM_registerMenuCommand 脚本** — 用户安装的脚本可能通过菜单项（而非页面 DOM 修改）工作。用户说「没生效」时，提醒他们点 🐒 图标看有没有菜单命令
- **vision_analyze 有 429 限流** — 高频调用会被拒绝，注意间隔或 fallback 到 tesseract OCR
- 截图文件路径要在 OpenClaw 能找到的地方（如 `/Users/gu/` 下）
- 使用 MEDIA: 前缀发送图片给用户：`MEDIA:/Users/gu/screenshot.png`
- 子Agent 的 isolation 应设为 shared（readonly 会阻止截图工具写盘）

### 桌面操作备用方案：Agent TARS

如果 OpenClaw 的桌面操作效果不佳（用户反馈「不好用」），可以考虑用 Agent TARS（字节跳动开源的多模态 GUI Agent）作为备选。

**工作流**：Hermes → `terminal()` → `agent-tars run --headless --input "..." --format json` → 解析 JSON 结果

**配置要点**：需传入 `--model.provider`, `--model.baseURL`, `--model.id`, `--model.apiKey` 来指定底层模型（推荐 DeepSeek V4 Pro）

详见参考：`references/agent-tars-integration.md`

详细参考：`references/local-desktop-inspection.md`

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

## ⚠️ 切换默认模型 Provider（2026-05-11 补充）

OpenClaw 的 agent 默认模型在 `openclaw.json` 中配置，切换步骤：

### Step 1: 确认 provider 已配置

检查 `models.providers` 是否已有目标 provider：

```bash
python3 -c "import json; c=json.load(open('/Users/gu/.openclaw/openclaw.json')); print(list(c['models']['providers'].keys()))"
```

如果 provider 不存在，需要先在 `models.providers` 中添加（参照已有的 provider 格式）。

### Step 2: 修改 agent 默认模型

改两个地方：

1. **`agents.defaults.model.primary`** — 设为 `"provider/model-id"`（如 `"deep-seek/deepseek-v4-flash"`）
2. **`agents.defaults.models`** — 添加别名，用于 Dashboard 显示

```bash
# 用 node 直接改（比手写 JSON 安全）
node -e "
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.env.HOME + '/.openclaw/openclaw.json', 'utf8'));
cfg.agents.defaults.model.primary = 'deep-seek/deepseek-v4-flash';
cfg.agents.defaults.models = {
  ...cfg.agents.defaults.models,
  'deep-seek/deepseek-v4-flash': { alias: 'DeepSeek Flash' },
  'deep-seek/deepseek-v4-pro': { alias: 'DeepSeek Pro' }
};
fs.writeFileSync(process.env.HOME + '/.openclaw/openclaw.json', JSON.stringify(cfg, null, 2));
console.log('Done');
"
```

### Step 3: 清理空模型条目（常见陷阱）

**症状**：`openclaw gateway restart` 报错：
```
Config invalid
- models.providers.deep-seek.models.2.id: Too small: expected string to have >=1 characters
- models.providers.deep-seek.models.2.name: Too small: expected string to have >=1 characters
```

**原因**：provider 的 `models` 数组中存在空条目 `{"id":"","name":""}`，OpenClaw 新版 schema 校验不通过。

**修复**：删掉该空条目（注意处理尾随逗号，JSON 不允许）：

```bash
node -e "
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.env.HOME + '/.openclaw/openclaw.json', 'utf8'));
const provider = cfg.models.providers['deep-seek'];
if (provider) {
  provider.models = provider.models.filter(m => m.id && m.id.length > 0);
  fs.writeFileSync(process.env.HOME + '/.openclaw/openclaw.json', JSON.stringify(cfg, null, 2));
  console.log('Cleaned ' + provider.models.length + ' valid model entries');
}
"
```

### Step 4: 重启 Gateway

```bash
openclaw gateway restart
```

### Step 5: 验证

```bash
# 检查 Gateway 是否正常
curl -s -o /dev/null -w \"%{http_code}\" http://127.0.0.1:18789/

# 运行一个快速任务验证 OpenClaw 在新模型下可用
# 在 Hermes 中：delegate_task(agent_id='openclaw', goal='简单测试任务')
```

### Pitfalls

- **provider 名是 `deep-seek`（带连字符）**，不是 `deepseek`。在 `models.providers` 中定义的是什么名，引用时就用什么名
- **JSON 尾随逗号**：删掉数组最后一项后，记得检查上一项末尾没有多余的逗号，否则 `openclaw gateway restart` 会报 JSON parse error
- **Gateway 重启后可能有延迟**：建议等 2-3 秒再验证
- 如果有两个同名 provider 的 key 在不同的 credential store，以 `models.providers` 中的 apiKey 为准
- 改配置前最好备份：`cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak`

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

## 🗑️ 清空对话历史（会话管理）（2026-05-11 补充）

用户要求「把对话都清空」时，需要清除 OpenClaw 的 session store。

### 会话存储位置

```
~/.openclaw/agents/main/sessions/sessions.json
```

### ⚠️ 格式陷阱

session store 的格式是 **键值对对象**，不是 `{"sessions":[...]}` 数组：

```json
{
  "agent:main:feishu:direct:ou_f66b6d3e9cc7917051b18c47bcb2e451": {
    "sessionId": "e54891c7-...",
    "updatedAt": 1778459090548,
    ...
  }
}
```

**错误做法**：写入 `{"sessions":[]}` → OpenClaw 仍会报告 1 个残留会话。
**正确做法**：写入空对象 `{}`。

### 清空步骤

```bash
# 1. 备份当前会话
cp ~/.openclaw/agents/main/sessions/sessions.json \
   ~/.openclaw/agents/main/sessions/sessions.json.bak.$(date +%s)

# 2. 清空为 {}
echo '{}' > ~/.openclaw/agents/main/sessions/sessions.json

# 3. 验证
openclaw sessions --json | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(f'剩余 {d[\"count\"]} 个会话')"
# 应输出：剩余 0 个会话

# 4. 可选：清理旧的备份存档
rm -rf ~/.openclaw/agents/main/sessions/archived-*/
```

### 额外检查点

如果执行第 2 步后仍显示有会话，可能有 duplicate 路径：

```bash
# 检查是否有 ~/.openclaw/.openclaw/agents/main/sessions/ 下的副本
ls -la ~/.openclaw/.openclaw/agents/main/sessions/sessions.json 2>/dev/null
# 如果存在，也清掉
echo '{}' > ~/.openclaw/.openclaw/agents/main/sessions/sessions.json
```

### Pitfalls

- `openclaw sessions cleanup` 命令是维护性清理（按 age/cap 淘汰），不是「全部清空」
- `openclaw reset --scope config+creds+sessions` 会清空全部配置+凭据+会话，太重了——如果只想清会话别用这个
- 清空后 OpenClaw Gateway 无需重启，已缓存的连接（如飞书长连）会直接创建新会话
- 如果想同时重置当前上下文（避免旧对话内容影响新任务），可以顺便重启 Gateway：`openclaw gateway restart`

## Hermes 中 OpenClaw 的工具集要求（agent-registry.json）

OpenClaw 不仅有自己的配置文件（`~/.openclaw/openclaw.json`），作为 Hermes Named Agent，它还通过 `~/.hermes/config/agent-registry.json` 配置 delegate_task 时的 toolsets。

**默认 toolsets 为 `["terminal", "file"]`**，只能运行命令和读写文件，不能搜网页、不能看图。当需要 OpenClaw 完成以下任务时，必须先在 agent-registry.json 中添加 `"web"` 和 `"browser"` 工具集：

| 任务类型 | 需要工具集 | 原因 |
|---------|-----------|------|
| 搜索历史照片做对比 | `web`, `browser` | 需要 web_search + browser_navigate |
| 调研/竞品分析 | `web`, `browser` | 需要搜索+浏览网页 |
| 下载图片/文件 | `web`, `browser`, `terminal` | browser 看图，curl 下载 |
| 纯文本分析/报告 | `file`, `terminal` | 默认就够了 |

**配置修改方法：**
```bash
# 改 ~/.hermes/config/agent-registry.json → openclaw → subagent_profile → toolsets
# 改为 ["terminal", "file", "web", "browser"]
# 然后重启 gateway
hermes gateway run --replace
```

**同时更新 capabilities（可选但推荐）：**
```json
"capabilities": [
  "web_research",
  "market_intelligence",
  "competitor_monitoring",
  "news_gathering",
  "web_browsing",
  "image_search",
  "visual_analysis"
]
```

**验证方法：**
```python
delegate_task(agent_id='openclaw', goal='搜索...', context='...')
# 检查返回的 effective_toolsets 是否包含 web, browser
```

**⚠️ 已踩坑**：此 session 中 OpenClaw 因缺少 `web`/`browser` 工具集，无法搜图和下载，导致我要亲自干活。用户指出后增加了这两个工具集才解决问题。

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
