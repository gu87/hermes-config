---
name: competitive-intelligence
description: Gather recent marketing/competitive intelligence (24h-7d window). Monitor brand sponsorships, campaign launches, social media trends. Produce structured briefings with source tables.
agents:
  - openclaw
  - hermes-internal
related_skills:
  - last30days
  - hermes-cron-management
---

# Competitive Intelligence Research

## When to Use This Skill

Use this when the task is:
- Gathering recent marketing/competitive intelligence (past 24h to 7d window)
- Monitoring brand sponsorship moves, campaign launches, social media trends
- Producing a structured briefing with source tables and judgment calls
- Running as a cron-delivered intelligence job
- Chinese-market sports/football marketing intelligence (懂球帝 context)

Do NOT use this for 30-day trend research — that is the `last30days` skill (uses a bundled Python engine with Reddit/X/Twitter sources).

## Source-Gathering Approach

### Primary Tool: Playwright Browser MCP + Google / Google News

**Why:** Google blocks curl/scrapling_fetch. Playwright browser MCP works reliably with JavaScript-rendered pages.

**24-hour filter URL:**

```
https://news.google.com/search?q=<encoded-query>&hl=en-US&gl=US&ceid=US:en&when=1d
```

For shorter windows, use `tbs=qdr:d` (past 24h) or `tbs=qdr:w` (past week) on the standard Google Search URL:

```
https://www.google.com/search?q=<query>&tbm=nws&tbs=qdr:d&hl=en-US
```

### Chinese-Language Research — Google News as Primary Entry Point

For Chinese marketing intelligence (懂球帝 / sports marketing context), bypass standard Google Search and go directly to Google News:

```
https://news.google.com/search?q=<encoded-Chinese-query>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans
```

**Why:** Google News consistently returns Chinese-language results with readable snippet summaries even when the actual article pages are inaccessible (常见 404/付费墙/页面不存在). The snippet text alone often contains enough info for a daily briefing.

**When direct URL navigation fails (common pattern):**
- `sina.com.cn` links return "页面没有找到" (page not found). Google search result URLs are frequently truncated or use redirect wrappers that break.
- `163.com` links redirect to homepage instead of target article.
- `adage.com` articles return 404 — the URL from search results frequently leads to "Page not found".
- `designrush.com` links frequently redirect to 404 as articles get moved or deleted.
- `campaignasia.com`, `yicaiglobal.com` have paywalls.
- **What works**: Navigate to `thepaper.cn` articles directly — they are consistently readable without paywall.

**24-hour filter for Chinese queries:**

```
https://news.google.com/search?q=<query>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans&when=1d
```

**Fallback:** If Google News returns few results for Chinese queries with `when=1d`, use standard Google search with `tbs=qdr:d` and `tbm=nws`:

```
https://www.google.com/search?q=<query>&tbm=nws&tbs=qdr:d&hl=zh-CN&gl=CN
```

### Query Strategy — Run Multiple Angles

Run 3-5 parallel queries covering different angles:

| Angle | Example Query |
|-------|------|
| Broad catch-all | `"World Cup" "2026" sponsor OR marketing OR campaign` |
| Brand/sponsor track | `World Cup 2026 sponsor official brand` |
| Campaign track | `FIFA World Cup 2026 campaign ad creative` |
| Social trend track | `World Cup 2026 social media marketing viral` |
| Chinese market | `世界杯 2026 营销 品牌 赞助` |
| Chinese brand-specific | `海信 世界杯 2026 营销` or `蒙牛 世界杯 2026` |
| Competitor track | `<competitor name> World Cup 2026 marketing` |

The broad `OR`-based catch-all query consistently returns the most results.

### Deep-Dive Workflow

For each promising article found:

1. Check source reliability: if it's a known-fragile source (sina, 163, adage, designrush, campaignasia, yicaiglobal), skip browser_navigate — the snippet is your best data.
2. For reliable sources (thepaper.cn, reuters, bloomberg): `browser_navigate(url)` to the article
3. `browser_snapshot()` to extract content
4. Look for: brand names, campaign names, agency partners, financial terms, key executive quotes, social media strategy components (UGC, influencer, viral mechanics)
5. Note the source's reliability
6. If browser_navigate returns 404 or paywall: return to search results and use snippet data. Do not retry or seek alternative URLs.

### Fallback: When Google News Fails

- **Chinese searches from China IP may return zero results** with `tbs=qdr:d` + Chinese keywords. Fall back to English queries or remove the time filter.
- **Google redirects to `google.com.hk`** from China IPs — cached `.hk` results may differ from `.com` results. This is usually fine but note the variance.
- **Rate limiting**: keep to 5-8 page loads per session; no rapid-fire navigation.
- **Sina finance URLs break frequently**: The redirect URL from search results often leads to "页面没有找到". If the first URL fails, move to the next source rather than retrying.

## Source Reliability Scale

| Level | Description | Examples |
|-------|-------------|---------|
| High | Breaking news, exclusive access, primary source interviews | WWD, ADWEEK, Bloomberg, Reuters, thepaper.cn (澎湃新闻) |
| Medium | Official announcements, press release republication, industry trade | FOX Sports, LBBOnline, SportsPro, Forbes, jiemian.com (界面新闻), dongqiudi.com (懂球帝), finance.sina.com.cn (新浪财经), tmtpost.com (钛媒体) |
| Low | Opinion/analysis pieces, aggregators, republished press releases | Drug Store News, RetailWire, Brand Innovators, eastmoney.com (东方财富) |
| Unlabeled | Source not checked in this run — label explicitly | — |

Label unavailable sources in the source table (e.g., "X/Twitter: unavailable without credentials").

## Report Format

Use this structured Asian-format briefing for cron-delivered or on-demand reports:

```markdown
# 【标题】<Topic> - YYYY.MM.DD

## 【摘要】
- 动态1: ...
- 动态2: ...
- 动态3: ...
(3-5 key findings)

## 【关键变化】
- **变化1**：<What changed + implication for strategy>
- **变化2**：<What changed + implication>

## 【来源】
| 来源 | 时间 | 链接 | 备注 |

## 【判断】
- **是否需要关注**：是 / 否
- **建议后续动作**：
  1. ...
  2. ...
  3. ...
```

## Steps

1. **Understand scope** — time window (24h/7d/30d), topic (World Cup / industry / competitor), delivery method (cron vs on-demand)
2. **Run 3-5 parallel queries** covering different angles using browser_navigate
3. **Snapshot each result page** and extract headlines
4. **Deep-dive into 3-5 most relevant articles** using browser_navigate
5. **Compile findings** organized by theme/change, not by source
6. **Assess source reliability** — distinguish sourced findings from interpretation
7. **Format output** as structured briefing with source table and judgment section
8. **If cron-delivered**: output the briefing directly (no file save needed — the cron system delivers the response text)

## Common Pitfalls

- scrapling_fetch does NOT work for news gathering — consistently times out on Google (curl error 28), then marks the MCP server as "unreachable" after 3 consecutive failures, blocking further use for the entire session. Always use Playwright browser MCP from the start. After the first timeout, switch immediately — do not retry.
- Google News snapshots are text-only — images and video embeds cannot be extracted from snapshots
- Timestamps are relative — "3 days ago" means relative to crawl time, not absolute. Multiple relative timestamps in one report may confuse if cross-referenced later
- Chinese language searches from China IP may have lower recall — Google News' Chinese index is thinner; supplement with English queries
- Don't over-query — 5-8 page loads max per session to avoid rate limiting
- Don't re-ask the user — cron jobs have no user present; make reasonable decisions on scope and depth
- **"Stay on search results" technique**: After browser_navigate to Google search results, read article summaries from the browser_snapshot directly. Individual article links (sina.com.cn, 163.com, adage.com, campaignasia.com, designrush.com) frequently return 404, redirect to homepage, or hit paywalls. The search result snippets alone contain 70-80% of actionable intelligence for a daily briefing. Only deep-dive articles from reliably accessible sources (thepaper.cn, reuters.com, bloomberg.com).
- When a browser_navigate to an external article returns 404 or paywall, do NOT waste turns trying alternative routes. Return to the search results page and use snippet data.
- Chinese news site URL fragility: sina.com.cn, 163.com URLs from Google search results frequently return "页面没有找到" or redirect to homepage. Prefer thepaper.cn articles which are reliably readable. For paywalled sources (campaignasia.com, yicaiglobal.com, adage.com), the Google News snippet may be your best data source.
- Google News "展开" button: Clicking the expand button on a Google News article card reveals more snippet text but may not navigate to the article. Use browser_navigate for the article link directly.
- same_tool_failure_warning (3+ consecutive failures of the same tool) is a signal to change approach immediately, not retry.

## Related Skills

- `last30days` — 30-day community/social trend research (uses bundled Python engine, different source coverage)
- `hermes-cron-management` — cron job lifecycle and troubleshooting
