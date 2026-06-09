---
name: hermes-desktop-browser
description: >
  Hermes Desktop 内置 visible browser（可见浏览器窗格）的操作指南。
  覆盖 navigate、snapshot、click、type 四个工具的使用模式、
  已知限制和替代路径。不覆盖 headless browser_* 或 computer_use。
version: 1.1.0
platforms: [macos]
metadata:
  hermes:
    tags: [visible-browser, desktop, hermes-app, gui]
    category: desktop
    related_skills: [macos-computer-use]
---

# Hermes Desktop Visible Browser

Hermes Desktop 内置了一个可见浏览器窗格，用户可以直接看到页面渲染。
它通过 `visible_browser_*` 工具族进行操作。

## 工具

| 工具 | 功能 |
|------|------|
| `visible_browser_navigate` | 导航到 URL，返回 URL + bodyText 摘要 |
| `visible_browser_snapshot` | 获取页面 bodyText（纯文本内容），**不返回 `@eN` ref ID** |
| `visible_browser_click` | 点击 ref ID 元素（当前 Desktop 版本尚未实现 click 执行） |
| `visible_browser_type` | 在页面输入框输入文本。ref 参数**可选**，省略时自动定位第一个可编辑元素 |

## 核心限制：snapshot 不返回 ref ID

`visible_browser_snapshot` 返回的是 `bodyText` 纯文本（页面可读文字内容），
**不包含 `@eN` 格式的交互元素引用**。这与 headless `browser_snapshot` 不同。

**影响**：`visible_browser_click` 虽然接受 ref 参数，但 snapshot 无法提供 ref，
且当前 Desktop build 尚未实现 click 执行，因此实际上 **click 不可用**。

**可以做的**：
- `visible_browser_navigate` → 导航并获取页面文字
- `visible_browser_type` → 自动定位输入框并输入文字
- `visible_browser_snapshot` → 读取页面文字内容（如 ChatGPT 的流式回复）

## 输入与提交

`visible_browser_type` 不自动提交表单。输入文字后需要使用 **换行符 `\n`** 触发提交：

```
visible_browser_type(text="消息内容")
visible_browser_type(text="\n")  # 发送消息 / 提交表单
```

这等效于在输入框按 Enter。**必须分两次调用**——把 `\n` 嵌入消息文本中（如 `text="消息内容\n"`）不会触发提交，
只会把换行符当作普通文本输入。

### `visible_browser_type` 与 `browser_type` 的行为差异

| 行为 | `browser_type`（headless） | `visible_browser_type`（Desktop） |
|------|--------------------------|----------------------------------|
| 输入前清空字段 | ✅ 自动清空 | ❌ **不清空，追加文本** |
| ref 参数 | 必填 | 可选（自动定位第一个可编辑元素） |

**关键影响**：如果消息未成功发送，输入框中可能还保留上次文字。重新 `visible_browser_type` 不会清空，
会导致文字重复（如 "你好你好"）。发送前先用 `visible_browser_snapshot` 检查 bodyText，
确认输入框中究竟是什么，避免盲目重试。

## 陷阱

### 文字重复
由于 `visible_browser_type` 不清空字段（附加模式），在以下场景会导致文字重复：
- 消息未成功发送时重试输入
- 连续多次 `visible_browser_type` 调用

**规避**：发送前 snapshot 确认输入框状态；必要时重新 `visible_browser_navigate` 刷新页面。

### snapshot 缓存滞后
流式输出期间（ChatGPT "正在思考"），连续 `visible_browser_snapshot` 可能返回相同的 bodyText，
即使页面实际在更新。这是因为 snapshot 存在缓存窗口。遇到连续相同结果时，
**多等 1-2 秒再抓**，不要以连续 2 次相同结果就判定"回复完成"。

## 读取 ChatGPT 回复

ChatGPT 的流式回复会逐字出现在页面 bodyText 中。在 `visible_browser_type(text="\n")` 发送后，
ChatGPT 进入"正在思考"状态，`visible_browser_snapshot` 的 bodyText 会显示"正在思考"→
逐步显示回复内容。多次 snapshot 可跟踪流式输出，直到回复完成（不再变化）。

## URL 经验

| 目标 | 推荐的 URL | 备注 |
|------|-----------|------|
| ChatGPT | `https://chatgpt.com` | 已验证可用，无需使用旧域名 |

## 网络注意事项

Visible browser 在国内网络环境下访问境外站点可能超时（`ERR_CONNECTION_TIMED_OUT`）。
这通常是因为 visible browser 不走系统代理。确认代理配置后再重试。

## 何时使用 visible browser vs headless browser

| 场景 | 选择 | 原因 |
|------|------|------|
| 用户需要**看到**页面 | visible | 用户可见窗格 |
| 需要复杂交互（点击、滚动、多步操作） | headless `browser_*` | headless 支持完整的 click/scroll/snapshot ref |
| 只需输入文字 + 读取回复 | visible | type + snapshot 足够 |
| 需要截图/SOM | `computer_use` | macOS 桌面自动化

## 参考文件

- `references/chatgpt-session-log.md` — chatgpt.com 完整交互实录（2026-06-07），含操作序列和关键发现
