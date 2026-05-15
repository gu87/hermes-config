---
name: playwright-mcp
description: Playwright MCP — 自动化浏览器测试工具。Codex 用它在验收代码时跑端到端测试，模拟用户操作，检查页面交互是否正常。
tags: [testing, automation, e2e, playwright, code-review]
agents: [deepseek-tui, claude, codex]
---

# Playwright MCP — 自动化验收测试

## 用途

Codex 在审查前端/网页改动时，用 Playwright MCP 跑端到端测试：
- 页面能不能正常加载
- 按钮能不能点
- 表单能不能提交
- 有没有 JS 报错

## 使用方式

Playwright MCP 已配置为 Hermes MCP 服务器，通过 MCP 工具调用。

## Codex 验收流程

1. 拉取代码变更 → 理解改动范围
2. 启动目标页面 → 用 Playwright 截图确认渲染
3. 模拟用户操作 → 点击、输入、提交
4. 检查控制台 → 有无 JS 报错
5. 确认响应式 → 关键页面在移动端是否正常

## 注意

- Playwright MCP 需要目标服务在本地运行
- 如果改的是后端接口，用 curl/Python 测，不用 Playwright
- 重点测改动涉及的路由和交互，不是全量回归
