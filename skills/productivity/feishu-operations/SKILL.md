---
name: feishu-operations
description: "飞书（Feishu/Lark）操作总集 — 常规飞书 API 操作优先用 lark-cli。读文档、查日历、搜用户、通用 API 调用。遇到 lark-cli 覆盖不到、profile/权限不明确、或需要 Gateway 主 bot 凭证验证时，再按官方 OpenAPI/API 响应直接核验。"
triggers:
  - 飞书文档
  - lark
  - feishu
  - read feishu doc
  - 飞书日历
  - 飞书联系人
  - feishu api
  - 飞书表格
  - lark-cli
tags: [feishu, lark, productivity, cli]
category: productivity
agents: [hermes]
---

# 飞书操作集

> 最后更新: 2026-05-07
> 核心原则：常规飞书操作**优先**走 `lark-cli`（已安装），认证通常自动处理。当前唯一 active profile 为 `cli_a94fbfdef7e31ccb`（马尔蒂尼），是默认 profile 无需 `--profile` 参数。如果 CLI 能力、profile、权限或返回内容不确定，直接用官方后台/API 响应做源头验证。

---

## 工具

- **lark-cli** — 路径 `~/.npm-global/bin/lark-cli`，用 `npm view @larksuite/cli version` 查最新版（当前约 1.0.49，每日发版）。升级：`npm i -g @larksuite/cli@latest`
- **Hermes Gateway Bot** — 名称 **马尔蒂尼**，app_id: `cli_a94fbfdef7e31ccb`。凭证存于 `~/.hermes/.env`，由 Hermes Gateway 读取。**你和我对话走这个 Bot。**
- **lark-cli profile: `cli_a94fbfdef7e31ccb`** — 当前唯一 active profile，对应马尔蒂尼。凭证存于 macOS Keychain。默认 profile 无需 `--profile` 参数。**注意**: 旧文档可能引用 `--profile maldini`，该 profile 名已不存在。

---

## 常用操作

### 读文档

```bash
lark-cli api GET "/open-apis/docx/v1/documents/{doc_id}/raw_content"

# 格式化输出
lark-cli api GET "/open-apis/docx/v1/documents/{doc_id}/raw_content" -q '.data.content'

# 限制输出长度
lark-cli api GET "..." | head -100
```

**doc_id 获取方式**：从飞书文档 URL 中提取。URL 格式 `https://xxx.feishu.cn/wiki/Jo5ow71P4ix3HLkm6jScJC7Kn9G` 中的 `Jo5ow71P4ix3HLkm6jScJC7Kn9G` 是 wiki token，实际的 docx id 需通过 wiki API 解析或直接从 URL 的 obj_token 参数获取。

### 查日历

```bash
lark-cli calendar +agenda
lark-cli calendar events instance_view --params '{"calendar_id":"primary","start_time":"...","end_time":"..."}'
```

### 搜用户

```bash
lark-cli contact +search-user --query "John"
```

### 邮件

飞书邮件通过 `lark-cli mail` 子命令操作（CLI 封装了 API），不要手动拼 `/open-apis/mail/v1/...` 路径。

**权限前提**：
- 邮件是用户数据，必须用 **user token**（非 bot token）
- 马尔蒂尼 `cli_a94fbfdef7e31ccb` 已开通全部 8 个 `mail:*` scope
- 如果 `lark-cli auth status` 显示 `user identity: missing`，走 device 授权流程（见下方）

#### 列邮件（triage）

```bash
# 列出最近 20 封（默认 INBOX）
lark-cli mail +triage --max 20

# 只看未读
lark-cli mail +triage --filter '{"is_unread":true}' --max 50

# 按发件人过滤
lark-cli mail +triage --filter '{"from":["wuzhengying@dongqiudi.com"]}' --max 50

# 全文关键词搜索
lark-cli mail +triage --query "提成 销售" --max 50

# 输出 JSON（含附件/标签等完整字段）
lark-cli mail +triage --max 50 --format json
```

**已知限制**：triage 默认搜索窗口可能只覆盖数周。较早的邮件可能搜不到（即使 filter/query 正确）。

#### 读邮件正文

```bash
# 获取完整内容（含 body_plain_text、body_html、attachments）
lark-cli mail +message --message-id "<message_id>"

# JSON 格式（方便解析）
lark-cli mail +message --message-id "<message_id>" --format json
```

#### 读邮件线程

```bash
lark-cli mail +thread --thread-id "<thread_id>"
```

**注意**：实测 thread API 有时返回 0 items，即使同线程有多封邮件。此时改用 triage 按 subject 搜 + 逐个 message 读取作为替代方案。

#### 下载附件

附件下载是两步流程：

```bash
# Step 1: 获取临时下载 URL（有时效）
lark-cli mail user_mailbox.message.attachments download_url \
  --params '{"user_mailbox_id":"me","message_id":"<msg_id>","attachment_ids":["<att_id>"]}' \
  --format json

# Step 2: 从 JSON 输出提取 download_url，curl 下载
URL=$(lark-cli mail user_mailbox.message.attachments download_url \
  --params '{"user_mailbox_id":"me","message_id":"<msg_id>","attachment_ids":["<att_id>"]}' \
  --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['download_urls'][0]['download_url'])")
curl -s -o output.jpg "$URL"
```

**陷阱**：`--output` 只接受相对路径，需要先 `cd` 到目标目录。

完整附件下载的步步实录（含所有失败路径和最终可行流程）见 `references/feishu-mail-attachment-download.md`。

#### 定时检查未读邮件

用 cronjob 创建每日任务，`enabled_toolsets: ["terminal"]` 即可（lark-cli 在 PATH 中，不需要 web/search 等其他工具集）。

```bash
# 关键：用 lark-cli mail +triage --filter '{"is_unread":true}' --format json
# cron 的 prompt 中嵌入完整 bash 命令，让 cron agent 执行并汇总
# model 推荐 opencode-go / opencode_go_deepseek_flash（成本低，API 调用够用）
```

参考：已创建的「每日邮件未读检查」cron（job_id: `ccc94c3d1d41`，每日 10:30，enabled_toolsets: `["terminal"]`）

#### User Token 重新授权流程（device authorization）

当 `lark-cli auth status` 显示 `user identity: missing` 时：

```bash
# Step 1: 发起 device 授权，获取 verification_url
lark-cli auth login --domain mail --no-wait --json
# 输出包含 verification_url 和 device_code

# Step 2: 让用户在浏览器/Lark 里打开 verification_url，点击「授权」
open "<verification_url>" -a Lark

# Step 3: 用户确认后，用 device_code 完成登录
lark-cli auth login --device-code <device_code>

# Step 4: 验证 user identity 已就绪
lark-cli auth status  # 应显示 user: ready
```

#### 诊断命令

```bash
lark-cli auth scopes     # 查看已配置的权限 scope 列表
lark-cli auth status     # 查看 bot/user identity 状态
lark-cli mail user_mailboxes profile --params '{"user_mailbox_id":"me"}'  # 确认邮箱身份
```

#### 桌面客户端（备选方案）

```bash
open -a "Lark" "https://mail.feishu.cn/"
# 注意：macOS 上 App 名是 "Lark.app"，不是 "Feishu.app"
```

### 通用 API 调用

```bash
# 默认 profile：cli_a94fbfdef7e31ccb（马尔蒂尼）
lark-cli api GET /open-apis/bot/v3/info

# GET 请求
lark-cli api GET /open-apis/calendar/v4/calendars

# 带参数 GET
lark-cli api GET /open-apis/... --params '{"key":"value"}'

# POST 请求
lark-cli api POST /open-apis/... --data '{"key":"value"}'

# 自动翻页
lark-cli api GET /open-apis/... --page-all

# 输出格式
--format json|ndjson|table|csv|pretty
```

### 身份模式

```bash
# 以用户身份操作（需要用户授权）
lark-cli api GET ... --as user

# 以 bot 身份操作（默认）
lark-cli api GET ... --as bot

# 自动选择
lark-cli api GET ... --as auto
```

---

### 配置信息

#### Hermes Gateway Bot（马尔蒂尼）
- app_id: `cli_a94fbfdef7e31ccb`
- app_name: `马尔蒂尼` ✅ 已确认（2026-05-06）
- app_secret: 存于 `~/.hermes/.env`
- open_id: `ou_b455ec67f11b87a1befdc2c8326c5717`
- domain: `feishu`
- 用途：Gateway 通过 WS 连接飞书，收发 DM/群聊消息、处理事件
- lark-cli profile: `cli_a94fbfdef7e31ccb`（唯一 active profile，默认）

---

## 注意事项
- lark-cli 不支持数字格式（千分位/人民币符号），需手动在飞书设置
- 飞书表格 API 返回 Key 掩码（sk-、ark- 等），这是飞书安全机制
- iCloud 死锁时，用 `write_file` 工具绕过

---

## 相关参考

- 飞书 Bot 配置清单：`references/feishu-bot-inventory.md`（从开发者后台确认的最新 Bot 列表）
- 全量工具配置：Obsidian `系统环境配置.md`
- GitHub: [larksuite/cli](https://github.com/larksuite/cli)
- 官方文档: https://open.feishu.cn/document/mcp_open_tools/feishu-cli-let-ai-actually-do-your-work-in-feishu

## Pitfalls

- ⚠️ **不要在常规场景手动 curl + 自己管 token** — lark-cli 通常能自动处理认证。只有当 lark-cli 缺少接口封装、profile/权限需要源头核验、输出被工具遮蔽，或必须验证 Gateway 主 bot token 时，才按官方 OpenAPI/API 响应直接调用，并注意不要暴露 secret。
- ❌ **不要用 feishu_doc_read 工具** — 它只工作在 Feishu 评论上下文，DM 里不可用。用 lark-cli 代替
- ❌ **邮件接口报 `need_user_authorization` 不一定是权限没开** — 先用 `lark-cli auth scopes` 确认权限 scope 是否已配置，再用 `lark-cli auth status` 检查 user identity 是否 ready。常见根因是 user token 过期，走 `lark-cli auth login --domain mail` 流程重新授权即可，无需去开放平台改配置。
- ❌ **不要在 shell 里直接 cat/echo .env** — FEISHU_APP_SECRET 会被隐蔽工具截断显示。用 Python 读文件
- ✅ **lark-cli 已安装** — `which lark-cli` 确认在 `~/.npm-global/bin/`
- ⚠️ **npm 全局安装可能因 postinstall 脚本超时** — `npm i -g @larksuite/cli@latest` 的 `scripts/install.js` 有时超过 terminal() 默认 60s 超时。解决：`npm install -g @larksuite/cli@latest --ignore-scripts && node /path/to/scripts/install.js`。升级时如果 `npm i -g @larksuite/cli@latest` 因 postinstall 脚本超时被 SIGTERM，先 `--ignore-scripts` 再手动 `node scripts/install.js`
- ⚠️ **npm upgrade 超时** — `npm install -g @larksuite/cli@latest` 的 postinstall 脚本（`scripts/install.js`）可能超过 `terminal()` 默认 60s 超时被 SIGTERM。解决：`npm install -g @larksuite/cli@latest --ignore-scripts` 跳过 postinstall，然后手动 `node /Users/gu/.npm-global/lib/node_modules/@larksuite/cli/scripts/install.js`（给 120s）。install.js 会自动更新本 skill 的内容。
- ⚠️ **npm 升级 lark-cli 超时** — `npm i -g @larksuite/cli@latest` 的 postinstall 脚本 (`node scripts/install.js`) 可能在 Hermes 60s 默认超时内跑不完。解决方案：先 `--ignore-scripts` 安装包体，再手动跑 postinstall：
  ```bash
  npm install -g @larksuite/cli@latest --ignore-scripts
  node /Users/gu/.npm-global/lib/node_modules/@larksuite/cli/scripts/install.js
  ```
  这不是 CLI 的 bug，是 postinstall 脚本在慢网络/低资源下的正常耗时。
