# VNS 引擎调试清单

当用户反馈 game `dist/index.html` "不行" "不工作" "黑屏" 时，按此清单逐项排查。

---

## 第一层：确定游戏是否在跑

打开浏览器 file://path/to/dist/index.html，在 console 执行：

```javascript
cursor          // 当前推进到哪个节点
locked          // 是否被锁阻塞
advancing       // 是否正在推进中（True 表示有未完成的 advance 调用）
SCRIPT.length   // 总节点数
```

**正常状态**：点击"进入故事"后 cursor 应逐渐递增（0→1→2→...），locked 大部分时间为 false。

**异常判断：**
- cursor=0 且 locked=false：没走到 advance——检查 onLaunch/launch-btn
- cursor=1 且 locked=false：只走了 scene 节点——**锁冲突 bug**（参见 pitfalls.md #6）
- cursor 跳过 narrate/dialog 节点（如 2→4 而非 2→3→4）：**race condition bug**——advance() 被双重调用（参见 pitfalls.md #11）
- cursor>1 但画面无变化：检查 renderNode 中各 handler 是否正常执行

---

## 第二层：检查 scene 渲染

如果 cursor 过了 scene 节点但背景、HUD 无变化：

```javascript
document.getElementById('scene').style.backgroundImage  // 为空→setBg 未生效
document.getElementById('hud').className                 // 为空→show 类未加上
document.getElementById('hud-chapter').textContent       // 为空→chapter 未写入
IMG_DICT['bg01']                                        // 检查图片 key 是否存在
```

**常见原因：**
- IMG_DICT 缺少 bg key（图片未生成）
- 锁冲突导致 auto-advance 跳过 scene 还没来得及渲染（cursor 情况见上）
- 空 JS 错误吞掉了 DOM 操作（见 pitfalls.md #10）

---

## 第三层：检查 dialog 渲染

如果 cursor 过了 narrate/dialog 节点但对话框无内容：

```javascript
SCRIPT[cursor - 1]               // 检查上一个节点的完整数据
JSON.stringify(SCRIPT[n])        // 具体检查某个节点
document.getElementById('dialog-box').className     // 应为 "show"
document.getElementById('dialog-text').textContent  // 应为对话文本
```

**常见原因：**
- dialog 节点用 `"dialog":"xxx"` 但引擎读 `node.text` → 文本为空（pitfalls.md #7）
- narrate 节点的 `text` 字段拼写错误（如 `"content"` 而非 `"text"`）

---

## 第四层：检查 Choice 选择分支

如果选择后两个选项的结果都出现（或选项 A 的结果不出现）：

```javascript
// 确认 skipCount 全局变量存在
typeof skipCount  // → 'number'

// 确认 cursor 和 skipCount 在选项点击后的值
// 在 showChoice 的 btn.onclick 中：
//   cursor = choiceIdx + 1 + i  (正确)
//   skipCount = (i===0) ? 1 : 0 (正确)
```

**常见原因：**
- `showChoice()` 中直接调 `advance()` 而未设置 cursor 和 skipCount → 线性推进显示两个结果
- 旧版引擎（未修此 bug）表现：选择一个选项，两个后果文本依次出现（pitfalls.md #20）

## 第五层：检查其他节点类型

```javascript
document.getElementById('choice-box').className  // choice
document.getElementById('card-box').className     // card
document.getElementById('hero-box').className     // hero
```

对每种节点，提取数据检查字段名与引擎 handler 是否匹配：

| 引擎 Handler | 读什么字段 | 皮尔洛数据实际用什么 |
|-------------|-----------|-------------------|
| `renderNode` → scene | `node.bg`, `node.chapter` | ✅ `bg`, `chapter` |
| `renderNode` → narrate | `node.text` | ✅ `text` |
| `renderNode` → dialog | `node.dialog` (修复后) / `node.text`(BUG) | `dialog` |
| `renderNode` → panel | `node.src`, `node.pos` | ✅ `src`, `pos` |
| `renderNode` → choice | `node.question`, `node.options[].text` | ✅ 但参数可能用 `next_node`, `affinity_effect` |
| `renderNode` → card | `node.title`, `node.text`(BUG→description) | `title`, `description` |
| `renderNode` → hero | `node.image`, `node.title` | ✅ `image`, `title` |
| `renderNode` → ending | 无参数 | ✅ |

---

## 第五层：检查图片资产

获取所有图片引用 vs 实际存在的图片：

```javascript
// 脚本中所有图片引用
const refs = new Set();
SCRIPT.forEach(n => {
  if (n.bg) refs.add(n.bg);
  if (n.image) refs.add(n.image);
  if (n.src) refs.add(n.src);
  if (n.photo) refs.add(n.photo);
});
console.log('引用图片:', [...refs].sort());
console.log('已有图片:', Object.keys(IMG_DICT).sort());
console.log('缺失图片:', [...refs].filter(k => !IMG_DICT[k]));
```

如果缺失图片 > 0：
1. 去 `gen.py` 的 batch 来源（script_flat.json 或皮尔洛原始输出）检查图片 key 分配
2. 确保 `fix_script.py` 在 flatten 后运行了
3. 用 gen.py `--batch` 模式补集中生成缺失图
4. 生成完成后运行 `post_gen.py`（压缩 + 重建一步搞定）

---

## 第六层：JS 异常捕获

Playwright console 可能显示空 error message（pitfalls.md #10）：

```javascript
// 在浏览器中设置全局错误捕获
window.__errors = [];
window.onerror = function(msg, url, line, col, err) {
  window.__errors.push({msg, url, line, col, stack: err && err.stack});
  return true;
};
// 然后重现操作，再查看：
console.table(window.__errors);
```

**常见空错误来源：**
- 极大 base64 data URI 赋值给 `backgroundImage` 或 `img.src` 被浏览器拒绝
- Audio 文件 404（`new Audio('assets/typing.mp3')` 路径不对）
- CSS `url()` 中 base64 长度超过浏览器限制

---

## 第七层：静默脚本终止（TDZ / const 重复声明）

**症状**：页面加载正常，启动页可见，点击"进入故事"后 scene 渲染，但 cursor 停在 1 不再推进。没有任何 JS 错误信息。**这是最难排查的一类 bug。**

```javascript
// 1. 检查关键函数是否存在——如果 undefined 说明脚本执行未到达该处
typeof showHero       // → "undefined" = 脚本在 showHero 之前就终止了
typeof showDialog     // → "undefined" = 同理
typeof advance        // → "undefined" = 脚本在 advance 之前就终止了
typeof renderNode     // 同上

// 2. 如果引擎函数全 undefined，说明脚本早期就崩了
//    检查 applyMute() 之后的函数是否可用
typeof playSfx        // → 如果在 applyMute() 之后，因 TDZ 崩掉则不可用
typeof toggleMute     // → 函数声明被提升，即使 TDZ 崩掉也可见
```

**如果 `showHero`/`showDialog`/`playSfx` = undefined 但 `toggleMute`/`applyMute` 存在：**

**罪魁祸首：TDZ（pitfalls.md #13）**— `applyMute()` 在脚本中立即执行，引用了后文 `let` 声明的 `bgmAudio`/`ambAudio` → ReferenceError → 脚本执行到此停止 → 后续所有 `let` 变量（包括 `typingAudio`）和函数定义全部跳过。

```javascript
// 确诊方法——检查变量声明顺序
// 在 HTML 源码中搜索：
//   let bgmAudio    ← 必须出现在 applyMute() 之前
//   let ambAudio    ← 必须出现在 applyMute() 之前
//   let ambFadeTimer ← 必须出现在 applyMute() 之前
// 确认 applyMute() 调用出现在所有 let 声明之后
```

**根因易混淆**：报错的是 `typingAudio`（因为 advance() 最终调用了 stopTypingSfx），但实际崩掉的是更早的 `bgmAudio`/`ambAudio`。永远检查引用链上最早的 let。

**如果 `toggleMute` 也不存在或者脚本完全没执行：**

**罪魁祸首：const 重复声明（pitfalls.md #14）**——`const SFX_LIST` 或 `const ASSETS_BASE` 被声明了两次 → SyntaxError → 脚本整段无效。

```javascript
// 确诊方法——在 HTML 源码中搜索：
//   grep -n "const SFX_LIST" index.html    ← 应仅有 1 处
//   grep -n "const ASSETS_BASE" index.html ← 应仅有 1 处
//   grep -n "// ============ 音效系统" index.html ← 应仅有 1 节
```

---

## 第八层：字体与动画质感检查

当核心功能跑通但用户反馈"细节有问题"时：

```javascript
// 检查字体家族
getComputedStyle(document.body).fontFamily  // 不应是 sans-serif（默认）
getComputedStyle($('hero-title')).fontFamily  // 标题用 serif
getComputedStyle($('dialog-text')).fontFamily  // 正文用 sans-serif

// 检查 hero 停留时长
// 在 showHero 中：setTimeout(remove, 5000) → 应为 5000ms（不低于 4000ms）

// 检查 scene 章节过渡时长
// 在 renderNode(scene) 中：setTimeout(advance, 2500) → 应为 2500ms（不低于 2000ms）
```

## 第九层：音效系统验证

```javascript
// 检查音频基础设施
typeof playSfx        // → 'function'
typeof playBgm        // → 'function'
typeof startAmb       // → 'function'
typeof toggleMute     // → 'function'
typeof startTypingSfx // → 'function'

// 检查打字音效
// 如果是 Web Audio API 生成，打字时应该有 click 音
// 如果是依赖 typing.mp3：检查 ./assets/typing.mp3 是否存在
```

## 第十层：图片时代准确性验证（人肉验收）

这个无法自动化，必须人工查看每张图片确认：

| 节点 | 应有年份 | 发型特征 | 球衣特征 | 视觉年龄 |
|------|---------|---------|---------|---------|
| hero_1 | 1998 | 金色板寸 | 英格兰白#7 | 23岁 |
| hero_6 | 1998-99 | 稍长金发 | 曼联红 | 23-24岁 |
| hero_8 | 2001-02 | 莫西干头 | 英格兰白#7 | 26-27岁 |

**如果发现图片与历史不符** → 回看 prompt 缺少哪个锚定维度 → 补上后重生成。

- [ ] 点击"进入故事"→启动页 fade-out→scene 背景+ HUD 出现
- [ ] scene 自动推进到 hero/narrate（~2.2s）
- [ ] hero 定格 3s 后自动消失
- [ ] dialog 文本显示（非空）
- [ ] panel 浮层出现（4s 自动淡出）
- [ ] choice 选项可点击且理解度加分
- [ ] card 卡片内容完整（标题+正文）
- [ ] 全 80+ 节点无卡死
- [ ] ending 结局按理解度分支

## 门禁指令速查

当需要上线新 VNS 游戏时，执行以下完整流程（含两道门禁）：

```bash
# 1. 数据格式校验（assemble 前）
python ~/.hermes/scripts/vns/validate_script.py script_flat.json --img-dir compressed/

# 2. 构建
python ~/.hermes/scripts/vns/assemble.py --script script_flat.json --img-dir compressed/ --title "标题" --out dist/index.html

# 3. 自动验收（assemble 后）
python ~/.hermes/scripts/vns/accept_test.py dist/index.html
```
