---
name: html-anything
description: HTML Anything — 本地 AI 驱动的 HTML 编辑器。将 Markdown/CSV/JSON/SQL 等内容通过本地 Claude Code 自动生成精美 HTML，支持 75 套模板和公众号/小红书/知乎一键发布。
tags: [html-anything, html-editor, agent, publishing, wechat, xiaohongshu]
agents: [claude, designer, hermes-internal]
---

# HTML Anything 集成

## 部署位置

- **项目路径**: `~/Projects/html-anything/`
- **运行端口**: `14732`
- **服务管理**: launchd 常驻（`~/Library/LaunchAgents/com.html-anything.plist`），开机自启 + 崩溃自动重启

## 服务管理

### 当前状态
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:14732
# 200 = 正常运行
```

### 重启
```bash
launchctl kickstart -k gui/$(id -u)/com.html-anything
```

### 停止
```bash
launchctl unload ~/Library/LaunchAgents/com.html-anything.plist
```

### 开机自启
已通过 launchd 配置 `KeepAlive=true` + `RunAtLoad=true`，Mac 重启后自动恢复，无需手动干预。
lsof -ti :14732 | xargs kill
```

## API 接口

### POST /api/convert

将内容通过本地 AI agent 转换为 HTML。

**请求体 (JSON):**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent` | string | ✅ | Agent 名称。可选: `claude` / `codex` / `cursor` / `gemini` / `copilot` / `opencode` / `qwen` / `aider` |
| `templateId` | string | ✅ | 模板 ID。见下方列表 |
| `content` | string | ✅ | 要转换的内容 (Markdown/CSV/JSON/SQL/纯文本) |
| `format` | string | ❌ | 输入格式 (`markdown` / `csv` / `json` / `sql` / 自动识别) |
| `model` | string | ❌ | 具体模型名 |
| `editFromHtml` | string | ❌ | 编辑模式下，已有的 HTML（用于最小差异编辑） |
| `editFromContent` | string | ❌ | 编辑模式下，旧的内容文本 |

**返回:** SSE 流式响应，每次收到新 HTML 片段。

### GET /api/agents

获取当前系统可用的 coding agent 列表。

## 可用模板 (精选)

| 模板 ID | 用途 | 适合场景 |
|---------|------|---------|
| `article-magazine` | 杂志风格文章 | 公众号长文 |
| `card-xiaohongshu` | 小红书卡片 | 小红书笔记 |
| `card-twitter` | Twitter/X 卡片 | 社交媒体 |
| `deck-pitch` | Pitch Deck | 提案方案 |
| `deck-product-launch` | 产品发布 Deck | 产品介绍 |
| `data-report` | 数据报告 | 数据可视化 |
| `dashboard` | 数据看板 | 指标展示 |
| `deck-hermes-cyber` | Hermes 赛博主题 | 架构报告、技术文档 |
| `blog-post` | 博客文章 | 技术/营销文章 |

完整列表: `~/Projects/html-anything/src/lib/templates/skills/` (共 75 个模板)

## 在 Hermes 多Agent系统中使用

### 触发词

当 Gu 说「输出 HTML」「生成页面」「做一张卡片」「转成网页」「用 HTML Anything」时，Coordinator 必须优先委托 **Designer 视觉设计师** 调用此服务。**Coordinator 不得自己手写 HTML**——HTML 生成属视觉交付，走分工流程。

- **架构/技术报告** → 模板 `deck-hermes-cyber`，委托 Designer
- **方案/策划类** → Pirlo 负责内容结构，Designer 负责 HTML 视觉生成
- **公众号长文** → 模板 `article-magazine`，委托 Designer

### Agent 调用流程

**委托给 Claude（代码/技术类 HTML）:**
```
Claude，用 HTML-Anything 把以下内容转成 HTML：
- 模板: article-magazine
- 内容: [Markdown 内容]
- 保存到: /Users/gu/Desktop/output.html
```

**委托给 Designer（视觉型 HTML）:**
```
Designer，把这个商业方案用 HTML-Anything 生成 deck-pitch 模板的 HTML，
保存到桌面。
```

### 标准 curl 命令（Agent 执行）

```bash
# 第一步：确认服务在线
curl -s -o /dev/null -w "%{http_code}" http://localhost:14732

# 第二步：发送内容，生成 HTML
curl -s -X POST http://localhost:14732/api/convert \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "claude",
    "templateId": "article-magazine",
    "content": "你的 Markdown 内容（需要 JSON 转义）",
    "format": "markdown"
  }' > /tmp/html-output.txt
```

### 从 Hermes 工具调用
```python
from hermes_tools import terminal

# 先确认服务在运行
result = terminal('curl -s -o /dev/null -w "%{http_code}" http://localhost:14732')
if result["output"] == "200":
    # 发送内容
    result = terminal('''curl -s -X POST http://localhost:14732/api/convert \\
      -H "Content-Type: application/json" \\
      -d '{"agent":"claude","templateId":"card-xiaohongshu","content":"# 标题...","format":"markdown"}' ''')
```

## 实操经验 (2026-05-16 验证)

| 指标 | 数据 |
|------|------|
| 输入 | 7KB Markdown（含表格、代码块） |
| 模板 | article-magazine |
| 模型 | Claude Opus |
| 生成 HTML | 27KB（完整自包含，含样式+脚本） |
| 耗时 | ~5 分钟 |
| 花费 | ~$0.36 |

**SSE 解析注意:** API 返回的是 SSE 流，HTML 文本分布在多个 `data: {"type":"delta","text":"..."}` 事件中。需要用 Python 解析 JSON 提取并拼接。参考 `references/integration-patterns.md`。

## 注意事项

1. **服务常驻** — 已通过 launchd 配置开机自启 + KeepAlive，Mac 重启后自动恢复
2. **依赖 Claude Code** — 调用时使用 `agent: "claude"`，需要 `claude` CLI 已登录
3. **磁盘空间** — 项目约 13MB，pnpm install 后约几百 MB
4. **首次请求较慢** — 因为涉及 Claude Code 冷启动和模板加载
5. **SSE 流式响应** — API 返回的是流式数据，会逐步返回生成的 HTML
6. **端口 14732** — 非常用端口，避免被其他项目冲突
7. **委托模式** — 涉及安装/部署/配置 HTML Anything 的任务，委托 技术翻译官 执行
8. **大内容用文件传参** — 超过 ~2KB 的内容不要直接拼 JSON 字符串，先 `write_file` 到 `/tmp/html-anything-payload.json`，再用 `curl -d @文件路径` 传入，避免 shell 转义和 JSON 嵌套引号问题
9. **execute_code 中 curl 的 f-string 陷阱** — 用 `execute_code` + Python f-string 构造 curl 命令时，`%{http_code}` 和 `%{time_total}` 会被 Python 当成格式化变量。必须用 `{{http_code}}` 双花括号转义，或直接用 `subprocess.run` 传列表参数
