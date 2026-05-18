# VNS 系列踩坑记录

## 1. 皮尔洛剧本格式

**问题**：皮尔洛输出复杂 panel 结构（`layout:'split_left_right'`, `left:{illustration:{type:'illustration'}}`），引擎只支持简单 `{type:'panel', src:'key', pos:'br'}`。

**修复**：每次皮尔洛输出后必须运行 `fix_script.py` 标准化。

**解决**：在派单时明确约束格式（见 SKILL.md 阶段②约束）。

## 2. 图片 key 映射

**问题**：皮尔洛把 scene/panel/hero 的图片字段写成 `"?"`。引擎找不到图就显示空白的 navy 背景。

**修复**：`fix_script.py` 自动补 "?" 为 bg01~bg05 / hero_1~hero_N / panel_1~panel_N。生图后再用 gen.py 补图 + assemble.py 重建。

**理想流程**：
```
皮尔洛 → fix_script.py → key 已分配 → gen.py 生图（按 key 命名）→ compress.py → assemble.py
```

## 3. Terminal 中文注释问题

**问题**：在 terminal tool 的 bash command 字符串里，`# 中文注释` 行会被 shell 识别为命令而非注释，报错 `command not found`。

**修复**：不在 terminal 命令前面写中文注释行。要么放到命令末尾用 `# comment`，要么用 `echo "注释"` 单独一行，要么全用英文 `# English comment`。

## 4. compress.py 工作目录

**问题**：compress.py `--dir raw/` 参数是相对路径，需要先 `cd raw/` 或用绝对路径。

**修复**：运行时确保 cwd 正确，或直接用 `--dir /absolute/path/raw/`。

## 5. gen.py 503 超时

**问题**：GPT Image 2 API 高峰期 503。

**修复**：内置 3 次重试 + 300s timeout。如果频繁失败可增加 retries=5。

## 6. 引擎锁冲突 — 第一帧后游戏卡死

**问题**：scene 节点 `locked=true`（持续 2500ms）但 `setTimeout(advance, 800)` 在 800ms 时被自己的锁吞掉 → auto-advance 无声跳过，cursor 停在 scene 下一节点不推进。

**表现**：点击"进入故事"后，启动页 fade-out，只剩下 mute 按钮，什么也不显示。点哪儿都不推进。

**诊断方法**：浏览器 console 检查 `cursor`——如果 cursor=1（只走了 scene 节点），且 `locked=false`，就是此 bug。

**修复**：把 `assemble.py` ENGINE_TEMPLATE 中 scene 的 `setTimeout(advance, 800)` 改为 `setTimeout(advance, 2800)`（必须大于 lock duration 2500ms）。当前配置：locked=2500ms, auto-advance=2800ms。

## 7. dialog 字段名不匹配

**问题**：皮尔洛数据的 dialog 节点用 `"dialog": "文本内容"`，但引擎 `renderNode` 中 dialog handler 读的是 `node.text` → 所有对话文本显示为空。

**表现**：游戏能推进，对话框出现（classList show），但对话文本为空。

**诊断方法**：检查 SCRIPT 中 dialog 节点的字段名 vs 引擎 `renderNode()` 对应 handler 读的字段。

**修复**：引擎代码中 `showDialog(node.speaker, node.text)` → `showDialog(node.speaker, node.dialog)`。或者在 fix_script.py 中加入字段重命名。

## 8. card 字段名不匹配

**问题**：皮尔洛数据的 card 节点用 `"description": "..."`，但引擎 `showCard()` 读的是 `node.text` → 卡片内容空白。

**表现**：card 节点触发后弹出卡片框，标题有但正文空。

**修复**：引擎 `$('card-text').textContent = node.text || ''` → `node.description || node.text || ''`。同时 `card-photo` 的 src 应 fallback 到 `IMG_DICT[node.icon_img]` 因为数据可能只提供了 icon 字符串而非真实图片。

## 9. 图片生成数量不足

**问题**：generate_images.json 或 flatten.py 分配的图片 key 总数 > gen.py 实际生成的张数 → IMG_DICT 缺少 key。

**表现**：游戏画面中部分 panel/hero 显示裂图（而非缺失背景时的 navy 纯色）。不是崩溃级 bug，但影响体验。

**诊断方法**：浏览器 console 执行 `Object.keys(IMG_DICT)` 对比 SCRIPT 中引用的 image/hero/src/bg 总去重数。引用数 > IMG_DICT keys 数 ＝ 缺失。

**根本原因**：gen.py 的 batch 任务清单不全——只包含了 bg01-bg05 + hero_1，但 SCRIPT 引用了 hero_2~13 和 panel_1~9 等共 27 张图。

**修复**：从 SCRIPT 中提取所有图片引用 key，生成完整的 batch.json 传给 gen.py。

## 11. Race condition — hero 自动推进 vs 点击推进冲突

**问题**：`showHero()` 在 3s 后 `classList.remove('show')` 再加 `setTimeout(advance, 200)`。中间的 200ms 间隙中 hero-box 已消失，点击事件也能触发 `else { advance(); }`。两个 advance() 同时调用→双重推进→skip 掉 narrate 节点。

**表现**：
- cursor 跳过 narrate 节点（2→3→4 而非 2→3→等待→4）
- 玩家没看到台词就跳过去了
- 在 Playwright 自动化测试中表现为：点击"进入故事"后，画面从黑屏直接跳到 panel/narrate，中间的 hero 定格+旁白消失

**诊断方法**：
1. 浏览器 console 检查 `cursor`——如果倒序对比显示隔了几步（如 cursor=4 但对话框没出现过）
2. 在 `showHero` 的 `setTimeout(advance, 200)` 处加 console.log 确认触发次数

**根本原因**：advance() 没有互斥保护——setTimeout 和 click handler 都能独立调用它。

**修复**：在 advance() 中加入 `advancing` 互斥锁：
```javascript
let advancing = false;
function advance() {
  if (locked || advancing) return;
  advancing = true;
  // ... read node, advance cursor ...
  advancing = false;
  renderNode(node);
}
```
确保两次 advance() 不会同时执行。已在 `assemble.py` ENGINE_TEMPLATE 中修复。

## 12. Browser console 空错误消息但 JS 未执行

**问题**：Playwright `browser_console` 显示多个 `{"message": "", "source": "exception"}` 空错误，无法通过 `e.message` 获取详情。

**根本原因**：这些是浏览器运行时级别的无声错误（而非 JS 抛出异常），可能来自：
- 极大 base64 data URI 赋值给 `element.style.backgroundImage = 'url(data:...)'` 被浏览器拒绝（超出 CSS url() 长度限制）
- `new Audio('nonexistent.mp3')` 资源加载 404（浏览器不抛 JS 异常）
- CSS `url()` 中 base64 长度超过浏览器限制

**诊断方法**：
1. 临时注释掉 `setBg()` 调用确认是否该行导致
2. 检查 `document.getElementById('scene').style.backgroundImage.length`——如果为 0 但 `IMG_DICT[key]` 存在，说明赋值被浏览器吞了
3. 检查 Audio 路径 `document.querySelectorAll('audio')` 数量和状态
4. 在浏览器中设置全局错误数组：`window.__errors = []; window.onerror = function(msg,url,line,col,err) { window.__errors.push({msg,url,line,col,stack:err?.stack}); return true; }`
|
|**修复**：base64 图片目前无法避免，但可以在 `setBg` 中加入 try-catch 并用 bg-img 替代 backgroundImage。Audio 的 404 可通过 `new Audio().onerror` 捕获。

## 13. TDZ（暂时性死区）— let 变量引用未声明

**问题**：`applyMute()` 在脚本中立即执行（`applyMute()` 调用），但函数内引用了 `bgmAudio` 和 `ambAudio`。这两个变量用 `let` 声明在调用之后 → TDZ 错误 → 整个脚本崩掉 → 所有后续代码（包括 `typingAudio`、`showHero`、`showDialog`）都未初始化。

**表现**：
- 页面加载，启动页正常，点击"进入故事"后 scene 渲染，但 cursor 停在 scene 下一节点不前
- 浏览器 console 看到 `ReferenceError: Cannot access 'typingAudio' before initialization`
- 实际根因是 `bgmAudio`/`ambAudio` 的 TDZ，不是 `typingAudio` 本身
- 手动 `try { advance() } catch(e) { e.message }` 显示 `Cannot access 'typingAudio' before initialization`

**诊断方法**：
```javascript
// 检查是否有 let 变量在声明前被访问
// 常见区域：在声明的行号之前查找对该变量的引用
```

**根本原因**：`let` 和 `const` 有暂时性死区——在声明之前访问会抛出 ReferenceError。函数定义（function declaration）会被提升，但 `let` 变量不会。

**修复**：将所有脚本级 `let` 变量声明移至引用它们的函数调用之前。具体：
1. 找到 `applyMute()` 调用
2. 检查它引用了哪些后续声明的 `let` 变量（bgmAudio, ambAudio, ambFadeTimer）
3. 将这些 `let` 声明移到 `applyMute()` 之前

已在 `assemble.py` ENGINE_TEMPLATE 中修复。

## 14. const 重复声明

**问题**：ENGINE_TEMPLATE 中 `const SFX_LIST`、`const sfxCache`、`const ASSETS_BASE` 被声明了两次 → JavaScript 抛出 SyntaxError → 后续引擎函数（showHero、showDialog 等）无法定义。

**表现**：
- 页面能加载但游戏无响应
- 脚本执行到重复声明处报错后停止
- 看起来像所有引擎功能都失灵

**修复**：确保每个 `const` 变量只声明一次。在 `assemble.py` 模板中检查是否有两个 `// ============ 音效系统 ============` 节。保留第一个，删除第二个（及其附带的重复声明）。

已在 `assemble.py` ENGINE_TEMPLATE 中修复。

## 17. 球场/比赛地核查不精确 — 写错比赛场馆

**问题**：为贝克汉姆 1998 年世界杯 vs 哥伦比亚的 hero 图写了 "Stade de Marseille"，实际比赛在 **Stade Félix-Bollaert, Lens**。GPT Image 2 会按 prompt 生成的场景是错误的。

**表现**：导语/面板背景图与实际比赛场馆不符。用户指出"细节有问题"后需要我们逐一核查才发现。

**根因**：凭记忆写球场名，没查 Wikipedia 确认。马赛是 98 世界杯一个著名主场，但英哥之战不在那里。

**预防**：写任何球场名之前，必须查 Wikipedia 比赛页面确认 `Venue` 字段。写完后必须检查：
```bash
# 检查 prompt 中所有球场名是否与 Wikipedia 一致
# 常见容易搞混的：
# 1998 英哥之战 → Stade Félix-Bollaert, Lens（不是 Marseille）
# 1998 英阿之战 → Stade Geoffroy-Guichard, Saint-Étienne
# 2002 英阿之战 → Sapporo Dome, Sapporo（不是东京/横滨）
```

## 18. 预选赛与正赛混淆 — 比赛性质搞错

**问题**：hero_8 的 prompt 写 "at 2002 FIFA World Cup, about to take a free kick against Greece"，而这场是 **2001 年 10 月 6 日的世界杯预选赛**（希腊需要先晋级才能出现在 2002 正赛）。"2002 FIFA World Cup" 和 "Greece qualifiers" 本身就是矛盾的。

**表现**：GPT Image 2 不知道该理解为世界杯正赛还是预选赛 — 生成的背景可能包含世界杯元素（2002 标志、日本场馆等），与真实历史不符。

**根因**：把预选赛和正赛混为一谈，没区分 "2002 World Cup qualifier" vs "2002 FIFA World Cup tournament"。

**预防**：写 prompt 前先确认：
- 这是预选赛（qualifier）还是正赛（tournament）？
- 预选赛的场馆通常在主办国（希腊主场在雅典，英格兰主场在老特拉福德）
- 正赛的场馆在主办国（韩日世界杯在韩国/日本）

## 19. 跨年发型不同 — 同一人物不同年份发型不同

**问题**：把贝克汉姆 2002 年世界杯的**莫西干头**错误地用在了 2001 年希腊预选赛 prompt 中。实际上他 2001 年留的是**短刺金发**，莫西干是 2002 年世界杯专门换的造型。

**表现**：图片中人物发型与真实历史不匹配，用户在查看 promo 时发现不对。

**根因**：只记住了人物最出名的造型（莫西干），没查该造型从哪年开始到哪年结束。

**预防**：足球运动员发型变化频繁。必须按**具体年份**查证发型，不能笼统地用"该人物最著名的造型"覆盖整个时期。可参考贝克汉姆发型时间线模型自行编制核查表。
- 2001 → short spiky bleached (not mohawk)
- 2002 → bleached mohawk (World Cup)
- 2003 → longer darker, roots showing (Real Madrid)
- 2004 → short with shaved sides (Euro 2004)

**问题**：为历史/真实人物（如贝克汉姆）生成 hero/panel 图片时，prompt 写成 `"A dramatic portrait of David Beckham" + 中文对话`。没有年份、发型、球衣、年龄信息 → GPT Image 2 自由发挥 → 生成的人物形象与真实历史年代严重不符。

**表现**：
- 1998 年的贝克汉姆应该是金色板寸 + 英格兰白色 #7，但图片显示了其他年代的发型/球衣
- 用户看到第一眼就说"图片生成的太差了"

**根本原因**：把真实人物当作虚构角色处理——只给了名字，没给年代锚点。GPT Image 2 没有时间感，只会生成"最普遍的贝克汉姆形象"（往往是后期更出名的造型）。

**修复**：prompt 必须包含**全部身份锚定维度**：

| 维度 | 必须包含 | 示例 |
|------|---------|------|
| 年份/赛事 | 具体年份+比赛 | "1998 FIFA World Cup group stage" |
| 发型 | 具体描述 | "short bleached blonde buzz cut" |
| 球衣 | 球队+款式+号码 | "England white #7 jersey" |
| 年龄 | 数字年龄 | "23 years old" |
| 场景 | 具体球场/地点 | "at Stade de Marseille" |
| 情绪/表情 | 对应剧情情绪 | "young determined expression" |

**正确示例**（9 个维度全齐）：
```
"David Beckham in 1998, 23 years old, short bleached blonde buzz cut hair, England national team white #7, standing on the pitch at Stade de Marseille, 1998 FIFA World Cup, young determined expression, bright summer sunlight, photorealistic sports photography, 4K, Canon 1D, shallow depth of field, green grass background, emotional moment, wide shot"
```

**自检清单**（生成前逐条检查）：
- [ ] 年份明确？（不是"in the 90s"，是"1998"）
- [ ] 发型匹配该年份？
- [ ] 球衣/制服匹配该年份？
- [ ] 年龄数字准确？
- [ ] 场景地名具体？
- [ ] 情绪/表情对应剧本当前节点？
- [ ] 每张 hero / panel 独立写 prompt，不共用模板？
- [ ] 同一角色的不同年代形象是否有明显区分度？

## 20. 选择分支 — 两个结果都显示（skipCount 缺失）

**问题**：Choice 节点的选项有 `next_node` 字段（如 `"ch1_resp_a"`），但引擎的 `advance()` 只做线性游标推进（`cursor++`），不按 `next_node` 跳转。Choice 之后的两个结果 narrate 节点按顺序排列在数组里，引擎逐个渲染 → 用户选一个选项后，两个结果都显示了。

**表现**：点击选项 A，先显示 A 的正确结果，再点一下，又显示了 B 的结果。用户说"我选了一个选项，对应把两个选项的后续都告诉我了"。

**根本原因**：脚本结构是扁平数组，不是节点图。`next_node` 是皮尔洛剧本的残留字段，引擎没有实现 node-id 跳转。Choice 的 onclick handler 只调用了 `advance()`，后者简单地 `cursor++` 并读取下一项。

**修复**：在引擎中加入 `skipCount` 机制（2026-05-17 已实装到 dist/index.html，需要同步到 assemble.py ENGINE_TEMPLATE）：

```javascript
// 1. 新增全局变量
let skipCount = 0;

// 2. 在 advance() 中读取节点后跳过未选中的分支
function advance() {
  if (locked || advancing) return;
  advancing = true;
  if (cursor >= SCRIPT.length) { advancing = false; showEnding(); return; }
  const node = SCRIPT[cursor];
  cursor++;
  // 选择分支：跳过未选中的选项结果
  while (skipCount > 0 && cursor < SCRIPT.length) {
    cursor++; skipCount--;
  }
  advancing = false;
  renderNode(node);
}

// 3. 在 showChoice() 中设置 cursor 和 skipCount
btn.onclick = () => {
  btn.classList.add('selected');
  const scoreGain = opt.score || (opt.affinity_effect ? Object.values(opt.affinity_effect).reduce((a,b)=>a+b, 0) : 0);
  setTimeout(() => {
    setScore(score + scoreGain);
    const choiceIdx = SCRIPT.indexOf(node);
    cursor = choiceIdx + 1 + i; // i=0→第一个结果(A), i=1→第二个结果(B)
    if (i === 0) { skipCount = 1; } // 选A：显示A结果后跳过B的结果
    else { skipCount = 0; }         // 选B：直接从B结果开始
    box.classList.remove('show');
    setTimeout(advance, 300);
  }, 400);
};
```

**工作原理**：每个 Choice 节点后紧跟着 2 个 outcome narrate 节点（A 的 + B 的）。选择 A（i=0）时，play A（index+1），然后 advance() 的 skipCount 循环跳过 index+2（B）。选择 B（i=1）时，直接跳到 index+2（B）开始播放。假定所有 Choice 都正好有 2 个 outcome 紧邻其后——如果未来有 3 选项或跳转跨度大的 Choice，此方案需要升级。

**验证方法**：在浏览器 console 中执行：
```javascript
// 确认 skipCount 存在
typeof skipCount // → 'number'

// 确认跳出正常
const choiceIdx = SCRIPT.findIndex(n => n.type === 'choice');
SCRIPT[choiceIdx + 1]  // → 应是选项 A 的结果
SCRIPT[choiceIdx + 2]  // → 应是选项 B 的结果
```

## 21. 重建 HTML 覆盖手动编辑 — ENGINE_TEMPLATE 不同步丢失

**问题**：直接在 `dist/index.html` 中修改引擎代码（字体、动画、音效、Choice 跳转等），然后 `assemble.py` 重建会将所有手动改动覆盖——assemble.py 从 ENGINE_TEMPLATE 生成全新 HTML。

**表现**：重建后字体回到 `sans-serif`，动画回到旧 timing，Choice 双结果 bug 复活。

**根本原因**：`assemble.py` 内部有一个 `ENGINE_TEMPLATE` 常量（r"""字符串），是引擎代码的权威源。dist/index.html 只是该模板的输出。

**修复**：所有引擎修改必须同步到 `assemble.py` 的 `ENGINE_TEMPLATE`。流程：
```
修改 ENGINE_TEMPLATE (assemble.py) → assemble.py 重建 → dist/index.html 包含改动
而不是：
修改 dist/index.html → ❌ assemble.py 重建覆盖丢失
```

**检查方法**：重建后关键字搜索验证改动是否仍在：
```bash
grep -c 'skipCount' dist/index.html    # 应为 ≥1（choice fix）
grep -c 'var(--font-serif)' dist/index.html  # 应为 ≥10（字体改动）
grep -c '5000' dist/index.html | head -1    # hero auto-dismiss
```

## 22. BGM_MAP 文件命名与章节数对齐

**问题**：每篇 H5 的章节数不同（贝克汉姆篇有 6 个章节含新增的 99-99 赛季），BGM_MAP 文件命名 `bgm_01.mp3` ~ `bgm_06.mp3` 但容易忘记在新增章节时添加映射。

**预防**：SCRIPT 中每个 scene(chapter) 节点必须在 BGM_MAP 中有对应条目。可用 console 验证：
```javascript
// 列出所有章节名并检查是否有 BGM
const chapters = [...new Set(SCRIPT.filter(n => n.chapter).map(n => n.chapter))];
const missing = chapters.filter(c => !BGM_MAP[c]);
if (missing.length) console.warn('Missing BGM:', missing);
```

BGM 文件放在 `dist/assets/`，不存在时游戏正常运行只是无背景音乐。

## 26. 首秀/关键比赛事件搞错 — 印象流替代事实核查

**问题**：为贝克汉姆世界杯首秀写 audit 数据时，写了"vs 突尼斯穿白色主场"——默认以为首秀是小组赛第一场。实际他首秀是对罗马尼亚（小组第二场）第 32 分钟替补出场，穿的是红色客场。

**表现**：用户直接指出事实错误。首秀卡片的数据完全不对：不仅比赛对手错、球衣颜色错、球场也错（Marseille→Toulouse）。

**根因**：没有查 Wikipedia match report 确认"谁首发了、谁替补了、第几分钟"。凭"世界杯首秀 = 第一场比赛"的默认印象写。

**修复流程**：
```
// ❸ 关键：不仅要确认"他在该届世界杯是否出场"
//     还要确认"具体哪一场是第一次出场"
//     Wikipedia match report 字段：Substitutes 下面的名单才是首次出场
```

**验证方法**：
1. 打开 Wikipedia 该届世界杯该小组页面（如 `1998 FIFA World Cup Group G`）
2. 找到 England vs Tunisia 的阵容 — 确认 Beckham 是否在 Starting XI
3. 找到 England vs Romania 的阵容 — 如果 Beckham 在第 32 分钟出现在 Substitutes 下，说明这是首秀
4. 交叉验证：Beckham 的 Wikipedia 个人页面 -> "1998 World Cup" 章节通常写 "made his World Cup debut as a substitute against Romania"

**白名单法**（最稳）：在 Wikipedia 比赛页面的 Starting XI 里搜人名——如果在列说明首发。在 Substitutes 下出现说明替补登场。如果在两个名单里都没出现，说明那场没上场。

## 25. AI生成图像含日文字符 — 漫画风格prompt导致日文招牌/文字

**问题**：使用 `manga-style` / `manga-inspired` prompt 生成图片时，AI 倾向于在背景中添加日文字符（招牌、告示牌、漫画拟声词等）。对于非日本题材（如英国足球），这些日文与场景完全不搭。用户反馈：「所有生成的图片里边，不要有日文」。

**修复**：在 prompt 末尾强制追加反日文指令（详见 SKILL.md 反日文指令模板）。

## 25b. Panel z-index 低于 dialog — 面板图被对话框遮挡不可见

**问题**：`.panel` 的 `z-index:15` 低于 `#dialog-box` 的 `z-index:20`，面板图被对话框覆盖不可见。

**表现**：面板图在 DOM 中存在且加载成功，但用户看不到。

**修复**：`.panel { z-index: 22; }`。

## 25c. Google Fonts CDN 国内加载失败

**问题**：ENGINE_TEMPLATE 中通过 Google Fonts CDN 加载中文衬线体，国内访问失败。

**修复**：移除 Google Fonts CDN，依赖系统字体栈。

## 27. post_gen.py 脚本路径依赖 — compress.py/assemble.py 不在项目目录

**问题**：`post_gen.py` 原先用 `os.path.dirname(__file__)` 找 `compress.py` 和 `assemble.py`，但这两个脚本在 `~/.hermes/scripts/vns/`，不在项目目录下。重建时找不到脚本报错。

**表现**：
```
python3: can't open file 'compress.py': [Errno 2] No such file or directory
```

**修复**：在 post_gen.py 顶部定义为绝对路径常量：
```python
SCRIPTS = os.path.expanduser("~/.hermes/scripts/vns")
```
然后引用 `os.path.join(SCRIPTS, "compress.py")`。

**实践教训**：不要在 post_gen.py 中用 `os.path.dirname(__file__)` 做路径推算——项目目录和脚本目录不在一起。硬编码 home-relative 路径在工作站可控的环境中最稳。

## 28. gen.py 中断恢复 — 半写文件被 skip 跳过

**问题**：`gen.py --batch` 的 `skip-if-exists` 机制检查的是**文件存在性**而非**文件完整性**。如果进程在写入 PNG 中途被 kill，残留的不完整文件（可能只有几 KB）会被当做"已生成"跳过，导致最终图片缺失。

**表现**：batch 跑完后某张图文件存在但极小（<100KB 而非正常的 2-3MB），内容损坏。

**预防**：中断恢复后，不要直接 rerun batch。先检查文件大小：
```bash
ls -lh raw/*.png | grep "$(date +%Y)"
# 找 <100KB 的异常文件
for f in raw/*.png; do sz=$(stat -f%z "$f"); [ $sz -lt 100000 ] && echo "SUSPICIOUS SMALL: $f ($sz bytes)"; done
```
确认所有文件大小正常后再跑剩余 batch。
