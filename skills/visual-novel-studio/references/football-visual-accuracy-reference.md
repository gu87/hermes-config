# Football Visual Accuracy Reference

> 足球题材 H5 游戏图片 prompt 的真实性参考数据。
> 踩坑来源：Beckham 1998-2002 篇全量图片审计（2026-05-17）

## England National Team Kit Reference

### 1998 World Cup

| 对手 | 英格兰球衣 | 备注 |
|------|-----------|------|
| Tunisia (Group G) | White home (#7) | 小组赛第一场 |
| Romania (Group G) | Red away (#7) | — |
| Colombia (Group G) | **Red away (#7)** | 自由球进球的比赛 |
| Argentina (R16) | **Red away (#7)** | 红牌比赛 |

**关键教训：** 英格兰 1998 世界杯客场红色球衣带灰色斜条纹。不要凭「主队=主场球衣」推断——英格兰对阿根廷穿的是红色客场。

### 2002 World Cup

| 对手 | 英格兰球衣 | 备注 |
|------|-----------|------|
| Sweden (Group F) | White home (#7) | — |
| Argentina (Group F) | **White home (#7)** | 点球绝杀比赛 |
| Nigeria (Group F) | White home (#7) | — |
| Denmark (R16) | White home (#7) | — |
| Brazil (QF) | White home (#7) | 1-2 失利 |

### 1999-2001 预选赛/友谊赛

| 比赛 | 球衣 | 备注 |
|------|------|------|
| 2001 Oct vs Greece (WCQ) | **White home (#7)** | 老特拉福德，93分钟任意球绝平 |
| Euro 2000 group stage | White home / Red away | 视对手而定 |

## Beckham Hairstyle Timeline (Critical — Don't Guess)

This changes EVERY season. Do NOT use the most famous hairstyle for all years.

| 年份 | 发型英文描述 | 年份 |
|------|------------|------|
| 1998 (WC) | short bleached buzz cut, ~1cm length | ✅ Correct in hero_1-5, panel_1-3 |
| Late 1998 | slightly longer unkempt blonde, growing out | ✅ Correct in hero_6 |
| 1999 | longer golden blonde, side-parted, highlighting, ~shoulder length | ✅ Correct in hero_7, hero_14 |
| 2000 | longer blonde with slight waves, side-parting | — |
| 2001 | medium-length blonde with textured top, side-parting, NOT spiky | ⚠️ hero_8 wrongly said "short spiky" |
| 2002 (WC) | **very short bleached buzz cut, NOT mohawk** | ⚠️ hero_9/hero_10/panel_8/panel_9 wrongly said "mohawk" |
| 2003 | longer darker blonde with roots showing | — |
| 2004 (Euro) | short blonde with shaved sides | — |

**Common misconception:** Beckham's mohawk era was **2000-2001** (Euro 2000 and early WC qualifiers). By the 2002 World Cup he had cut it very short. Many references online say "iconic mohawk" for 2002 but this is incorrect — check actual match photos.

## Verification Protocol for New Football Projects

When generating images for a football-themed VNS game about real players:

### Step 1: Assign OpenClaw

For each key visual moment, dispatch OpenClaw with the exact query format:

```
Search: <player_name> <year> <match/event> photo kit hairstyle
Verify: match date, venue, home/away kit color, hairstyle in photos
```

### Step 2: Cross-reference dimensions

| Dimension | What to check | Source |
|-----------|--------------|--------|
| Kit color | Check match report photos, not Wikipedia text | Getty Images match photos |
| Hairstyle | Check close-up match photos from that specific year | Match photo gallery |
| Venue | Wikipedia match page "Venue" field | Wikipedia |
| Age | Player's birth year + match year | Wikipedia player page |
| Teammates | Match starting XI for that specific game | Match report |

### Step 3: Prompt verification checklist

Before generating:
- [ ] Kit color matches match report photos (NOT assumed from "home team")
- [ ] Hairstyle matches photos from that exact year (NOT the player's most famous look)
- [ ] Venue name is spelled correctly
- [ ] Age is correct for that year
- [ ] "NO Japanese text" guardrail is in prompt
- [ ] Face recognition constraint is in prompt (for semi-realistic manga)
