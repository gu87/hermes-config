---
# Competitive Intelligence Research

## When to Use This Skill

Use this when the task is:
- Gathering recent marketing/competitive intelligence (past 24h to 7d window)
- Monitoring brand sponsorship moves, campaign launches, social media trends
- Producing a structured briefing with source tables and judgment calls
- Running as a cron-delivered intelligence job

**Do NOT use this for 30-day trend research** — that's the `last30days` skill (uses a bundled Python engine with Reddit/X/Twitter sources).

## Source-Gathering Approach

### Primary Tool: Playwright Browser MCP + Google News

**Why:** Google blocks curl/scrapling_fetch. Playwright browser MCP works reliably with JavaScript-rendered Google News pages.

**24-hour filter URL:**

```
https://news.google.com/search?q=<encoded-query>&hl=en-US&gl=US&ceid=US:en&when=1d
```

For shorter windows, use `tbs=qdr:d` (past 24h) or `tbs=qdr:w` (past week) on the standard Google Search URL:

```
https://www.google.com/search?q=<query>&tbm=nws&tbs=qdr:d&hl=en-US
```

### Query Strategy — Run Multiple Angles

Run 3-5 parallel queries covering different angles:

| Angle | Example Query |
|-------|------|
| Broad catch-all | `"World Cup" "2026" sponsor OR marketing OR campaign` |
| Brand/sponsor track | `World Cup 2026 sponsor official brand` |
| Campaign track | `FIFA World Cup 2026 campaign ad creative` |
| Social trend track | `World Cup 2026 social media marketing viral` |
| Chinese market (used with `google.com.hk`) | `世界杯 2026 营销 品牌 赞助` |
| Competitor track | `<competitor name> World Cup 2026 marketing` |

**The broad `OR`-based catch-all query consistently returns the most results.**

### Deep-Dive Workflow

For each promising article found:

1. `browser_navigate(url)` to the article
2. `browser_snapshot()` to extract content
3. Look for: brand names, campaign names, agency partners, financial terms, key executive quotes, social media strategy components (UGC, influencer, viral mechanics)
4. Note the source's reliability (see below)

### Fallback: When Google News Fails

- **Chinese searches from China IP may return zero results** with `tbs=qdr:d` + Chinese keywords. Fall back to English queries or remove the time filter.
- **Google redirects to `google.com.hk`** from China IPs — cached `.hk` results may differ from `.com` results. This is usually fine but note the variance.
- **Rate limiting**: keep to 5-8 page loads per session; no rapid-fire navigation.

## Source Reliability Scale

| Level | Description | Examples |
|-------|-------------|---------|
| **High** | Breaking news, exclusive access, primary source interviews | WWD, ADWEEK, Bloomberg, Reuters |
| **Medium** | Official announcements, press release republication, industry trade | FOX Sports, LBBOnline, SportsPro, Forbes |
| **Low** | Opinion/analysis pieces, aggregators, republished press releases | Drug Store News, RetailWire, Brand Innovators |
| **Unlabeled** | Source not checked in this run — label explicitly | — |

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

- **scrapling_fetch does NOT work on Google** — always use Playwright browser MCP
- **Google News snapshots are text-only** — images and video embeds cannot be extracted from snapshots
- **Timestamps are relative** — "3 days ago" means relative to crawl time, not absolute. Multiple relative timestamps in one report may confuse if cross-referenced later
- **Chinese language searches from China IP may have lower recall** — Google News' Chinese index is thinner; supplement with English queries
- **Don't over-query** — 5-8 page loads max per session to avoid rate limiting
- **Don't re-ask the user** — cron jobs have no user present; make reasonable decisions on scope and depth

## Related Skills

- `last30days` — 30-day community/social trend research (uses bundled Python engine, different source coverage)
- `hermes-cron-management` — cron job lifecycle and troubleshooting

agents: [openclaw, hermes-internal]
---
