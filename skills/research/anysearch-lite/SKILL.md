---
name: anysearch-lite
description: Low-token external search for DeepSeek-TUI worker tasks. Use when current external information, docs, release notes, issue references, or URL extraction are needed. Prefer local grep/read tools for repository code.
agents:
  - deepseek-tui
---

# AnySearch Lite

Use this skill only for bounded external information retrieval.

## DeepSeek Worker Search Policy

1. Prefer local repository tools first: `grep_files`, `file_search`, `read_file`, `git_history`.
2. Use AnySearch only when the question needs external/current information or documentation.
3. Never perform open-ended research. Search once, summarize, and stop unless the user asks for more.
4. Return at most 3-5 useful sources.
5. For URL reading, prefer the existing `scrapling-fetch` MCP when a URL is already known.
6. Do not send secrets, private code, private file paths, customer data, or API keys to AnySearch.
7. Always produce a compact result: source title, URL, one-line relevance, and recommended next action.

## Commands

Use the existing AnySearch CLI:

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
