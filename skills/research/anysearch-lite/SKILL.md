---
name: anysearch-lite
description: Low-token external search for DeepSeek-TUI worker tasks. Use when current external information, docs, release notes, issue references, or URL extraction are needed. Prefer local grep/read tools for repository code.
agents:
  - deepseek-tui
  - hermes-internal
---

# AnySearch Lite

Use this skill only for bounded external information retrieval.

## AnySearch MCP (Preferred — Hermes Native)

AnySearch 已在 Hermes config 中注册为 MCP 工具（`mcp_anysearch_*`），可通过 4 个工具直接调用：

| 工具 | 用途 |
|------|------|
| `mcp_anysearch_search(query, max_results, domain)` | 通用/垂直搜索 |
| `mcp_anysearch_batch_search(queries=[...])` | 并行搜索 2-5 个 query |
| `mcp_anysearch_extract(url)` | 抓取 URL 全文转 Markdown |
| `mcp_anysearch_get_sub_domains(domain)` | 获取垂直领域子分类 |

**不需要 API key**（匿名可用，有低限流）。推荐 MCP 方式。

### MCP 配置方式

AnySearch 通过 `npx mcp-remote https://api.anysearch.com/mcp` 代理注册。配置位于 `mcp_servers.anysearch`。

⚠️ **Key 配置限制**：Hermes remote MCP 不支持 `headers` 字段传递 Authorization header。mcp-remote 也不支持 `--header` 参数。API key 需要：
- 写入 `env.ANYSEARCH_API_KEY` 字段（mcp-remote 子进程继承）
- 同时写入 `~/.zshrc` 供新终端继承
- 然后重启 Hermes gateway 才能生效

实际测试中**匿名模式**（无 key）可以正常搜索和抓取，限流对每日 2 次 cron 任务（早报+晚报各 5-10 次搜索）足够。

### Cron 任务集成模式

Cron prompt 中应直接指定 AnySearch MCP 工具，禁止使用 Playwright/Chrome/browser_navigate：

```
## 搜索方法
1. 使用 mcp_anysearch_search 进行搜索
2. 关键文章使用 mcp_anysearch_extract 抓取全文（自带 Markdown 转换）
3. 优先使用 mcp_anysearch_batch_search 并行搜索（一次最多5个query）
4. 禁止使用 Playwright、Chrome 或 browser_navigate 工具
```

## CLI Fallback（当 MCP 不可用时）

Use the existing AnySearch CLI when the MCP tools are unavailable:

```bash
python3 /Users/gu/.codex/skills/anysearch/scripts/anysearch_cli.py search "query" --max_results 5
```

Batch independent searches:

```bash
python3 /Users/gu/.codex/skills/anysearch/scripts/anysearch_cli.py batch_search --queries '[{"query":"q1","max_results":3},{"query":"q2","max_results":3}]'
```

Extract a page when `scrapling-fetch` is unavailable or failed:

```bash
python3 /Users/gu/.codex/skills/anysearch/scripts/anysearch_cli.py extract "https://example.com/page"
```

## Search Policy

1. Prefer local repository tools first: `grep_files`, `file_search`, `read_file`, `git_history`.
2. Use AnySearch only when the question needs external/current information or documentation.
3. Never perform open-ended research. Search once, summarize, and stop unless the user asks for more.
4. Return at most 3-5 useful sources.
5. For URL reading, prefer `mcp_anysearch_extract` when MCP is available, or the existing `scrapling-fetch` MCP when a URL is already known.
6. Do not send secrets, private code, private file paths, customer data, or API keys to AnySearch.
7. Always produce a compact result: source title, URL, one-line relevance, and recommended next action.

## Output Format

After searching, respond with:

```text
Search summary:
- Source: <title>
  URL: <url>
  Why it matters: <one sentence>

Verdict: <one sentence>
Next action: <one sentence>
```

If AnySearch fails, say so briefly and do not keep retrying.