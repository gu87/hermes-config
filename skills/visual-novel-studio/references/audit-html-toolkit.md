# VNS Audit HTML Toolkit

适用于 VNS 图片审计阶段的交互式 HTML 审核工具。用户可在本地浏览器打开，逐张对比 AI 图 vs 真实照片，勾选保留/修改意见，导出决策 JSON。

## 核心功能

| 功能 | 说明 |
|------|------|
| Tab 切换 | 按剧本章节分 7 个 Tab（6 章 + 背景合集） |
| 卡片视图 | 每张卡：左 AI 图 + 右参考图（如有），底部控制面板 |
| 评级徽章 | 🟢准确 / 🟡轻微 / 🔴失实（pre-set 在 DATA 中） |
| Keep/Redo 勾选 | 每张卡「✅ 保留」默认勾选，需要修改的勾「🔄 需要修改」 |
| 修改意见框 | 文本区填写具体修改要求（发型、球衣、颜色等） |
| 📤 上传自定参考图 | 用户上传本地图片替换参考图区域（FileReader data URL） |
| ✕ 移除 | 恢复原始参考图或"暂无参考照片"占位符 |
| 📥 导出意见 | 导出 JSON 含所有卡片的 keep/redo/comment/hasCustomRef 字段 |
| ↺ 重置 | 恢复所有选项到初始状态 |

## 实现结构

### DATA 数据结构

```javascript
[{
  chapter: "ch1",          // 章节ID，对应Tab切换
  chapterTitle: "闪耀新星", // 章节标题
  bgIntro: "...",           // 章节背景介绍
  items: [{
    id: "hero_1",          // 唯一ID，关联所有DOM操作
    type: "hero",          // hero/panel/bg
    name: "hero_1·xxx",    // 显示名
    rating: "yellow",       // green/yellow/red
    desc: "描述文本",
    issue: "问题说明",
    current: "../raw/xxx.png",  // AI生成图路径
    ref: "photos/xxx.jpg"       // 真实照片路径(null=暂无)
  }]
}]
```

### 上传参考图机制

- **变量**：`const uploadedRefs = {}`（key=id, value={dataUrl, name, size}）
- **文件选择**：`<input type="file" accept="image/*">` 隐藏，通过 `<label for="upload-xxx">` 触发
- **读取**：`FileReader.readAsDataURL(file)` → data URL 内联显示
- **替换**：找到 `.img-box-ref[data-id="xxx"]` → 设置 innerHTML 为 `<img src="dataUrl">`
- **恢复**：从 DATA 中重新读取 item.ref，还原原始内容
- **导出**：exportDecisions() 中读取 `uploadedRefs[item.id]`，写入 `hasCustomRef` 和 `customRefFilename`
- **移除**：`delete uploadedRefs[id]` + 恢复 DOM + 恢复按钮状态 + 清空 file input

### CSS 关键类

```css
.upload-btn           /* 虚线边框上传按钮 */
.upload-btn.uploaded  /* 已上传状态（绿色实线边框） */
.img-box-ref          /* 参考图容器，最大高度200px */
.remove-upload        /* 移除按钮，默认隐藏 */
```

### 章节归属修复（叙事流重构）

当审计发现素材的章节归属不符合叙事流时（如正面事件在负面章节），直接编辑 DATA 数组实现结构重组：

1. **移动 items** — 将 items 对象从一个章节的 `items: [...]` 数组剪贴到目标章节
2. **更新 rating/desc/issue** — 移动后评估该素材在新章节中的合理 rating（如果只是位置不对、事实没问题，可从 🔴 降为 🟡）
3. **更新 bgIntro** — 源章节和目标章节的背景介绍需重写以匹配新内容
4. **更新 bg 卡片章节号** — 背景图描述中的章节编号（"第一章"→"第二章"等）同步更新
5. **重算统计数字** — header 中的 🟢🟡🔴 计数重新计算
6. **验证叙事流** — 按新章节顺序读一遍确认顺畅

**典型重构案例（Beckham 篇）：** 哥伦比亚首球（正面事件）原在 ch2「坠入深渊」→ 移到 ch1「闪耀新星」。红牌事件碎片（散在 ch3+ch4+ch5）→ 合并到 ch2（冲突现场）+ ch3（媒体后果）。

### 导出 JSON 格式

```json
{
  "exportedAt": "2026-05-17T...",
  "decisions": [{
    "id": "hero_1",
    "name": "hero_1·首秀肖像",
    "keep": true,
    "redo": false,
    "comment": "发型改为金色寸头",
    "hasCustomRef": false,
    "customRefFilename": null
  }]
}
```
