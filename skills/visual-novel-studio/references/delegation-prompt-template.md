# 皮尔洛派单模板 — VisualNovelStudio 剧本

向皮尔洛派单时，必须附带以下格式约束。**不遵守会导致剧本不兼容引擎，需要额外修复步骤。**

## 强制约束（**必须**写在 goal 或 context 中）

```
输出要求（严格遵守）：
1. 使用5章结构，每章包含 nodes 数组
2. 节点支持的类型仅限：scene / narrate / dialog / panel / choice / card / hero / ending
3. 不要使用 illustration 类型
4. panel 节点格式必须为 { type:'panel', src:'KEY', pos:'br' }，不要嵌套 left/right/layout/illustration 字段
5. hero 节点用 title 字段（放角色台词），不要用 dialog 字段
6. scene 节点必须包含 chapter 字段，格式如 "第一章：标题"
7. 图片 key 不要用 "?"。scene 用 bg01-bg05，panel 用 overlay_01-overlay_N，hero 用 hero_01-hero_N，card 用 card_01-card_N
8. 不要包含 id / character / expression / pose / duration_seconds 等元数据字段
9. choice 节点必须含 options 数组，每项有 text 和 score
10. 每章至少1个 scene + 1个 narrate + 1个 choice + 1个 card
11. 全部输出为 JSON 格式
```

## 额外建议（根据故事类型可选）

- 救赎/传记类：固定主角视角（第一人称），增加内心独白节点
- 争议/对抗类：双视角交错，加抽卡节点
- 群像类：多 POV，每章切换视角
