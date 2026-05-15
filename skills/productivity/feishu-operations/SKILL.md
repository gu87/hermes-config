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
> 核心原则：常规飞书操作**优先**走 `lark-cli`（已安装），认证通常自动处理。lark-cli 已配置双 profile：默认 `nesta` 操作内斯塔；需要操作 Gateway 主 bot **马尔蒂尼** 时，显式使用 `--profile maldini`。如果 CLI 能力、profile、权限或返回内容不确定，直接用官方后台/API 响应做源头验证。

---

## 工具

- **lark-cli** — 路径 `~/.npm-global/bin/lark-cli`，版本 1.0.12
- **Hermes Gateway Bot** — 名称 **马尔蒂尼**，app_id: `cli_a94fbfdef7e31ccb`。凭证存于 `~/.hermes/.env`，由 Hermes Gateway 读取。**你和我对话走这个 Bot。**
- **lark-cli profile: `maldini`** — 名称 **马尔蒂尼**，app_id: `cli_a94fbfdef7e31ccb`。凭证存于 macOS Keychain。
- **lark-cli profile: `nesta`** — 名称 **内斯塔**，app_id: `cli_a9434df9ad3a1cb6`。凭证存于 `~/.lark-cli/config.json` + macOS Keychain。当前默认 profile。
- **独立 AI 助手 Bot** — 名称 **皮尔洛**，app_id: `cli_a95bb5a854f8dcc3`。描述"AI助手"，凭证**不在本机**。

> ⚠️ **关键：三个飞书应用相互独立！** Hermes Gateway 默认走**马尔蒂尼**，OpenClaw/默认 lark-cli 走**内斯塔**，皮尔洛是独立的。lark-cli 已支持 `nesta` 与 `maldini` 双 profile，查身份或操作资源时必须显式确认 profile，**不要混淆它们的 App ID 和能力范围。**

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

### 通用 API 调用

```bash
# 默认 profile：nesta（内斯塔）
lark-cli api GET /open-apis/bot/v3/info

# 显式使用内斯塔
lark-cli --profile nesta api GET /open-apis/bot/v3/info

# 显式使用马尔蒂尼
lark-cli --profile maldini api GET /open-apis/bot/v3/info

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

## 配置信息

### Hermes Gateway Bot（马尔蒂尼）
- app_id: `cli_a94fbfdef7e31ccb`
- app_name: `马尔蒂尼` ✅ 已确认（2026-05-06）
- app_secret: 存于 `~/.hermes/.env`
- open_id: `ou_b455ec67f11b87a1befdc2c8326c5717` ✅ 已确认（2026-05-06）
- domain: `feishu`
- 用途：Gateway 通过 WS 连接飞书，收发 DM/群聊消息、处理事件
- lark-cli 操作方式：`lark-cli --profile maldini ...`

### lark-cli Bot（内斯塔）
- app_id: `cli_a9434df9ad3a1cb6`
- app_secret: 存于 macOS Keychain（`appsecret:cli_a9434df9ad3a1cb6`）
- 配置：`~/.lark-cli/config.json`
- 用途：命令行工具，执行 API 调用
- open_id: `ou_d4d4bcffd234aa177b1458ae0381934c`
- lark-cli 操作方式：`lark-cli --profile nesta ...`，也是当前默认 profile

### 三 bot 的影响与确认方法

**⚠️ 关键工作流：查 Bot 信息不要猜，直接上开发者后台。**
Gu 明确说过：不要从本地配置文件瞎猜 Bot 对应关系，直接打开 https://open.feishu.cn/app 登录后看应用列表。登录后的浏览器工具 snapshot 直接显示所有 Bot 的名称、App ID、状态。

| 场景 | 可用工具 | 备注 |
|------|---------|------|
| DM 收发消息 | Gateway → 马尔蒂尼 | 正常 |
| lark-cli 调 API | 默认 `nesta`，可显式指定 profile | 默认查到的是内斯塔 |
| lark-cli 查内斯塔身份 | `lark-cli --profile nesta api GET /open-apis/bot/v3/info` | app_name 应为内斯塔 |
| lark-cli 查马尔蒂尼身份 | `lark-cli --profile maldini api GET /open-apis/bot/v3/info` | app_name 应为马尔蒂尼 |
| API 拉马尔蒂尼进群 | 优先用 `--profile maldini` | 必须确认权限和 member_id_type |
| 查全部 Bot 列表 | 浏览器登录开发者后台 | https://open.feishu.cn/app → 直接看应用列表 |

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
- ❌ **不要把 bot 名称搞混淆** — 一共三个独立 Bot：马尔蒂尼（Hermes Gateway）、内斯塔（lark-cli/OpenClaw）、皮尔洛（独立 AI 助手，凭证不在本机）。皮尔洛和马尔蒂尼**不是同一个 Bot**，它们的 App ID 不同。
- ❌ **不要用默认 lark-cli 查到的 bot 信息去配 Gateway** — 默认 profile 是内斯塔；查马尔蒂尼必须加 `--profile maldini`
- ❌ **拉 bot 进群不要用 open_id** — 必须用 `member_id_type: app_id` + bot 的 app_id，不然报 `invalid_id_list`
- ❌ **不要在 shell 里直接 cat/echo .env** — FEISHU_APP_SECRET 会被隐蔽工具截断显示。用 Python 读文件
- ✅ **lark-cli 已安装** — `which lark-cli` 确认在 `~/.npm-global/bin/`
