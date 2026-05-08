---
name: obscura-headless-browser
description: Obscura — Rust 写的轻量 headless 浏览器，用于网页抓取和数据提取。57MB 二进制，30MB 内存，V8 引擎，CDP 协议兼容。安装于 ~/bin/obscura。补充 Chrome 而非替代。
tags: [obscura, headless, browser, web-scraping, cdp, rust]
---

# Obscura 使用手册

## 概述

Obscura 是一个 Rust 编写的轻量级 headless 浏览器（v0.1.0），使用真正的 V8 引擎执行 JavaScript，支持 Chrome DevTools Protocol（CDP）。

**核心定位**：轻量 fetch/scrape 工具，**补充** Chrome headless 而非替代。适合简单网页内容提取，不适合需要截图/CSS 渲染/完整 Puppeteer 兼容的场景。

## 安装位置

```bash
~/bin/obscura          # 57MB 主二进制
~/bin/obscura-worker   # 55MB scrape 并发 worker
```

## 何时用 Obscura vs Chrome

| 场景 | 用 Obscura | 用 Chrome |
|------|-----------|-----------|
| 简单网页内容提取（fetch + eval） | ✅ 首选 | ❌ 太重 |
| 批量 URL 链接/标题抽取 | ✅ scrape 命令 | ❌ |
| 返回纯文本/HTML/链接 | ✅ dump 模式 | ❌ |
| 需要 JS 执行 | ✅ V8 引擎 | ✅ |
| 需要截图/视觉分析 | ❌ 不支持 | ✅ |
| 需要 CSS 渲染/布局计算 | ❌ 无渲染管线 | ✅ |
| 复杂的 Puppeteer 用户交互 | ❌ CDP 兼容性在打磨中 | ✅ |
| 反爬/stealth 场景 | ✅ 内置 | ❌ 需配置 |
| `browser_vision` / 视觉操作 | ❌ | ✅ |

## CLI 命令

### fetch — 单页抓取

```bash
# 获取页面标题
~/bin/obscura fetch https://example.com --eval "document.title" --quiet

# 提取纯文本
~/bin/obscura fetch https://example.com --dump text --quiet

# 提取 HTML
~/bin/obscura fetch https://example.com --dump html --quiet

# 提取所有链接（带文本）
~/bin/obscura fetch https://example.com --dump links --quiet

# 自定义 UA
~/bin/obscura fetch https://example.com --user-agent "Mozilla/5.0 ..." --eval "document.title" --quiet

# 带选择器等待 + JS eval
~/bin/obscura fetch https://example.com --selector "h1" --eval "document.querySelector('h1').textContent" --quiet

# 设置超时（默认 30s）
~/bin/obscura fetch https://slow-site.com --timeout 60 --quiet
```

**重要 flag**：
- `--quiet`：抑制输出横幅（推荐脚本用）
- `--timeout <N>`：导航超时秒数（默认 30）
- `--eval <JS>`：页面加载后执行 JS 表达式
- `--selector <CSS>`：等待 CSS 选择器出现（最多等 `--wait` 秒，默认 5）
- `--dump <html|text|links>`：输出模式
- `--user-agent <UA>`：自定义 User-Agent
- `--stealth`：启用反检测（需编译时含 stealth feature；下载的二进制可能不支持）
- `--proxy <URL>`：HTTP/SOCKS5 代理

### scrape — 并发批量抓取

```bash
# 批量提取标题（10 并发）
~/bin/obscura scrape url1 url2 url3 --eval "document.title" --concurrency 10 --format json

# 批量提取特定内容
~/bin/obscura scrape url1 url2 --eval "document.querySelector('h1')?.textContent" --concurrency 25
```

**注意**：`obscura-worker` 必须和 `obscura` 在同一目录下。

### serve — CDP 服务器模式

```bash
# 启动 CDP WebSocket 服务器
~/bin/obscura serve --port 9222

# 带代理
~/bin/obscura serve --port 9222 --proxy socks5://127.0.0.1:1080
```

客户端连接方式：
```javascript
// Puppeteer
import puppeteer from 'puppeteer-core';
const browser = await puppeteer.connect({ browserWSEndpoint: 'ws://127.0.0.1:9222/devtools/browser' });

// Playwright
import { chromium } from 'playwright-core';
const browser = await chromium.connectOverCDP({ endpointURL: 'ws://127.0.0.1:9222' });
```

## 已知限制和 Pitfalls

1. **默认代理行为**：Obscura 默认会通过 `http://127.0.0.1:7890` 路由 HTTP 流量（源码硬编码的 proxy 检测）。如果没跑 Clash/V2ray 等透明代理，遇到 CDN 类网站（Fastly/Cloudflare）会直接连接失败（如 Hacker News、httpbin.org）。**解法**：目前没有 `--no-proxy` flag，如果目标网站连不上但 curl 能连，就是这个问题。

2. **部分 CDN 网站不可达**：某些网站（如 Hacker News、httpbin.org）在测试中连接失败——不是 Obscura 的 bug，是该网络环境下 CDN 被限制或代理干扰。遇到这种情况切 Chrome 浏览器工具即可。

3. **`--dump text` 包含 `<style>` 内容**：文本抽取模式会保留 style/script 标签内的文本，不是纯 visible text。需要干净文本时用 `--eval` 配合 JS 过滤。

4. **不支持截图**：CDP 的 `Page.screenshot` 没实现，需要视觉分析的任务必须用 Chrome。

5. **CDP 兼容性在打磨中**：部分 Puppeteer/Playwright 功能可能需要 workaround（见 issue #122）。

6. **无 `--version` flag**：用 `--help` 查看帮助。

7. **`scrape` 命令需要 `obscura-worker`**：两个二进制必须在同目录。

8. **默认 timeout 较短**（30s 导航，5s 等待选择器），动态页面需自行加长。

9. **终端 CWD 损坏（terminal session 永久失效）**：如果在 `terminal()` 中 `cd` 到一个临时目录然后删除了它，shell 的 CWD（当前工作目录）变成无路径，**所有后续 `terminal()` 调用都报 `FileNotFoundError`**，即使指定 `workdir` 参数也无法绕过。**解法**：

   a) 用 `execute_code()` 中的 `subprocess.run()` 绕过损坏的 session（不退出现有会话）：
   ```python
   import subprocess
   r = subprocess.run(["/Users/gu/bin/obscura", "fetch", url, "--eval", "document.title", "--quiet"], capture_output=True, text=True, timeout=15)
   ```
   
   b) 修复 session：recreate 那个被删除的目录，cd 到正常路径再清理：
   ```bash
   mkdir -p 那个被删除的目录  # 让 CWD 重新有效
   cd /Users/gu              # 切到稳定路径
   rm -rf 那个被删除的目录    # 再安全删除
   ```
   
   **预防**：删除目录前先 `cd /tmp` 或 `cd ~` 切出去，不要在目录里直接删。

## Hermes 集成模式

**推荐用法**：通过 `terminal()` 直接调用 CLI，而非走 CDP server 模式。

```bash
# 提取页面关键内容
~/bin/obscura fetch $URL --eval "document.title + '|' + (document.querySelector('meta[name=description]')?.content || '')" --quiet

# 页面文本提取（替代 html2text）
~/bin/obscura fetch $URL --dump text --quiet

# 获取所有链接
~/bin/obscura fetch $URL --dump links --quiet
```

## 初始安装命令

```bash
gh release download -R h4ckf0r0day/obscura --pattern "obscura-aarch64-macos.tar.gz" --dir /tmp
cd /tmp && tar xzf obscura-aarch64-macos.tar.gz
cp obscura ~/bin/ && cp obscura-worker ~/bin/ && chmod +x ~/bin/obscura ~/bin/obscura-worker
rm -f /tmp/obscura-aarch64-macos.tar.gz
```

## 参考

- `references/test-results.md` — 2026-05-07 实测结果（含通过/失败清单）

