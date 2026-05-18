# 用户自定义参考图检索协议

## 背景

用户在审计 HTML 中通过「📤 上传参考图」功能上传了图片，然后导出 JSON。导出时 `hasCustomRef: true` 和 `customRefFilename` 记录了上传的文件名。但上传的图片以 data URL 形式存在浏览器内存中，不会自动落盘到项目目录——需要手动从用户系统的 Downloads 目录（或其他默认保存位置）找到并复制到项目中来。

## 触发条件

用户导出了审计 JSON，且其中包含 `hasCustomRef: true` 的条目。用户说「图片都在downloads 文件夹里，你自己去找」或类似意思。

## 执行流程

### 第一步：读取导出 JSON

```bash
ls -lt ~/Downloads/vns-audit-decisions-*.json | head -3
```

读取 JSON 找到 `hasCustomRef: true` 的卡片，记录 `customRefFilename`（文件名）。

### 第二步：扫描 Downloads 查找文件

```bash
ls -lt ~/Downloads/ | head -30
```

在列表中找到与 `customRefFilename` 匹配的文件。注意文件名可能看上去不像真名（如 `rBXRn2n8L8-AeaJ4AAJHF4LeS7s152.jpg`、`unnamed.gif`）。按修改时间和文件大小辅助判断。

### 第三步：复制到项目目录

```bash
cd ~/Projects/<game>/audit/photos
cp ~/Downloads/<原始文件名> user_<卡片ID>.<原扩展名>
```

命名规则：`user_<卡片ID>.<ext>`（如 `user_hero_1_debut.jpg`、`user_panel_2_freekick_scene.gif`）。

### 第四步：更新 audit HTML 的 ref 链接

找到对应卡片的 `ref: "..."` 字段，改为指向新复制的用户图：

```
ref: "photos/user_hero_1_debut.jpg"
```

### 第五步：验证

确认 HTML 中没有 `ref: null` 条目，所有卡片都有了参考图。

## 文件名常见模式

| 来源 | 文件名特征 | 示例 |
|------|-----------|------|
| 微信/手机截图 | `screenshot-YYYYMMDD-HHMMSS.png` | `screenshot-20260517-234437.png` |
| 浏览器下载 | 哈希文件名 | `rBXRn2n8L8-AeaJ4AAJHF4LeS7s152.jpg` |
| 网页保存 | 原始文件名 | `U773P427T9D353F259DT20060222175039.jpg` |
| GIF 动图 | `unnamed.gif` | 通常来自懂球帝文章的 GIF 片段 |
| WebP 格式 | 哈希 `.webp` | `0302b301knqb51hy5yy010fywgo5tqpc2n.webp` |

## 注意事项

- `unnamed.gif` 是来自文章长图/动图的常见文件名。扩展名虽然为 `.gif` 但可能内容为静态截图。
- 文件的修改时间通常和导出 JSON 接近（几分钟内），这是识别依据之一。
- 下载目录中可能有大量不相关文件（PDF、PPT、zip 等），按时间排序最有效。
- 不要在 user_ 文件名中包含中文或特殊字符，只用 `_` 分隔。
