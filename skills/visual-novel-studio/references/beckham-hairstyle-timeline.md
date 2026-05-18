# 贝克汉姆发型时间线速查表

## 作用

快速核验涉及贝克汉姆的图片 prompt 中发型描述是否准确。**不要凭印象写发型**——他的发型几乎每年都在变，且不同赛季之间可能判若两人。

## 完整发型对照表

| 年份 | 年龄 | 发型 | 英文描述（用于prompt） | 关键赛事/事件 | 曾犯错误 |
|------|------|------|----------------------|-------------|---------|
| **1998** | 23 | **金色中长发，侧分**（耳下长度，不是板寸） | `medium-length side-parted blonde hair, falling to ear level` | 法国世界杯首秀（vs罗马尼亚替补登场）、世界杯首球（vs哥伦比亚任意球） | ❌ 曾误写为"short bleached buzz cut" |
| 1999 | 24 | 稍长金发偏分 | `longer blonde hair, side-parted` | 曼联三冠王赛季、诺坎普欧冠决赛 | |
| 2000 | 25 | 中长金发，偏分，发色偏自然 | `medium-length natural blonde, side-parted` | 欧洲杯、赛季 | |
| 2001 | 26 | **侧分中长金发**（耳下，非短刺） | `side-parted medium-length blonde hair` | 对希腊预选赛93分钟任意球绝平 | ❌ 曾误写为"short spiky bleached" |
| 2002 | 27 | **极短漂白板寸**（#1-2长度，非莫西干） | `very short bleached buzz cut, close to scalp #1-2 length` | 韩日世界杯、对阿根廷罚入点球 | ❌ 曾误写为"iconic bleached mohawk" |
| 2003 | 28 | 偏分深金发，发根可见黑色 | `longer darker blonde hair with roots showing, side-parted` | 转会皇马首个赛季 | |
| 2004 | 29 | 短发两侧剃光 | `short blonde hair with shaved sides` | 欧洲杯葡萄牙 | |

## 典型错误模式

### 错误1：把1998写成板寸
**表现**：1998年世界杯所有图片的prompt都写"short bleached buzz cut"
**真实**：1998年是金色中长发，侧分（耳下长度，有明显分界）
**影响范围**：hero_1~hero_5, panel_1/2/3/p7204（共9张）
**根因**：审计时只看了金发颜色，没查具体长短

### 错误2：把2001写成短刺
**表现**：hero_8 prompt写"short spiky bleached"
**真实**：2001年希腊预选赛是侧分中长金发（耳下，非竖立刺头）
**根因**：把2001和2002的发型记反了

### 错误3：把2002写成莫西干
**表现**：hero_9/10, panel_8/9 prompt写"iconic bleached mohawk"
**真实**：2002年世界杯是极短漂白板寸（#1-2长度，最"光头"时期）
**根因**：莫西干是贝克汉姆最具标志性的造型，容易默认覆盖所有年代

## 核查清单

写prompt之前逐一确认：

- [ ] 该年份 Beckham 发型是长发/中发/短发？
- [ ] 发色是漂白金/自然金/深金？
- [ ] 是否偏分/中分/无分界？
- [ ] 两侧是剃光还是保留长度？
- [ ] 有无当场比赛照片对照确认？

## 参考照片来源

- Getty Images editorial: 搜索 `"David Beckham" [year] [event]` → browser模式访问
- Wikipedia: 该年世界杯/欧洲杯/赛季页面中常见比赛照片
- 新旧搜索前先检查 `audit/photos/` 目录是否有此前下载但未引用的照片
