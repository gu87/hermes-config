---
name: hermes-cron-management
description: Hermes Agent cron job lifecycle — create, update, troubleshoot, and ensure scheduled tasks fire correctly. Covers the cronjob tool API, Gateway dependency, environment setup, and common failure modes.
tags: [hermes, cron, scheduler, automation]
agents: [hermes]
---

# Hermes Cron Job Management

## Overview

Hermes has a built-in cron scheduler. Jobs are stored in `~/.hermes/cron/jobs.json` and fired by the **Gateway's tick mechanism** — meaning the Gateway must be running for cron jobs to execute automatically.

## The `cronjob` Tool — Critical Pitfalls

### ⚠️ PITFALL #1: `cronjob(action='update')` 更新 prompt 后必须验证

`cronjob(action='update', job_id='...', prompt='...')` 是正确的 prompt 修改方法（不要用 sed/crontab -e 手工改 JSON）。但**更新后务必验证**，因为存在两个静默失败场景：

1. **Gateway 重启回滚**：config/cron 变更后 Gateway 重启检测到 YAML 损坏 → 自动回滚 → prompt 丢失
2. **手动编辑 JSON 未持久化**：`sed`/`crontab -e` 改 JSON 可能在 Gateway 重启时被覆盖

**验证三步**：

```bash
# Step 1: 查看 cronjob list，确认 prompt_preview 包含新内容
cronjob(action='list')

# Step 2: 立即手动跑一次（不等定时触发）
cronjob(action='run', job_id='xxx')

# Step 3: 用 session_search 查 actual cron session，看 run 的时候用了什么 prompt
session_search(query="cron_job_id_xxx", limit=1, sort="newest")
# → 检查 bookend_start 的第一条 user message 是否包含新 prompt 的搜索结果
# → 如果还是旧 prompt（如"使用 web_search 和 Playwright"），说明更新未生效
```

**为什么 session_search 比 prompt_preview 更可靠**：prompt_preview 只显示截断的前几十字，而 session_search 的 bookend_start 包含 cron 实际收到的完整 system prompt，能精确判断搜索工具指令是否更新。

### ⚠️ PITFALL #2: `cronjob(action='update')` ALWAYS REQUIRES A `prompt` PARAMETER

Even if you just want to change the schedule or toolsets, you MUST pass the prompt. It's not an optional field — omitting it causes data loss. Always read the job first and re-pass the full prompt.

## Cron Jobs Don't Fire Without the Gateway

The cron scheduler runs inside Hermes Gateway. If the Gateway isn't running, **cron jobs will NOT fire**.

**Check Gateway status:**
```bash
hermes gateway status
```

**Start Gateway if needed:**
```bash
# Background process (preferred — bypasses launchd issues)
terminal(background=true): hermes gateway run --replace

# Or via launchd
hermes gateway start
```

**Verify gateway is alive:**
```bash
ps aux | grep hermes | grep -v grep
# Should show a hermes gateway process
```

## Environment Setup for Cron Jobs

### Python Dependencies

Hermes venv (`~/.hermes/hermes-agent/venv/`) uses **uv** for package management, NOT pip.

```bash
# Inside Hermes venv
uv pip install <package>
```

Note: `python3 -m pip` does NOT work in the Hermes venv (pip is not installed).

### Chrome CDP for Browser-Based Cron Tasks

If the cron job uses browser automation (e.g., a grab/purchase script), Chrome must be running with `--remote-debugging-port=9222`:

```bash
# Start regular Chrome with CDP
terminal(background=true): /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir="$HOME/.hermes/chrome-profile"

# Verify CDP is ready
curl -s http://localhost:9222/json/version
# → Should return Chrome version JSON
```

Note: Regular Google Chrome works fine — Chrome for Testing is NOT required.

## 二点五、Cron 任务工具约束

Cron 任务的工具调用由两件事共同决定：**prompt 中写了什么** + **config.yaml 中加载了什么 MCP 工具**。两者独立，且都可能出问题。

### 2.5.1 Prompt 中的搜索工具约束

⚠️ **已发生的故障**（2026-06-08）：世界杯营销日报 prompt 写「使用 web_search 和 Playwright 浏览器抓取」。模型在执行搜索时调用了 `browser_navigate` 打开虎扑等页面，Chrome 被拉起后不自动关闭，在 8GB 内存环境中产生显著资源占用。

**当前推荐工具**（2026-06-08 更新）：已切换到 **AnySearch MCP**（`mcp_anysearch_search` + `mcp_anysearch_extract`），不再依赖 Playwright/Chrome。prompt 中明确列出可用工具：

```
## 搜索工具
使用 AnySearch MCP 工具进行搜索和内容提取：
- **mcp_anysearch_search** — 搜索关键词，返回结果摘要
- **mcp_anysearch_extract** — 提取指定 URL 的完整文章内容
- 不依赖 Playwright、Chrome、web_search
```

**规则**：纯搜索+抓取的 cron 任务，prompt 中明确列出「用哪些、不用哪些」，禁止写「浏览器」「Playwright」「Chrome」。

### 2.5.2 Provider 切换 ≠ MCP 工具切换

**⚠️ 已发生的故障**（2026-06-08）：将 cron 任务的 model provider 从 deepseek 切到 opencode-go，但 `config.yaml` 中的 minimax MCP server 仍 `enabled: true`。`mcp_minimax_web_search` 继续被加载，模型仍然可以调用它。

**原理**：MCP 工具由 `config.yaml mcp_servers` 段加载，与模型 provider 独立。切换 provider **不自动禁用旧 MCP 工具**。

**迁移检查清单**：

```
□ 1. 更新 cron 任务 model 字段（per-job model override）
□ 2. 检查 config.yaml mcp_servers 段：旧 provider 的 MCP 是否还 enabled？
   → 如 minimax、volcengine 等
   → 不再使用的设 enabled: false
□ 3. 验证：新 provider + 旧 MCP 不会组合出预期外调用
   → 手动 rerun 一次确认搜索/抓取工具调用链正常
   → 检查 ps aux 确认无 Chrome 残留进程
```

详细案例见 `references/cron-tool-routing-constraints.md`。

## 三、Job Storage & Direct Access

Jobs are stored as JSON:

**File:** `~/.hermes/cron/jobs.json`

```json
{
  "jobs": [
    {
      "id": "16a6b3e04d52",
      "name": "my-cron-job",
      "prompt": "...",
      "schedule": { "kind": "once", "run_at": "..." },
      "state": "scheduled",
      "enabled": true,
      "enabled_toolsets": ["browser", "web", "terminal"]
    }
  ]
}
```

For safe edits (avoiding the cronjob tool's update pitfalls), use `patch` directly on this file.

## Gateway Respawn Patterns

If cron jobs need to survive Mac sleep/wake cycles:
- `hermes gateway run --replace` as a background terminal process
- launchd plist (`~/Library/LaunchAgents/ai.hermes.gateway.plist`) for system-level persistence
- Note: launchd can kill the gateway if drain takes > 60s

## Cron Job States

| State | Meaning |
|-------|---------|
| `scheduled` | Waiting to fire |
| `running` | Currently executing |
| `completed` | Done (one-shot jobs) |
| `paused` | Manually paused |
| `failed` | Execution error |

## `no_agent=True` + Script Pattern (Zero-Token Cron)

For cron jobs that produce deterministic output (fixed-format reports, data dumps, API scrapes), use `no_agent=True` with a standalone script. This saves tokens entirely — the script's stdout is delivered verbatim, no LLM involved.

### When to Use

- Output format is fixed and doesn't need reasoning
- The script does all the work (fetch, parse, format)
- No conditional logic based on content is needed

### Creation Pattern

```bash
# 1. Write the script in ~/.hermes/scripts/<name>.py
# Script prints output to stdout → that's the delivered message

# 2. Create the cron job
cronjob(
    action='create',
    name='Daily Report',
    schedule='0 9 * * *',
    script='my-report.py',     # relative to ~/.hermes/scripts/
    no_agent=True,             # skip LLM, just deliver stdout
    deliver='feishu:oc_xxxxx'  # explicit target
)
```

### Script Contract

- Output to stdout → becomes the delivered message
- Exit code 0 → delivery succeeds
- Exit code non-zero → error alert sent to user
- Empty stdout → SILENT (nothing delivered)

### Real Example: GitHub Trending Top 10 (no_agent=False, script + LLM)

```bash
# Script: ~/.hermes/scripts/github-trending.py
# Fetches GitHub trending data, formats as Markdown candidate list for the LLM
# The LLM then filters, sorts, and writes the final report

cronjob(
    action='create',
    name='GitHub 每日 Trending Top 10',
    schedule='0 10 * * *',        # Morning delivery
    script='github-trending.py',   # Provides trending data as context
    # no_agent=False (default) — LLM reads script output and produces final report
    deliver='feishu:oc_xxxxx',
    model={'provider': 'opencode-go', 'model': 'kimi-k2.6'}  # Per-job model pin
)
```

The script prints Markdown-formatted repo candidates. The LLM loads them, picks the top 10 by relevance to the user's tech stack, and formats a short report.

**When NOT to use no_agent=True:**
- Output needs reasoning, filtering, or prioritization
- The user wants a summary, not raw data
- The script's output format is a data-collection block, not a finished message

### Comparison: no_agent=True vs False

| 维度 | no_agent=True | no_agent=False |
|---|---|---|
| Token 消耗 | 0 | prompt + output tokens |
| 输出内容 | 脚本 stdout 原文 | LLM 重新组织 |
| 脚本职责 | 完整输出 | 提供上下文给 LLM |
| 适用场景 | 固定格式报表 | 需要总结/筛选/判断 |

### Pitfall: CHANGING no_agent After Creation

## Troubleshooting

1. **Job not firing** → Gateway down. Start Gateway.
2. **Job fires but does nothing** → Prompt overwritten (see Pitfall #1). Restore from jobs.json backup or session history.
3. **Chrome CDP fails** → Chrome not started with `--remote-debugging-port`. Start it.
4. **Python import error** → Dependency not installed in Hermes venv. Use `uv pip install`.
5. **Output not delivered** → `deliver` field misconfigured. Use `"origin"` to send output back to the creating chat. For Feishu groups, explicitly set `deliver="feishu:<chat_id>"` — never assume `"origin"` will resolve to the right group.

## Cron Job Failure — 实战诊断流程

当 cron 任务标记为 `last_status: error` 时，按以下顺序诊断：

### Step 1: 看 `delivery_error`
```bash
cronjob(action='list')
# 检查 last_delivery_error 字段
```

| delivery_error 有值？ | 含义 | 下一步 |
|----------------------|------|--------|
| **DNS 解析失败** (`Failed to resolve 'open.feishu.cn'`) | 本地网络不通（Clash 代理关闭 / DNS 漂移） | ❌ 非 LLM 问题。修复本地网络，重新跑一次任务 |
| **403 / 401** | 飞书 token 过期 | 检查飞书凭证有效性 |
| **为空 (null)** | 模型/工具调用阶段失败 | 进入 Step 2 |

### Step 2: 看 agent.log 中的失败模式
```bash
grep '<job_id>' /Users/gu/.hermes/logs/agent.log | grep 'ERROR\|WARNING.*stale\|WARNING.*Broken pipe\|WARNING.*Connection error' | tail -10
```

| 日志模式 | 根因 | 修复 |
|---------|------|------|
| `Stream stale for 180s — no chunks received` → `[Errno 32] Broken pipe` | Provider 服务端断连（DeepSeek 常见） | 换 provider。pin 到 opencode-go 包月池 |
| `APIConnectionError: Connection error`（连续 3+ 次重试全挂） | 本地网络不通（API 和 Delivery 同时失败） | 修复代理，不是模型问题 |
| `quota_exceeded` / `rate_limited` | API 额度耗尽 | 换 fallback 模型或等额度恢复 |
| `Team 'ai-team' does not exist` | Claude Code Mailbox 插件错误 ✅ 无害 | 会自动 auto-join，忽略 |

### Step 3: 快速手动验证
```bash
# 手动 rerun（观察输出是否正常）
cronjob(action='run', job_id='xxx')

# 检查 rerun 后 last_status 是否变为 ok
cronjob(action='list')
```

如果 rerun 成功，说明是瞬时故障（DeepSeek 断连、网络瞬断）。如果连续失败，需要换 provider 或排查网络。

### 实战案例：2026-06-08 双重失败

| 任务 | 时间 | agent.log 模式 | delivery_error | 根因 | 修复 |
|------|------|---------------|----------------|------|------|
| 世界杯早报 | 08:30 | `Stale stream 180s → Broken pipe x3` | null | DeepSeek 服务端断连 | 换 opencode-go 包月池 |
| GitHub Trending | 10:01 | `APIConnectionError x6` | `Failed to resolve open.feishu.cn` | 网络全断（Clash 关闭） | 修复代理后手动 rerun |

**关键判断**：早报的 delivery_error 是空（API 阶段就失败，没到 delivery 阶段）。Trending 的 delivery_error 有 DNS 错误（网络全断，包括 delivery）。这意味着即使早报 API 通了，也无法投递——两个不同根因同时发生。

### ⚠️ PITFALL #6: Gateway 重启可能回滚手工编辑的 config/cron prompt

**已发生**（2026-06-08）：用 `sed`/`Python` 手工编辑 `config.yaml` 后，Gateway 重启检测到 YAML 损坏（缩进错误、JSON 字符串 vs YAML 列表格式不匹配），自动回滚到清洁版本。连带 `mcp_servers` 段和 cron prompt（如存储在 config 相关文件中）一起丢失。

**预防**：
- MCP 服务器配置用 `hermes config set mcp_servers.<name>.<field>` 而非手工编辑
- Cron prompt 用 `cronjob(action='update', ...)` 修改，不要手工改 crontab/JSON
- 修改后立即 `cronjob(action='run')` 验证实际效果
- 再用 `session_search` 查 actual cron session 的 bookend_start，确认 prompt 中搜索工具指令已更新（不要只看 prompt_preview 的截断预览）
- 恢复文件在 `config.yaml.corrupt.*.bak`，可从中提取丢失配置

Cron jobs inherit the global default provider (`config.yaml → model.provider`). If that provider goes down (server-side broken pipe, quota exhausted, rate limit), the job fails with zero fallback — there is no chain.

**Two failure modes seen in production:**

| Failure | Log Pattern | Root Cause | Fix |
|---------|------------|------------|-----|
| **DeepSeek server idle kill** | `Stream stale for 180s — no chunks received` followed by `[Errno 32] Broken pipe` after 3 retries | DeepSeek kills idle streams at 180s on first call; retry on the same provider and endpoint reproduces the same kill | Switch to a different provider for the job, or add a per-job model override pointing to OpenCode Go / Claude. |
| **Local DNS / proxy failure** | `APIConnectionError: Connection error` on ALL provider calls AND `Failed to resolve 'open.feishu.cn'` on delivery | Local network (Clash proxy off, DNS misconfigured) — no outbound connectivity at all | Fix local proxy. Cron jobs are not immune to network outages. |

**Prevention — always pin a per-job model for production cron tasks:**

```python
# Good — pins to a specific provider so it's stable even if the global default changes
cronjob(action='create', ...,
        model={'provider': 'deepseek', 'model': 'deepseek-chat'})
**Better — use a provider with better uptime (OpenCode Go pool, Claude). For low-cost cron tasks (marketing intelligence, trending summaries) use the cheapest stable model:**
```python
cronjob(action='create', ...,
        model={'provider': 'opencode-go', 'model': 'opencode_go_deepseek_flash'})
```

**Do NOT rely on `fallback_providers` in config.yaml** — that is a global setting and modifying it has side effects on non-cron sessions. Use per-job `model` field instead.

**To add a model override to an existing job:**

```python
# Read the full job first (extract prompt), then:
cronjob(action='update',
        job_id='xxx',
        prompt='<original prompt>',
        model={'provider': 'opencode-go', 'model': 'kimi-k2.6'})
```

**Distinguish between "provider is down" and "network is down":**
- Provider down → only the API host fails; delivery (feishu) still works
- Network down → everything fails including delivery; the `delivery_error` field in cron list will show DNS resolution errors for the target platform

### ⚠️ PITFALL #3: `deliver` defaults to `"origin"` on create

When using `cronjob(action='create')`, the `deliver` parameter defaults to `"origin"` — which sends output to the conversation that created the job. If you're creating the job from one chat but want output in a different group, you MUST explicitly set `deliver`.

```python
# WRONG — output goes to current chat, not the target group
cronjob(action='create', name='daily-briefing', schedule='0 9 * * *', prompt='...')

# CORRECT — output goes to specific Feishu group
cronjob(action='create', name='daily-briefing', schedule='0 9 * * *',
         prompt='...', deliver='feishu:oc_xxxxxxxxxxxxx')
```

**Fix after creation:**
```python
cronjob(action='update', job_id='xxx', deliver='feishu:oc_xxxxxxxxxxxxx')
```

### ⚠️ PITFALL #4: `repeat` Parameter Type Sensitivity

When using `cronjob(action='create')` with `schedule` in standard cron format (e.g., `"30 8 * * *"`), the `repeat` parameter may cause `'<=' not supported between instances of 'str' and 'int'` errors depending on the backend version. If this occurs:

```python
# May fail with comparison error
cronjob(action='create', name='daily-report', schedule='30 8 * * *', repeat='forever', ...)

# WORKAROUND: Omit repeat entirely — default is 'forever' for recurring schedules
cronjob(action='create', name='daily-report', schedule='30 8 * * *', ...)
```

### Multi-Cron Merge Pattern

When replacing N old cron jobs with M new ones (e.g., merging two separate reports into one):

1. **Remove old jobs first** to avoid duplicate delivery
2. **Create new jobs with explicit `deliver`** set to target group
3. **Verify with `cronjob(action='list')`** that old jobs are gone and new jobs show correct schedule + deliver target

## Marketing Intelligence Cron Pattern

For competitive/marketing intelligence reports that need global timezone coverage, use the **dual-run pattern** with a structured three-tier output format.

### Dual-Run Scheduling

| Run | Time | Coverage |
|-----|------|----------|
| Morning | 08:30 | Overnight European/US market activity |
| Evening | 18:00 | Asian/EU daytime activity |

Both jobs share the same prompt template — only the report label (早报/晚报) differs.

### Three-Tier Output Structure

```
# 🏆 {Report Title} | {Date} 早报/晚报

## 📌 今日三信号
> ① {top signal}
> ② {second}
> ③ {third}

## 📰 品牌动态
### 1. {Brand} {Action}
**时间**：{time}
**动作**：{2-3 sentence description}
**为什么重要**：{1 line}
**对我们意味着**：{1 actionable line}
**来源**：{source}
(2-5 items, P0 brands first)

## 🧠 启示与行动
- {Specific actionable advice}
```

### P0/P1/P2 Priority System

Embed a priority filter in the prompt so the cron agent knows which brands to prioritize:

- **P0 — Focus Brands**: The user's clients + key sponsors. Keep this list explicit and updatable.
- **P1 — Competitors**: Rival platforms' moves.
- **P2 — Industry Trends**: Broader marketing innovation.

### [SILENT] Pattern

When there's genuinely no new information in the search window, the agent should output exactly `[SILENT]` to suppress empty delivery. The cron system recognizes this and won't push a blank message.

### Prompt Design Rules

1. **Actionable, not encyclopedic** — every item must answer "so what for us?"
2. **Fixed signal count** — top-level signals always exactly 3, forcing prioritization
3. **No vague verbs** — ban "值得关注", "建议跟踪" in the 启示 section. Every suggestion must be executable.
4. **Updatable brand list** — keep P0 brands in the prompt itself (the user corrects it directly), not in external files that go stale.

Full prompt template: `references/marketing-intelligence-prompt-template.md`

## One-Shot Job Design Pattern (e.g., Time-Sensitive Purchases)

For time-sensitive cron tasks (flash sales, limited-stock purchases):

1. Schedule the cron job **2 minutes before** the target time (e.g., 09:58 for a 10:00 sale)
2. The script should include a **wait loop** to the exact second
3. Use **dual strategy**: API first (fast), browser CDP second (reliable)
4. Always include a **fallback notification** so the user can manually act
4. The standalone script path can be referenced in the cron prompt: `python3 ~/grab_script.py`

### Polling Frequency for Sub-Second Timing

For flash sales where stock sells out in <500ms:

```python
# 100ms polling loop — NOT 500ms
import time
while time.time() < target_timestamp:
    time.sleep(0.001)  # busy-wait until exact second

# 100ms polling for button state
while True:
    btn = find_purchase_button()
    if btn and not btn.disabled:
        btn.click()
        break
    time.sleep(0.1)  # 100ms — fast enough to catch a 500ms window
```

**Why 500ms fails:** A stock that sells out in 300ms with a random 0-500ms offset between polls means you can miss it entirely.

### Non-Headless Chrome for Cron Browser Tasks

When headless Chrome gets rate-limited by the target site, start non-headless Chrome from the cron prompt:

```bash
terminal(background=true): /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
  --remote-debugging-port=9222 \\
  --remote-allow-origins=* \\
  --no-first-run --no-default-browser-check \\
  --user-data-dir="$HOME/.hermes/chrome-profile" \\
  "https://target-site.com/buy"
```

Then use `browser_navigate`/`browser_click` Hermes tools for interaction. The non-headless window appears on the user's screen — they may need to log in manually before automation can proceed.

**Key CDP flag that must be included:**
```bash
--remote-allow-origins=*
# Without this, WebSocket connections fail with HTTP 403:
# "Rejected an incoming WebSocket connection from the http://localhost:9222 origin."
```
