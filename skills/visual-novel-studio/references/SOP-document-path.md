# VisualNovelStudio SOP 文档

## 在线版本
https://gaokao.aisportsapp.com/sop_index.html

## Obsidian 本地存档
[[3-知识/wiki/AI与Agent/Hermes/VisualNovelStudio-SOP.md]]

## 会话更新记录

### 2026-05-16 本轮完成

**新获取的资产：**
| 资产 | 状态 | 备注 |
|------|------|------|
| GPT Image 2 API Key | ✅ 验证通过 | 已配置在 `scripts/config.py` |
| 引擎模板 | ✅ 已提取+内嵌 | 从 `game6mldn/index.html` 提取，内嵌在 `assemble.py` 中 |
| 引擎结构分析 | ✅ 已存档 | `references/engine-template-structure.md` |
| `gen.py` | ✅ 自建 | 支持单张+批量，含重试逻辑 |
| `edit.py` | ✅ 自建 | 支持图生图编辑 |
| `compress.py` | ✅ 自建 | 四种规格：bg/panel/hero/photo |
| `assemble.py` | ✅ 自建 | 完整构建脚本，引擎模板内嵌，SDK 保留口 |

**仍缺失：**
| 资产 | 获取路径 |
|------|---------|
| UnifiedRewardSDK | 找小李飞蛋拿 `unified-reward-bridge.js` |
| 懂球帝文章 API cookie | 登录 `frontadmin.dongqiudi.com` 获取 `laravel_session` |

---

## 依赖的外部资源
| 资产 | 来源 / 路径 | 状态 |
|------|------------|------|
| H5 引擎模板 | `https://gaokao.aisportsapp.com/game6mldn/index.html` | ✅ 已提取到 `~/Downloads/vns-engine-template.html`（2.3MB）|
| 引擎结构 | IMG_DICT (base64) + SCRIPT (DSL) + Engine (JS) + SFX | ✅ 完整 |
| 音效文件 | `https://gaokao.aisportsapp.com/game6mldn/assets/` | ✅ 可外链 |
| GPT Image 2 脚本 | `~/.hermes/scripts/vns/gen.py` | ✅ 自建（单张+批量模式） |
| 图片编辑脚本 | `~/.hermes/scripts/vns/edit.py` | ✅ 自建（支持 edit API） |
| 图片压缩脚本 | `~/.hermes/scripts/vns/compress.py` | ✅ 自建（bg/panel/hero/photo 四种规格） |
| API 配置 | `~/.hermes/scripts/vns/config.py` | ✅ 含 KEY + API endpoint + model 名 |
| 广告 SDK (UnifiedRewardSDK) | 小李飞蛋机器: `unified-reward-bridge.js` | ❌ 待获取 |
| 文章 API | 懂球帝 admin: `dadmin.dongqiudi.com` | ❌ 待获取 laravel_session cookie |
