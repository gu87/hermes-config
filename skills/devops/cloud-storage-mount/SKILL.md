---
# Cloud Storage Mount — 云存储挂载

将网盘通过 Alist（WebDAV 网关层）→ CloudDrive 2（FUSE 挂载层）挂载为 macOS 本地文件夹。

## 架构

```
夸克/百度/阿里网盘
    ↓ (API + Cookie)
Alist (http://localhost:5244) — 存储驱动层
    ↓ (WebDAV)
CloudDrive 2 (http://localhost:19798) — FUSE 挂载层
    ↓ (本地文件系统)
~/Desktop/CloudDrive/ — 本地访问
```

## Alist 存储驱动配置流程

### 通用步骤

1. **打开 Alist Web UI** → `http://localhost:5244` (账号: `admin`, 密码: `admin`)
2. 左侧导航 **存储** → 点 **添加**
3. 选择要添加的驱动类型
4. 填 **显示文件夹名称**（建议 `/网盘名`，唯一、不可重复）
5. 填驱动特定的认证信息（Cookie / Token / RefreshToken）
6. 默认项: 缓存30分钟、WebDAV策略302重定向、根文件夹ID `0`
7. 点 **保存**

### 夸克网盘 Cookie 提取（关键技术）

夸克网盘的认证走 Cookie，而非 OAuth Token。**关键坑：`document.cookie` 拿不全（缺 HttpOnly）**。

#### ✅ 正确方法（Playwright Context API）

用 Playwright 的 `context.cookies()` 获取全部 Cookie（含 HttpOnly）：

```javascript
// 登录夸克网盘后
const cookies = await page.context().cookies('https://pan.quark.cn');
const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join('; ');
// cookieStr 约 1700+ 字符
```

#### ❌ 不完整的方法（仅限快速查看）

```javascript
// 在浏览器 Console 或 Playwright evaluate 执行
document.cookie;
// ⚠️ 拿不到 HttpOnly cookie（如 __puus、__pus、_UP_*）
// 用这个填进 Alist 会报: Failed init storage: require login [guest]
```

#### 提取步骤

```
步骤 1: Playwright 打开 https://pan.quark.cn
步骤 2: 用户扫码登录 / 手机验证码登录
步骤 3: 确认进入 https://pan.quark.cn/list 文件列表页
步骤 4: 用 page.context().cookies() 提取全部 Cookie（~1700 字符）
步骤 5: 粘贴到 Alist 夸克配置的 Cookie 输入框（id="cookie"）
步骤 6: 点保存
```

#### 错误诊断

| 错误 | 原因 | 修复 |
|------|------|------|
| `Failed init storage: require login [guest]` | Cookie 不完整（缺 HttpOnly） | 改用 Playwright context API 重取 |
| 保存后页面跳转到登录页 | Alist 会话超时，但 **存储已保存成功** | 重新登录后检查存储列表状态 |

**注意**：
- Cookie 有有效期，过期后需重新提取
- 如果扫码登录后页面没跳转，手动导航到 https://pan.quark.cn/list
- Alist Web UI 保存操作会触发登录重定向（会话过期），但实际保存已生效 — 用存储列表页的状态为准

## CloudDrive 2 WebDAV 挂载

Alist 存储驱动保存后，会在自身暴露 WebDAV 端点：
```
http://localhost:5244/dav/网盘路径
```

### ⚠️ 已知 Bug：CloudDrive 2 忽略 WebDAV 路径字段

**现象：** 在 CloudDrive 2 的 WebDAV 配置对话框中，填入路径 `/dav` 后 URL 预览仍显示 `http://localhost:5244`（不含 `/dav`）。连接时报错：
```
decode error: list response code not 207
```

**根因：** CloudDrive 2 的 WebDAV 实现**不将 path 字段拼入 URL**。它将路径 `/dav` 作为根目录筛选器（而非 WebDAV 端点路径）。实际发起的 PROPFIND 请求目的地是 `http://localhost:5244/`（返回 405，非 207）。

**验证：**
```bash
# Alist WebDAV 端点（正确响应）
curl -s -o /dev/null -w "%{http_code}" -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5244/dav/
# → 207

# 根路径（CloudDrive 2 实际请求）
curl -s -o /dev/null -w "%{http_code}" -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5244/
# → 405（非 207）
```

### 方案：Python 反向代理（推荐）

用本地代理将根路径 `/` 透明转发到 Alist 的 `/dav`，同时重写 WebDAV XML 响应中的 href 路径：

```
localhost:5250  →  localhost:5244/dav
↓ PROPFIND /        ↓ PROPFIND /dav/
↓ GET /夸克网盘/..   ↓ GET /dav/夸克网盘/..
```

**安装步骤：**

1. **启动代理**（确保脚本在固定路径）：
   ```bash
   # 一次性启动
   python3 ~/home/development/scripts/alist-webdav-proxy.py 5250 &

   # 验证（应返回 207）
   curl -s -o /dev/null -w "%{http_code}" -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5250/
   ```

2. **配置开机自启（launchd）**：
   ```bash
   cat > ~/Library/LaunchAgents/com.alist-webdav-proxy.plist << 'EOF'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.alist-webdav-proxy</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/bin/python3</string>
           <string>/Users/gu/home/development/scripts/alist-webdav-proxy.py</string>
           <string>5250</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/Users/gu/Waytech/Alist/log/proxy_stdout.log</string>
       <key>StandardErrorPath</key>
       <string>/Users/gu/Waytech/Alist/log/proxy_stderr.log</string>
   </dict>
   </plist>
   EOF
   launchctl load ~/Library/LaunchAgents/com.alist-webdav-proxy.plist
   ```

3. **在 CloudDrive 2 中添加 WebDAV 存储**（用代理端口）：
   | 字段 | 值 | 说明 |
   |------|------|------|
   | 协议 | **HTTP** | |
   | 服务器地址 | `localhost` | |
   | 端口 | `5250` | **代理端口** |
   | 路径 | **留空** | 代理已映射到 `/dav` |
   | 用户名 | `admin` | Alist 认证 |
   | 密码 | `admin` | Alist 认证 |
   | 匿名访问 | ❌ 不勾 | |

4. **验证挂载**：桌面上 `~/Desktop/CloudDrive/` 下应出现 `WebDAV/夸克网盘/` 目录。在 CloudDrive 2 文件浏览器中导航到 WebDAV → 夸克网盘 应列出所有文件。

#### ⚠️ 代理关键坑点

1. **Alist WebDAV 返回的 href 路径带 `/dav/` 前缀**（如 `<D:href>/dav/夸克网盘/</D:href>`），但 CloudDrive 2 做路径匹配时期望不带前缀。**不重写的话报 "error decoding response body" / FUSE I/O error。**

   代理需在转发时做 XML body 重写：
   ```python
   text = text.replace("<D:href>/dav/", "<D:href>/")
   text = text.replace("<D:href>/dav", "<D:href>/")
   ```

2. **重写 body 后必须修正 Content-Length**。原始响应头中的 Content-Length 对应未重写的数据长度，不修正则客户端读多/读少：
   ```python
   # 跳过原始 Content-Length
   # 发送修正后的值
   self.send_header("Content-Length", str(len(data)))
   ```

3. **http.server.BaseHTTPRequestHandler 是 HTTP/1.0**，不支持 chunked encoding。必须从响应头中剥离 `Transfer-Encoding`, `Connection`, `Keep-Alive`，否则 curl 报 `chunk hex-length char not a hex digit`。

4. **验证命令**：
   ```bash
   # 应返回 207
   curl -s -o /dev/null -w "%{http_code}" -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5250/
   # 应返回 207（子目录）
   curl -s -o /dev/null -w "%{http_code}" -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5250/%E5%A4%B8%E5%85%8B%E7%BD%91%E7%9B%98/
   # 应返回 href="/夸克网盘/"（不含 /dav/ 前缀）
   curl -s -X PROPFIND -H "Depth: 1" http://admin:admin@localhost:5250/ | grep -o "<D:href>[^<]*</D:href>"
   ```

### 已知限制：双层 FUSE I/O 错误

CloudDrive 2 FUSE (`~/Desktop/CloudDrive/`) 挂载 WebDAV 存储后，文件列表可能出现：
```
ls: fts_read: Input/output error
```

**根因：** 双层 FUSE 架构（macFUSE → CloudDrive 2 FUSE → Alist WebDAV → 网盘 API）导致的心跳/超时问题。FUSE 层对远端文件系统的状态缓存与 HTTP WebDAV 的真实状态不同步。

**应对方案：**
- 优先使用 Alist Web UI (`http://localhost:5244`) 直接访问夸克网盘文件
- 通过 macOS Finder → Go → Connect to Server → `http://admin:admin@localhost:5244/dav` 挂载 WebDAV（绕过 CloudDrive 2 FUSE）
- 大文件操作直接在 Alist 或夸克网盘原生客户端完成

### 在 CloudDrive 2 中添加（直连方式 — 仅用于其它网盘）

1. 打开 CloudDrive 2 Web UI `http://localhost:19798`（默认账号: `86741711@qq.com`，密码由用户记忆） 
2. 左侧边栏 **云存储** → 点 **+ 添加云盘**
    - 在弹出的对话框中选择「本地存储 → **WebDAV**」
3. 填表单（⚠️ CloudDrive 2 的 UI 框架不响应 `getByLabel`—Playwright 需用 `evaluate` 直接 DOM 赋值）:

| 字段 | 值 | 注意 |
|------|------|------|
| 协议 | **HTTP**（默认已选中） | 本地服务不用 HTTPS |
| 服务器地址 | `localhost` | |
| 端口 | `5244` | 可选字段，需手动填 |
| 路径 | `/dav` | 已预填，确认保留 |
| 用户名 | `admin` | Alist 的登录账号 |
| 密码 | `admin` | Alist 的登录密码 |
| 匿名访问 | ❌ 不勾 | 需要认证 |

4. 点 **添加** → 挂载成功
5. 文件出现在 `~/Desktop/CloudDrive/` + Alist 存储列表中

#### Playwright 操作要点

CloudDrive 2 WebDAV 配置对话框的 input 没有可用的 `placeholder` 或 `aria-label`，标准 `getByLabel` 和 `getByPlaceholder` 会超时。推荐通过 JavaScript 直接操作 DOM：

```javascript
// 在 dialog 内定位 inputs
const inputs = document.querySelectorAll('.modal-content input:not([type="checkbox"]):not([type="number"])');
// [0]=地址, [1]=用户名, [2]=密码
const numbers = document.querySelectorAll('input[type="number"]');
// [0]=端口
```

参考 `references/quark-cookie-extraction.md` 的「坑点总结」部分。

## 开机自启确认

CloudDrive 2 和 Alist 都已配置 launchd 开机自启：

```bash
# 确认运行
launchctl list | grep -E 'clouddrive|alist'

# 查看 plist
cat ~/Library/LaunchAgents/com.clouddrive2.plist
cat ~/Library/LaunchAgents/com.alist.plist
```

## 已知问题

| 问题 | 原因 | 应对 |
|------|------|------|
| Cookie 过期 | 夸克登录态有效期短 | 定期刷新 cookie，建议每次需要访问时重新提取 |
| CloudDrive 2 卡顿 | FUSE 远程文件系统物理延迟 | 热数据放本地，冷数据走云；大文件操作避免实时读写 |
| 飞书 DNS 间歇失败 | 系统/网络层 | 重启网络或重试 |
| MacBook Air 8GB | 内存小，多服务同时运行吃力 | 避免 CloudDrive 2 + 浏览器 + 本地 AI 同时运行 |

## 参考文件

- `references/quark-cookie-extraction.md` — 夸克 Cookie 提取详细实操记录（含 Alist 路径历史、WebDAV 代理方案）
- `scripts/alist-webdav-proxy.py` — Python WebDAV 反向代理脚本（含 href 路径重写 + Content-Length 修正）
- `templates/com.alist-webdav-proxy.plist` — 代理开机自启 launchd plist 模板

agents: [nesta, hermes]
---
