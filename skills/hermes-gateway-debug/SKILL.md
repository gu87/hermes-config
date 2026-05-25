---
name: hermes-gateway-debug
description: 'Hermes Gateway 飞书连接断开排查 + 飞书API Permission排查。UMBRELLA: 合并了 feishu-permission-debug。'
tags:
- hermes
- gateway
- feishu
- troubleshooting
category: hermes-multi-agent-research
agents:
- hermes
- hermes-internal
---

# Hermes Gateway 排障指南

## 核心判断：gateway_state.json 的坑

`gateway_state.json` 中的 feishu 状态可能是**滞后的**——进程已死但状态还显示 connected。

正确顺序：
1. 查 PID 是否真实存在 → `ps aux | grep hermes`
2. 读 `gateway_state.json` 的 `gateway_state` 字段：
   - `running` = 正常
   - `draining` / `null` = 进程已退出或正在退出
3. 查日志 `~/.hermes/logs/gateway.log` 看飞书连接最后是什么时候

## 重启命令

```bash
Hermes gateway restart
```

## 飞书连接症状（正常日志）

```
[Lark] [INFO] connected to wss://msg-frontier.feishu.cn/ws/v2?...
[Lark] [ERROR] receive message loop exit, err: no close frame received or sent
```
后半句 ERROR 是飞书服务器主动断开的，gateway 会自动重连，不需要干预。

## 需要人工介入的情况

- Gateway 进程本身退出（PID 在 ps 中找不到）
- `gateway_state` 变成 `draining` 且不恢复
- 连续 SSL errors 无法重连

**先用** `Hermes gateway restart`。

## 验证 channel_skill_bindings（飞书多人格绑定）

当配置了 `channel_skill_bindings` 后，用以下流程验证绑定生效：

### 1. 检查配置

```bash
# 查看绑定条目
grep -n "channel_skill_bindings\|skills:" ~/.hermes/config.yaml

# 确认格式：feishu → extra → channel_skill_bindings → [{id, skills}]
```

### 2. 检查网关是否加载了绑定

```bash
# 日志中应有 "Channel directory built: N target(s)"
grep "Channel directory built" ~/.hermes/logs/gateway.log
```

- N > 0 表示配置已加载
- 如果 N=0 或日志不出现，检查 config.yaml 格式是否在 `feishu.extra` 下

### 3. 检查代码路径

```bash
# 核心解析函数是否存在
grep -n "def resolve_channel_skills" ~/.hermes/hermes-agent/gateway/platforms/base.py

# 飞书 adapter 是否调用了
grep -n "resolve_channel_skills\|auto_skill" ~/.hermes/hermes-agent/gateway/platforms/feishu.py
```

### 4. 检查 skill 文件

```bash
# 确认绑定的 skill 存在
ls ~/.hermes/skills/<skill-name>/SKILL.md
```

### 5. 端到端验证

```bash
lark-cli api POST /open-apis/im/v1/messages \
  --params '{"receive_id_type":"chat_id"}' \
  --data '{"receive_id":"<chat_id>","msg_type":"text","content":"{\"text\":\"人格测试\"}"}'
```

注意：
- channel_skill_bindings **仅对群聊生效**，DM 仍是默认人格
- 改完 config 必须重启 gateway：`kill <pid>` + `hermes gateway run --replace`
- 同一群可以绑定多个 skills（数组），按顺序全部加载

### 已验证 Bot 信息（Gu 的环境）

| Bot | app_id | open_id | 凭证来源 | 查询方法 |
|-----|--------|---------|---------|---------|
| 马尔蒂尼 (Gateway) | `cli_a94fbfdef7e31ccb` | `ou_b455ec67f11b87a1befdc2c8326c5717` | ~/.hermes Feishu Bot (主) | `~/.hermes/.env` → `FEISHU_APP_ID/SECRET` | 主 Gateway 进程 |
| 内斯塔 (lark-cli / Hermes Profile) | `cli_a9434df9ad3a1cb6` | `ou_d4d4bcffd234aa177b1458ae0381934c` | ~/.hermes/profiles/nesta Feishu Bot | `~/.lark-cli/config.json` + Keychain 或 `~/.hermes/profiles/nesta/.env` | Hermes profile `nesta` / lark-cli |

> 内斯塔 Bot 原本由 OpenClaw 管理，2026-05-13 迁移到独立 Hermes Profile `nesta`。迁移时必须确保 OpenClaw 的 feishu channel 已禁用，否则两个 WebSocket 客户端同时连接同一个飞书 Bot 会导致消息被 OpenClaw 拦截。

## §G — 多 Gateway 进程管理

当多个 Hermes Profile 各自运行独立的 Gateway 进程时（如主网关 + 内斯塔 + 皮尔洛），需注意以下事项：

### 进程识别

```bash
# 查看所有 Hermes Gateway 进程
ps aux | grep "hermes.*gateway" | grep -v grep

# 区分不同 Profile
# 主网关：hermes gateway run --replace  （或 -m hermes_cli.main gateway run）
# 内斯塔：hermes -p nesta gateway run --replace
# 皮尔洛：hermes -p piero gateway run --replace
```

### 冲突预防

| 资源 | 冲突条件 | 解决方法 |
|------|---------|---------|
| api_server 端口 | 默认 8642，所有 Profile 争夺同一端口 | 在 config.yaml 中设置 `platforms.api_server.port` 为不同值（如 8643, 8644），或直接禁用 api_server |
| 飞书 Bot 长连接 | 同一个 Bot 的 app_id 不允许同时建立两个 WebSocket | 确保 OpenClaw 和 Hermes Gateway 不会同时连接同一个 Bot |

### 端口配置

```yaml
# ~/.hermes/profiles/<name>/config.yaml
platforms:
  api_server:
    port: 8643  # 各 Profile 使用不同端口
    # 或完全禁用
    # enabled: false
```

> 完整拉 bot 进群流程见 [`references/add-bot-to-group.md`](./references/add-bot-to-group.md)

---

## §F — 群聊无响应排查（Bot 收不到/回不了群消息）

> **场景：** 用户建了群、把 bot 拉进群（或以为拉进了群），但在群里发消息 bot 不回复。

### 排查流程（按顺序，别跳步）

```bash
# Step 1 — 确认 gateway 进程活着 + Feishu 连接正常
ps aux | grep hermes | grep -v grep
cat ~/.hermes/gateway_state.json          # feishu.state 应为 connected
```

```bash
# Step 2 — 检查日志中有没有来自目标群的 inbound 消息
grep "chat_id=oc_xxxxx" ~/.hermes/logs/gateway.log
# 能搜到 → 消息到了 gateway，检查 mention/policy gate
# 搜不到 → 消息根本没到 gateway，两个可能原因：
#   ① bot 不在群里（去 Step 3 确认）
#   ② bot 在群里但飞书事件订阅没开"接收群聊消息"（跳"诊断方向 A"）
#   区分：走 Step 3 确认 bot 在群 → 仍在 Step 2 搜不到 → 事件订阅问题
```

```bash
# Step 3 — 确认 bot 到底在不在群里（这是最常踩的坑）
lark-cli api GET "/open-apis/im/v1/chats/{chat_id}"
# 返回的 bot_count=0 → bot 不在群里，不需要再看别的
```

```bash
# Step 4 — 确认当前连接的 bot 身份
# ⚠️ lark-cli 和 Gateway 用的是两个不同的飞书应用！
# lark-cli 查到的是"内斯塔"（app_id cli_a9434df9ad3a1cb6）
# Gateway 连的是"马尔蒂尼"（app_id cli_a94fbfdef7e31ccb）
lark-cli api GET /open-apis/bot/v3/info  # 这是内斯塔的信息
```

```bash
# Step 5 — 尝试向目标群发一条测试消息
lark-cli api POST /open-apis/im/v1/messages \
  --params '{"receive_id_type":"chat_id"}' \
  --data '{"receive_id":"{chat_id}","msg_type":"text","content":"{\"text\":\"测试\"}"}'
# 成功 → 能发消息，问题在 receive 端
# 失败 230002 → "Bot/User can NOT be out of the chat" — bot 不在群里
```

### 如果 bot 不在群里

**方案 A：用户手动添加（推荐，不需要额外权限）**
在飞书群里 → 右上角群设置 → 添加机器人 → 搜索 bot 名称添加

**方案 B（Gu 环境专用）：通过 Gateway 凭证直接调 API 拉马尔蒂尼进群**

> ⚠️ lark-cli 连的是**内斯塔** bot（app_id: `cli_a9434df9ad3a1cb6`），不是 Gateway 的**马尔蒂尼** bot（app_id: `cli_a94fbfdef7e31ccb`）。用 lark-cli 拉人本质是用内斯塔的 token 操作，会失败（230002 或 99991672）。

正确的做法是直接用 Gateway 的凭证调飞书 API：

```python
import requests, json

# Step 1: 从 ~/.hermes/.env 读取马尔蒂尼的凭证（用 Python 读取避免 shell 截断）
# 注意：.env 中的 FEISHU_APP_SECRET 在 shell 中 cat/echo 会被隐蔽
with open('/Users/gu/.hermes/.env') as f:
    for line in f:
        if line.startswith('FEISHU_APP_ID='):
            APP_ID = line.split('=', 1)[1].strip()
        elif line.startswith('FEISHU_APP_SECRET='):
            APP_SECRET = line.split('=', 1)[1].strip()

# Step 2: 获取 tenant_access_token
r = requests.post(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET}
)
token = r.json()['tenant_access_token']

# Step 3: 用 app_id 作为 member_id_type 拉 bot 进群（不是 open_id！）
r = requests.post(
    f'https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}/members',
    params={'member_id_type': 'app_id'},
    json={'id_list': [APP_ID]},
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
)
# 成功时 code=0, invalid_id_list=[] 
```

**关键：** 拉 bot 进群必须用 `member_id_type: app_id`，用 `open_id` 会报 `invalid_id_list`。

```bash
# Step 4: 验证 bot 已进群
curl -s "https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}" \
  -H "Authorization: Bearer {token}"
# bot_count 应 > 0
```

```bash
# Step 5: 发测试消息确认连通
curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id" \
  -H "Authorization: Bearer {token}" -H "Content-Type: application/json" \
  -d '{"receive_id":"{chat_id}","msg_type":"text","content":"{\"text\":\"测试消息\"}"}'
```

### 如果 bot 在群里但依然无响应

#### 诊断方向 A：飞书服务端事件订阅未开启群消息（最常见）

> 完整诊断 + 对比表见 [`references/group-message-event-subscription.md`](./references/group-message-event-subscription.md)

**信号：** Gateway 日志中只出现 `Inbound dm message`（私聊），完全搜不到目标群的 chat_id。说明飞书服务器**根本没把群消息事件推送过来**。

**原因：** 飞书开放平台 → 应用 → 事件与回调 → 事件配置中 `im.message.receive_v1` 事件只有"接收私聊消息"勾选，**没有勾选"接收群聊消息"**。

**修复（需人工在飞书开放平台操作）：**
1. 打开 [飞书开放平台](https://open.feishu.cn/app/{app_id}/) → 应用管理中心 → 你的 bot
2. 左侧 **事件与回调** → **事件配置**
3. 找到 `im.message.receive_v1`（接收消息），展开
4. **勾选** ☑️ `接收群聊消息`
5. 保存 → **发布新版本**（必须发布才生效，仅保存不生效）

**注意：** 飞书开放平台没有公开 API 可以查询或修改事件订阅配置，必须手动操作。

#### 诊断方向 B：Gateway 端群消息策略门控

如果日志能搜到群 chat_id 入站（说明事件已到达），检查 `_should_accept_group_message` 逻辑（`gateway/platforms/feishu.py`）：
1. `_allow_group_message` — group_policy 是否为 `open`（config.yaml 中 feishu.group_policy）
2. 是否需要 @mention 才能触发（policy 非 open 时需要 @bot）
3. 用户是否在 allowlist/blacklist 中

### 关键日志锚点

| 症状 | 日志关键词 | 原因 |
|------|-----------|------|
| 日志搜不到群 chat_id | 无匹配 | bot 不在群 / 事件订阅没发过来 |
| `Dropping group message that failed mention/policy gate` | 群消息被 gate 拦截 | group_policy 或 mention 门控 |
| `code=230002` | 发送消息时返回 | bot 不在群里 |
| `code=99991672` | 拉人时返回 | 缺少 im:chat 权限 |

---

## 备用方案：直接拉起 Gateway（绕过 launchd）

如果 `restart` 后进程依然频繁挂掉（launchd 管理导致 drain timeout），用这个方式直接拉起后台 Gateway：

```
terminal(background=true) 执行: hermes gateway run --replace
```

关键发现：
- `Hermes gateway restart` 底层通过 launchctl 管理服务，在 drain 超时（60s）内未完成时 launchd 会强制终止
- 症状：gateway_state 不断在 "running" 和 "draining" 间跳动，飞书反复连接断开
- 解决：不用 restart，直接 `hermes gateway run --replace` 作为独立后台进程跑，绕过 launchd 生命周期管理

验证：
```bash
ps aux | grep hermes | grep -v grep  # 确认进程存在
cat ~/.hermes/gateway_state.json      # gateway_state 应为 running，feishu 为 connected
lsof -p $(pgrep -f hermes-gateway) -i -P -n | grep LISTEN  # 确认监听端口（Gateway 默认 8642）
```

---

## §C — 飞书 API Permission 排查（absorbed from `feishu-permission-debug`）

> **核心发现：** 飞书 API 返回 `code=99991672` (Access denied) 时，响应体内**直接包含**缺失的权限列表和可点击的授权申请链接。不要自己猜需要什么权限，直接读 error 里的 `permission_violations` 数组和 `troubleshooter` 链接。

### 排查流程
```bash
# 1. 用 tenant_access_token 调一个需要权限的 API
# 注：lark-cli 使用内斯塔 bot 的 token，Gateway 使用马尔蒂尼 bot 的 token
# 两个 bot 的权限集可能不同
curl -s "https://open.feishu.cn/open-apis/drive/v1/files" \
  -H "Authorization: Bearer {token}"

# 2. 读 error.code 和 error.permission_violations
# 3. 用 troubleshooter 链接直接申请权限
```

### 常见缺失权限对照

| 目标操作 | 需要权限 |
|---------|---------|
| 读文档/表格 | `drive:drive` 或 `space:document:retrieve` |
| 写文档/表格 | `drive:drive` |
| 发消息 | `im:message` |
| 搜索文档 | `search:docs:read` |
| 拉机器人进群 | `im:chat` + `im:chat.members:write_only` |

### 双 Bot 身份说明（Gu 的环境）

| Bot | 用途 | app_id | 说明 |
|-----|------|--------|------|
| 马尔蒂尼 | Hermes Gateway 飞书连接 | `cli_a94fbfdef7e31ccb` | 收发 DM/群消息、处理事件 |
| 内斯塔 | lark-cli API 调用 | `cli_a9434df9ad3a1cb6` | 仅用于命令行调 API |

**不要混淆。** 用 lark-cli 查到的 bot 信息（内斯塔，open_id: ou_d4d4bcffd234aa177b1458ae0381934c）不是 Gateway 的 bot。Gateway 的 bot 马尔蒂尼的 open_id 无法通过 lark-cli 获取。

### 备注
- 授权链接里的 `token_type=tenant` 表示开通的是 tenant 级权限（应用身份）
- 发布应用后权限才生效，不是改完就立即可用

---

## §H — DNS/Proxy 导致的飞书断连排查（Clash DNS 间歇故障型）

### 症状

- `gateway.log` 持续报 `Failed to resolve 'open.feishu.cn' ([Errno 8] nodename nor servname provided, or not known)`
- 每 ~2 分钟一次重试，持续 15-20 分钟，然后自动恢复
- `gateway_state.json` 的 `feishu.state` 显示 `connected`（过时状态），但实际已断连
- `dig open.feishu.cn` 直接执行能正常返回 IP（系统 DNS 正常）

### 根因

Clash 代理（或同类 proxy 工具）的内置 DNS（fake-ip 模式）通向远端 DNS 服务器时连接失败。Python HTTP 客户端（httpx/requests）走代理出口时使用 Clash 的 DNS，而 Clash 的 DNS 上游挂掉了 → DNS 解析失败 → WebSocket 连接断开 → 不断重试 → Clash DNS 上游恢复后自动重连成功。

### 排查流程

```bash
# 1. 确认系统代理状态
scutil --proxy | grep HTTPEnable        # 0=关闭, 1=开启
networksetup -getwebproxy Wi-Fi         # 另一种检查方式

# 2. 确认 Clash 进程存活
ps aux | grep -i clash | grep -v grep

# 3. 确认直接 DNS 正常
dig open.feishu.cn +short               # 应返回 IP

# 4. 确认问题出在代理出口
curl -x http://localhost:7890 -s --max-time 5 https://open.feishu.cn
# HTTP 000 (curl error) 或长时间卡住 = 代理 DNS 挂了

# 5. 查日志确认故障时间段
grep "Failed to resolve 'open.feishu.cn'" ~/.hermes/logs/gateway.log | tail -5
grep "receive message loop exit" ~/.hermes/logs/gateway.log | tail -3
```

### 修复方案

**方案 A（推荐 — 根治 DNS 依赖问题）：**
```bash
# 让飞书 DNS 跳过代理，走系统 DNS
echo '# Feishu DNS - bypass proxy' >> ~/.zshrc
echo 'export NO_PROXY="$NO_PROXY,open.feishu.cn,feishu.cn,open.larksuite.com,larksuite.com"' >> ~/.zshrc
source ~/.zshrc
```

**方案 B（恢复 Clash DNS 后重启网关）：**
```bash
# 先确认 Clash 恢复正常
curl -x http://localhost:7890 -s --max-time 5 https://open.feishu.cn
# 然后重启网关
hermes gateway restart
```

**方案 C（绕过 launchd 直接后台跑）：**
详见上方「备用方案：直接拉起 Gateway（绕过 launchd）」章节。

### 关键区分

| 症状 | 诊断 | 处理 |
|------|------|------|
| `Errno 8 nodename nor servname` + 系统 DNS 正常 | Clash DNS 挂了 | 方案 A 或等自动恢复 |
| `Errno 8` + 系统 DNS 也失败 | 网络全局断连 | 检查 VPN/代理/路由器 |
| SSL errors + DNS 正常 | 证书/TLS 问题 | 不同路径，不属此节 |

---

## §I — 多 Agent 系统完整快照流程

当用户要求「看看我的 Agent 状态」「系统快照」「检查各 Agent 情况」时，按以下固定流程执行：

### 流程步骤

```bash
# Step 1 — 进程概览
ps aux | grep hermes | grep -v grep         # 所有 Hermes 相关进程
ps aux | grep gateway | grep -v grep        # 所有 Gateway 进程
lsof -i -P | grep LISTEN                    # 所有监听端口

# Step 2 — Agent 注册表
cat ~/.hermes/config/agent-registry.json    # 完整的 agent 定义和路由规则
# 或通过 WebUI: http://localhost:8787 → Backend agents

# Step 3 — Gateway 状态
cat ~/.hermes/gateway_state.json            # 连接状态 (可能过时!)

# Step 4 — 错误日志
tail -20 ~/.hermes/logs/errors.log          # 最新错误
grep "ERROR" ~/.hermes/logs/errors.log | tail -10

# Step 5 — Gateway 日志（飞书连接状态）
grep -E "connected|disconnected|close frame|reset" ~/.hermes/logs/gateway.log | tail -10

# Step 6 — 资源监控
vm_stat | head -5                           # 内存
df -h / | tail -1                           # 磁盘
sysctl hw.memsize | awk '{print $2/1024/1024/1024 " GB"}'  # 总内存
```

### 输出格式

以表格形式呈现以下维度：
1. **网关进程表** — PID、角色、运行时长、CPU%、内存%
2. **Agent 注册表** — 名称、类型、权限模式、隔离级别、工具集
3. **端口映射** — 端口号 → 服务名
4. **问题列表** — 严重度（🔴🟡⚪）、症状、根因、修复方案
5. **定时任务** — 名称、状态、调度时间

### 信号词

用户说「快照」「检查情况」「各 Agent 状态」「系统诊断」「看看系统」时，直接执行此流程。

### 已知陷阱

- `gateway_state.json` 的 feishu.state 可能已过时 — 必须结合日志验证
- feishu 断连但 gateway 进程活着 → 检查 DNS/proxy（见 §H）
- agent-registry.json 在 `~/.hermes/config/`，不在 `~/.hermes/` 根目录

---

## §J — GitHub/Git MCP 故障排查

### 症状

- MCP server 'github' 反复断连，`unhandled errors in a TaskGroup (1 sub-exception)`
- 5 次重试后放弃，约 90 秒后重新开始新一轮

### 排查流程

```bash
# 1. 确认配置
grep -A8 "github:" ~/.hermes/config.yaml

# 2. 确认网络可达
curl -s --max-time 10 https://api.github.com
# 正常 → API 可达

# 3. 检查 gh auth
gh auth status
# ✓ Logged in → token 存在
# Token scopes 应包含 repo, workflow

# 4. 如果是 Copilot MCP 端点 (api.githubcopilot.com/mcp/)
# 需要检查 Copilot 本地缓存
ls ~/.config/github-copilot/ 2>/dev/null
gh copilot --version 2>/dev/null
```

### 两类配置及对应故障

| 配置类型 | config.yaml 格式 | 认证方式 | 常见故障 |
|---------|-----------------|---------|---------|
| **Copilot MCP** | `url: https://api.githubcopilot.com/mcp/` + `headers.Authorization: Bearer ***` | Copilot 订阅 token | HTTP 400 = token 过期或无 Copilot 订阅 |
| **Command MCP** | `command: npx` + `args: [-y, @modelcontextprotocol/server-github]` | gh token (OAuth) | 依赖本地环境，需确认 npx 可用 |

### Copilot 端点的修复

```bash
# 1. 重新认证 Copilot
gh copilot auth login    # 交互式，需用户手动操作

# 2. 如果不需要 Copilot，切到 command 模式：
# 改 config.yaml 中的 github MCP 配置为：
# github:
#   enabled: true
#   command: npx
#   args:
#   - -y
#   - @modelcontextprotocol/server-github
#   timeout: 120
# 然后重启网关

# 3. 验证修复
curl -s --max-time 10 -H "Authorization: Bearer $(gh auth token)" \
  https://api.githubcopilot.com/mcp/ 2>&1
# 返回非 400 = 修复成功
```

---

## §D - 桌面工具在网关会话中不可用

网关会话（Feishu/Telegram 等）不加载 `desktop` 工具集，`desktop_permissions` 等桌面工具不可用。

**回退方案：** 直接调用底层 Python 函数（详见 `references/tool-availability.md`）。

**原则：** 不要直接回复"这个工具不可用"——底层 Python 函数往往可直接调用。

---

## §E — 飞书文档读取限制

`feishu_doc_read` 工具**只能在飞书评论回复上下文（comment context）中调用**。在普通 DM 中调用会报错："Feishu client not available (not in a Feishu comment context)"。

详见 `references/feishu-doc-read-limitations.md`。
