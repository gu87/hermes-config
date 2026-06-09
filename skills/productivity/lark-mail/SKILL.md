---
name: lark-mail
description: 飞书邮箱操作 — 未读邮件检查、内容读取、每日汇总。使用 lark-cli mail 子命令完成邮件的 triage（列表）、message（内容读取）、reply（回复）、send（发送）等操作。覆盖 device auth 授权流程和常见权限坑。
category: productivity
---

# Lark Mail — 飞书邮箱操作

通过 `lark-cli mail` 子命令完成飞书邮箱的全部操作。前提：飞书应用已开通邮件权限（`mail:user_mailbox:readonly` 等 scope），且 user token 有效。

## 触发条件
- 查看邮件 / 未读邮件
- 读某封邮件内容
- 回复 / 转发 / 发邮件
- 设置每日邮件检查 cron

---

## 权限与授权

### 检查当前权限状态
```bash
lark-cli auth status
lark-cli auth scopes | grep mail
```

关键判断：
- `scopes` 中有 `mail:user_mailbox:message:readonly` 和无 `mail` 相关 scope → 需在开放平台添加权限
- `auth status` 中 `user identity: missing` → 需重新登录（新权限未包含在旧 token 中）

### Device Auth 授权流程
```bash
# 1. 获取 device code 和授权 URL
lark-cli auth login --domain mail --no-wait --json

# 输出中：
#   device_code: 用于完成授权
#   verification_url: 发给用户打开的链接
#   expires_in: 600（10 分钟过期）

# 2. 用户打开 verification_url 点「授权」后，完成登录
lark-cli auth login --device-code <device_code>
```

**注意**：授权 URL 是标准飞书 OAuth device flow，用 `open` 命令在 Lark 桌面客户端中打开即可：
```bash
open "<verification_url>" -a Lark
```

---

## 邮件列表（Triage）

```bash
# 列出最近 20 封邮件（表格格式）
lark-cli mail +triage --max 20

# 仅未读邮件（JSON 输出，方便程序解析）
lark-cli mail +triage --filter '{"is_unread":true}' --max 50 --format json 2>/dev/null

# 按文件夹筛选
lark-cli mail +triage --filter '{"folder":"INBOX"}' --max 10

# 全文搜索（max 50 字符）
lark-cli mail +triage --query "百威" --max 10
```

**filter 支持的字段**：`folder`, `folder_id`, `label`, `label_id`, `is_unread`, `from`, `to`, `cc`, `bcc`, `subject`, `has_attachment`, `time_range`

**输出字段**（JSON）：`date`, `from`, `subject`, `message_id`, `thread_id`, `folder`, `labels`

---

## 邮件内容（Message）

```bash
# 读取单封邮件完整内容
lark-cli mail +message --message-id "<message_id>"

# 批量读取（多个 message_id 逗号分隔）
lark-cli mail +messages --message-ids "<id1>,<id2>"

# 读取整个会话
lark-cli mail +thread --thread-id "<thread_id>"
```

**输出内容**：
- `data.body_plain_text` — 纯文本正文（直接用于摘要）
- `data.body_html` — HTML 正文（保留格式）
- `data.attachments` — 附件列表
- `data.cc` / `data.to` / `data.head_from` — 收发件人信息
- `data.date_formatted` — 日期

---

## 其他操作

```bash
# 回复（保存为草稿）
lark-cli mail +reply --message-id "<id>" --body "回复内容"

# 回复所有人
lark-cli mail +reply-all --message-id "<id>" --body "回复内容"

# 转发
lark-cli mail +forward --message-id "<id>" --to "someone@example.com"

# 新建邮件
lark-cli mail +send --to "someone@example.com" --subject "主题" --body "正文"

# 发送草稿（--confirm-send 直接发送，否则保存草稿）
lark-cli mail +reply --message-id "<id>" --body "..." --confirm-send
```

---

## 每日未读检查 Cron 模板

```yaml
# cronjob create 参数
name: 每日邮件未读检查
schedule: "30 10 * * *"
model: opencode_go_deepseek_flash
enabled_toolsets: ["terminal"]
```

**Prompt 核心流程**：
1. `lark-cli mail +triage --filter '{"is_unread":true}' --max 50 --format json` — 获取未读列表
2. 对每封未读邮件执行 `lark-cli mail +message --message-id "<id>"` — 读取内容
3. 从 `data.body_plain_text` 提取摘要（每封 2-5 句）
4. 无未读邮件时回复 `[SILENT]`
5. 含"紧急""赔付""合同""Saving""deadline"等关键词的邮件标注 ⚠️

---

## Pitfalls

| 坑 | 表现 | 修复 |
|----|------|------|
| User token 缺失 | `need_user_authorization` 错误 | `lark-cli auth login --domain mail` |
| 权限 scope 不足 | 404 或权限拒绝 | 飞书开放平台 → 权限管理 → 添加 mail 相关 scope → 发布 → 重新 auth login |
| Device code 过期 | 10 分钟后 auth login 失败 | 重新执行 auth login 获取新 code |
| `+triage` 的 `page_size` 字段不存在 | 报 `unknown field "page_size"` | 用 `--max` 不是 `--filter '{"page_size":10}'` |
| `--filter` JSON 格式错误 | JSON 解析失败 | 注意单双引号：外层单引号，JSON 内双引号 `'{"is_unread":true}'` |