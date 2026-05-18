# 引擎模板结构说明

引擎模板内嵌在 `~/.hermes/scripts/vns/assemble.py` 的 `ENGINE_TEMPLATE` 常量中。

## 替换占位符

| 占位符 | 替换内容 | 来源 |
|--------|---------|------|
| `{{TITLE}}` | 游戏标题 | 用户输入 |
| `{{SUBTITLE}}` | 副标题 | 用户输入 |
| `{{TEASER}}` | 引子文案（3-4行） | 用户输入 |
| `{{IMG_DICT}}` | 图片 base64 字典 JSON | compress.py / assemble.py 自动生成 |
| `{{SCRIPT}}` | 剧本 DSL 数组 JSON | flatten.py 转换后 |
| `{{SFX_LIST}}` | 音效文件名列表 JSON | assemble.py 自动扫描 |
| `{{SDK_PLACEHOLDER}}` | 广告 SDK 代码 | 待接入（`unified-reward-bridge.js`） |

## 引擎核心函数

| 函数 | 用途 |
|------|------|
| `advance()` | 推进到下一节点 |
| `renderNode(node)` | 根据类型分发渲染 |
| `showDialog(speaker, text)` | 打字机效果对话 |
| `showPanel(node)` | 浮层插图（自动淡出4s） |
| `showChoice(node)` | 选择题面板（选中高亮0.4s） |
| `showCard(node)` | 历史档案卡 |
| `showHero(node)` | 英雄时刻定格（3秒自动关闭） |
| `showGacha(node)` | 抽卡（翻牌动画+重抽） |
| `showEnding()` | 结局页（理解度分档） |
| `playSfx(file)` | 单次音效 |
| `playBgm(file)` | 循环BGM（自动淡出/淡入切换） |
| `startAmb(file)` | 环境音（可淡出） |
| `toggleMute()` | 全局静音开关（localStorage持久化） |

## 体验优化（已内置）

- 浮层自动淡出 4s
- 场景切换锁定 1.5s
- 选择题选中动画 0.4s
- 打字机加粗抖动特效
- BGM淡入淡出切换
- 环境音独立淡出控制
- 页面可见性监听（切后台暂停音效）
- iOS 自动播放限制（启动页按钮触发）
