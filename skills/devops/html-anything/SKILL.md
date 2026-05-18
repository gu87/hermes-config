---
name: html-anything
description: HTML Anything — 本地 AI 驱动的 HTML 编辑器。将 Markdown/CSV/JSON/SQL 等内容通过本地 Claude Code 自动生成精美 HTML，支持 75 套模板和公众号/小红书/知乎一键发布。
tags: [html-anything, html-editor, agent, publishing, wechat, xiaohongshu]
---

# HTML Anything 集成

## 部署位置

- **项目路径**: `~/Projects/html-anything/`
- **运行端口**: `14732`
- **启动命令**: `cd ~/Projects/html-anything && pnpm dev -p 14732`

## 服务管理

### 启动
```bash
cd ~/Projects/html-anything && pnpm dev -p 14732
```
建议用 background 模式启动。

### 验证运行
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:14732
# → 200
```

### 停止
```bash
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
| `dating-web` | 社交风格 | 创意页面 |
| `blog-post` | 博客文章 | 技术/营销文章 |

完整列表: `~/Projects/html-anything/src/lib/templates/skills/` (共 75 个模板)

## 调用方式 (从 Hermes)

### 直接 curl 调用
```bash
curl -X POST http://localhost:14732/api/convert \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "claude",
    "templateId": "card-xiaohongshu",
    "content": "你的Markdown内容...",
    "format": "markdown"
  }'
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

1. **服务必须保持运行** — 当前是 `pnpm dev` 开发模式，若 Mac 重启需手动重新启动
2. **依赖 Claude Code** — 调用时使用 `agent: "claude"`，需要 `claude` CLI 已登录
3. **磁盘空间** — 项目约 13MB，pnpm install 后约几百 MB
4. **首次请求较慢** — 因为涉及 Claude Code 冷启动和模板加载
5. **SSE 流式响应** — API 返回的是流式数据，会逐步返回生成的 HTML
6. **端口 14732** — 非常用端口，避免被其他项目冲突
7. **委托模式** — 涉及安装/部署/配置 HTML Anything 的任务，委托 内斯塔 执行（用户反感我自己直接干）
8. **系统重启后需手动重启** — `pnpm dev` 是前台进程，Mac 重启后服务不会自启。需手动 `cd ~/Projects/html-anything && pnpm dev -p 14732`
9. **SSE 解析** — API 返回的是流式 SSE 数据。用 Python JSON 解析器提取 delta 事件中的 text 字段。详见 `references/sse-parsing.md`
