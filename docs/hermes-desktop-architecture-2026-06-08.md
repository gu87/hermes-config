# Hermes 桌面应用架构详解

> 生成日期: 2026-06-08 | 目录: `apps/desktop/` (342 files, 285 symbols in main.cjs)

---

## 一、整体架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                     Electron Shell                             │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              Electron 主进程 (main.cjs)                  │   │
│  │  ┌────────────┐  ┌──────────┐  ┌───────────────────┐   │   │
│  │  │ 窗口/菜单  │  │ IPC 桥   │  │ 后端生命周期      │   │   │
│  │  │ 管理       │  │ (65 个)  │  │ (bootstrap/启动)   │   │   │
│  │  └────────────┘  └──────────┘  └───────────────────┘   │   │
│  │  ┌────────────┐  ┌──────────┐  ┌───────────────────┐   │   │
│  │  │ 终端管理   │  │ 内嵌浏览器│  │ 更新管理         │   │   │
│  │  │ (node-pty) │  │ (BrowserView)│                   │   │   │
│  │  └────────────┘  └──────────┘  └───────────────────┘   │   │
│  └────────────────────────────────────────────────────────┘   │
│                               │ IPC                            │
│  ┌────────────────────────────────────────────────────────┐   │
│  │            React 渲染进程 (Web UI)                       │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │              App Shell (布局框架)                   │   │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │   │   │
│  │  │  │ Titlebar │  │ Sidebar  │  │ RightSidebar  │   │   │   │
│  │  │  │ Controls │  │ (会话)    │  │ (终端/浏览器)  │   │   │   │
│  │  │  └──────────┘  └──────────┘  └──────────────┘   │   │   │
│  │  │  ┌──────────────────────────────────────────┐   │   │   │
│  │  │  │              Main Content                  │   │   │   │
│  │  │  │  (Chat / Agents / Settings / ...)          │   │   │   │
│  │  │  └──────────────────────────────────────────┘   │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │         NanoStores 状态管理层 (~30 stores)         │   │   │
│  │  │  session│layout│composer│boot│preview│gateway...   │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │            Hermes API Client (hermes.ts)          │   │   │
│  │  │  → backend gateway via JSON-RPC over WebSocket    │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、Electron 主进程 (`electron/main.cjs`)

### 2.1 启动生命周期

```
app.on('ready')
  │
  ├── 1. GPU 检测 (remote display → disable GPU)
  ├── 2. HERMES_HOME 解析 (~/.hermes 或 %LOCALAPPDATA%)
  ├── 3. 安装标记加载 (install-stamp.json)
  ├── 4. 应用菜单设置
  ├── 5. 主窗口创建 (BrowserWindow)
  ├── 6. 注册所有 IPC handlers (65 个)
  ├── 7. 引导后端 (bootstrap-runner → install.ps1/sh → venv)
  ├── 8. 启动 Hermes CLI backend (hermes dashboard)
  └── 9. 渲染 React SPA
```

### 2.2 核心常量

```javascript
HERMES_HOME          = ~/.hermes           // macOS/Linux
ACTIVE_HERMES_ROOT   = $HERMES_HOME/hermes-agent
VENV_ROOT            = $ACTIVE_HERMES_ROOT/venv
DESKTOP_LOG_PATH     = $HERMES_HOME/logs/desktop.log
PORT_RANGE           = 9120-9199
```

### 2.3 IPC 处理器体系 (65 个 handler)

| 类别 | 数量 | Handlers |
|------|------|----------|
| **后端生命周期** | 3 | `connection`, `backend:touch`, `boot-progress:get` |
| **Bootstrap** | 3 | `bootstrap:reset/repair/cancel/get` |
| **连接配置** | 6 | `connection-config:get/test/probe/oauth-login/oauth-logout/save/apply` |
| **Profile** | 2 | `profile:get/set` |
| **通用 API 代理** | 1 | `api` — 通用 API 请求代理 |
| **文件系统** | 5 | `readFileDataUrl` `readFileText` `selectPaths` `fs:readDir` `fs:gitRoot` |
| **剪贴板/图片** | 4 | `writeClipboard` `saveImageFromUrl` `saveImageBuffer` `saveClipboardImage` |
| **预览** | 3 | `normalizePreviewTarget` `watchPreviewFile` `stopPreviewFileWatch` |
| **终端 (PTY)** | 4 | `terminal:start/write/resize/dispose` |
| **内嵌浏览器** | 11 | `browser:mount/unmount/set-bounds/get-state/get-dom-summary/get-screenshot/get-selected-text/navigate/reload/stop/go-back/go-forward/is-available/type-text/verify-action-target` |
| **通知** | 1 | `notify` |
| **更新** | 4 | `updates:check/apply/branch:get/set` |
| **日志** | 2 | `logs:reveal/recent` |
| **杂项** | 9 | `titlebar-theme`, `fetchLinkTitle`, `version`, `requestMicrophoneAccess`, `previewShortcutActive`, `setting:defaultProjectDir:*`, `openExternal` |

### 2.4 终端管理 (node-pty)

```
terminal:start  → 创建 node-pty 进程 (zsh/bash/cmd)
terminal:write  → 向 PTY 写入字符
terminal:resize → 调整 PTY 尺寸 (cols/rows)
terminal:dispose→ 关闭 PTY 进程
```

- 通过 `node-pty` 实现原生终端
- macOS 会自动修复 `spawn-helper` 的可执行权限
- `terminalSessions` Map 维护多会话
- 事件：`terminal:data` (stdout 推送), `terminal:exit` (进程退出)

### 2.5 内嵌浏览器管理 (BrowserView)

```
browser:mount          → 创建 BrowserView 实例
browser:unmount        → 销毁视图
browser:set-bounds     → 调整位置/大小 (x/y/width/height)
browser:get-state      → 获取 URL/title/导航状态
browser:navigate       → 导航到 URL
browser:type-text      → 模拟键盘输入
browser:get-dom-summary→ 获取 DOM 摘要 (a11y tree)
browser:get-screenshot → 截屏 (base64)
browser:verify-action-target → 验证动作目标
```

- 由 Desktop Visible Provider 抽象暴露给 agent
- 只读操作（get-dom-summary/get-screenshot）不走 approval gate
- `type-text` 和 `verify-action-target` 需要 approval (action-gateway)

---

## 三、React 前端架构

### 3.1 入口渲染树 (`main.tsx`)

```tsx
<StrictMode>
  <ErrorBoundary>
    <QueryClientProvider>        ← @tanstack/react-query
      <I18nProvider>             ← 国际化 (i18n)
        <ThemeProvider>          ← 主题系统
          <HapticsProvider>       ← 触觉反馈
            <HashRouter>          ← react-router-dom
              <App />            ← DesktopController
```

### 3.2 路由表 (`routes.ts`)

| 路径 | View | 组件 | 渲染方式 |
|------|------|------|----------|
| `/` | chat | `ChatView` | 主内容区 |
| `/settings` | settings | `SettingsView` (lazy) | Overlay |
| `/agents` | agents | `AgentsView` (lazy) | Overlay |
| `/command-center` | command-center | `CommandCenterView` (lazy) | Overlay |
| `/skills` | skills | `SkillsView` (lazy) | 主内容区 |
| `/messaging` | messaging | `MessagingView` (lazy) | 主内容区 |
| `/artifacts` | artifacts | `ArtifactsView` (lazy) | 主内容区 |
| `/cron` | cron | `CronView` (lazy) | Overlay |
| `/profiles` | profiles | `ProfilesView` (lazy) | Overlay |
| `/browser` | browser | `BrowserWorkspace` (lazy) | 主内容区 |
| `/:sessionId` | chat | `ChatView` (resume) | 主内容区 |

Overlay views 以全屏模态卡片形式在 App Shell 上层渲染。

### 3.3 布局系统 (`AppShell`)

```
┌─────────────────────────────────────────────────────┐
│  Titlebar Controls                                   │
│  ┌──┬────────────┬──┬──────────────┬──┬──────────┐  │
│  │← │ Pane-Tools │  │ SystemTools  │  │ StatusBar│  │
│  │  │ (preview)  │  │ (haptic/prof │  │ (model)  │  │
│  └──┴────────────┴──┴──────────────┴──┴──────────┘  │
├────┬────────────────────────────────────────────────┤
│    │                                                 │
│ S  │              Main Content                       │
│ i  │  ┌────────────────────────────────────────┐   │
│ d  │  │     ChatView / ChatThread                │   │
│ e  │  │  ┌──────────────────────────────┐      │   │
│ b  │  │  │  MessageList (virtualized)    │      │   │
│ a  │  │  │  ├ UserMessage                │      │   │
│ r  │  │  │  ├ AssistantMessage           │      │   │
│    │  │  │  │  ├ MarkdownText            │      │   │
│    │  │  │  │  ├ ToolCalls               │      │   │
│    │  │  │  │  └ ToolApproval            │      │   │
│    │  │  │  └ ...                        │      │   │
│    │  │  └──────────────────────────────┘      │   │
│    │  │  ┌──────────────────────────────┐      │   │
│    │  │  │  Composer (rich editor)       │      │   │
│    │  │  │  ├ RichEditor (contenteditable)│     │   │
│    │  │  │  ├ Attachments                │      │   │
│    │  │  │  ├ Controls (submit/voice)    │      │   │
│    │  │  │  ├ QueuePanel                 │      │   │
│    │  │  │  └ HelpHint                   │      │   │
│    │  │  └──────────────────────────────┘      │   │
│    │  └────────────────────────────────────────┘   │
│    ├────────────────────────────────────────────────┤
│    │  Right Sidebar                                 │
│    │  ┌──────────┬──────────┐                       │
│    │  │ Terminal │ Browser  │                       │
│    │  │ (xterm)  │ (iframe) │                       │
│    │  └──────────┴──────────┘                       │
├────┴────────────────────────────────────────────────┤
│  Statusbar (model, provider, cwd, connection)        │
└─────────────────────────────────────────────────────┘
```

### 3.4 关键页面组件

#### ChatView — 核心聊天界面

```
ChatView
├── ChatSidebar             ← 会话列表（虚拟滚动、固定、分组）
│   ├── SessionRow          ← 每条会话（标题、摘要、时间）
│   ├── SessionActionsMenu  ← 右键菜单（重命名、删除、归档）
│   └── VirtualSessionList  ← @tanstack/react-virtual
│
├── ChatThread              ← 消息线程
│   ├── VirtualizedThread   ← 虚拟滚动
│   ├── ThreadMessage       ← 单条消息
│   │   ├── UserMessageText       ← 用户消息
│   │   ├── MarkdownText          ← AI 消息 (markdown 渲染 + LaTeX)
│   │   ├── DirectiveContent      ← 指令文本 (@ref, /commands)
│   │   ├── ToolFallback          ← 工具调用卡片
│   │   ├── ToolApproval          ← 工具审批交互
│   │   ├── ClarifyTool           ← 澄清请求
│   │   └── TodoTool/HoistedTodoPanel ← 待办事项
│   └── ThreadLoadingIndicator
│
├── ChatBar (Composer)      ← 输入框
│   ├── RichEditor          ← contenteditable (富文本编辑器)
│   ├── AttachmentList      ← 附件列表
│   ├── ComposerControls    ← 发送/语音
│   ├── QueuePanel          ← 队列面板
│   ├── HelpHint            ← 快捷键提示
│   └── TriggerPopover      ← @ 和 / 补全
│
├── ChatPreviewRail         ← 右侧预览栏
│   ├── PreviewPane         ← 文件/控制台预览
│   └── PreviewFile         ← 文件内容渲染
│
├── ChatDropOverlay         ← 拖放上传
└── ChatSwapOverlay         ← 会话切换
```

#### SettingsView — 设置面板 (8 个子页)

```
SettingsView
├── about-settings          ← 关于
├── appearance-settings     ← 外观 (主题)
├── model-settings          ← 模型配置
├── providers-settings      ← Provider 管理
├── keys-settings           ← API 密钥
├── sessions-settings       ← 会话管理
├── mcp-settings            ← MCP 配置
├── config-settings         ← 配置编辑器
├── gateway-settings        ← Gateway 配置
├── toolset-config-panel    ← 工具集配置
└── env-credentials         ← 环境变量/凭证
```

#### 其他视图

| 视图 | 用途 | 关键文件 |
|------|------|----------|
| AgentsView | 子 Agent 管理、任务流 | `agents/index.tsx` |
| BrowserWorkspace | 浏览器 workspace UI | `browser-workspace.tsx` |
| CronView | 定时任务管理 | `cron/index.tsx` |
| MessagingView | 消息平台管理 | `messaging/index.tsx` |
| SkillsView | 技能启停 | `skills/index.tsx` |
| ArtifactsView | 对话产物浏览 | `artifacts/index.tsx` |
| CommandCenterView | 命令中心 | `command-center/index.tsx` |
| ProfilesView | Profile 管理 | `profiles/index.tsx` |

### 3.5 组件库

| 层次 | 目录 | 说明 |
|------|------|------|
| **assistant-ui** | `components/assistant-ui/` | AI 聊天 UI（markdown, thread, tool, clarify） |
| **chat** | `components/chat/` | 聊天组件（code-card, diff, timer, intro） |
| **ui** | `components/ui/` | 基础 UI ~40 组件（button, dialog, select, sidebar, tabs 等） |
| **pane-shell** | `components/pane-shell/` | 面板布局系统 |

---

## 四、状态管理层 (NanoStores)

### 4.1 Store 目录 (~30 atom 文件)

| Store | 文件 | 用途 | 大小 |
|-------|------|------|------|
| **session** | `store/session.ts` | 会话/消息/连接状态 | 84 symbols |
| **layout** | `store/layout.ts` | 面板布局/尺寸/固定项 | 43 symbols |
| **boot** | `store/boot.ts` | 启动进度/错误 | 12 symbols |
| **composer** | `store/composer.ts` | 编辑器/附件 | 22 symbols |
| **composer-queue** | `store/composer-queue.ts` | 消息队列 | 24 symbols |
| **preview** | `store/preview.ts` | 文件/控制台预览 | 50 symbols |
| **panes** | `store/panes.ts` | 面板开关/宽度 | 22 symbols |
| **profile** | `store/profile.ts` | Profile 管理 | 37 symbols |
| **gateway** | `store/gateway.ts` | Gateway 状态 | 34 symbols |
| **onboarding** | `store/onboarding.ts` | 新手引导 | 64 symbols |
| **updates** | `store/updates.ts` | 更新管理 | 35 symbols |
| **subagents** | `store/subagents.ts` | 子 Agent 状态 | 32 symbols |
| **notifications** | `store/notifications.ts` | 通知 | 19 symbols |
| **model-visibility** | `store/model-visibility.ts` | 模型可见性 | 16 symbols |
| **tool-view** | `store/tool-view.ts` | 工具视图 | 16 symbols |
| **+16 more** | ... | 活动/命令面板/输入历史/主题等 |

### 4.2 核心数据流

```
Backend Gateway (hermes_cli backend)
      │
      │ JSON-RPC over WebSocket
      ▼
Hermes API Client (hermes.ts)
  ├── listSessions()            → $sessions atom
  ├── getSessionMessages()      → $messages atom
  ├── getStatus()               → connection state
  ├── getHermesConfig()         → settings state
  └── saveHermesConfig()        → write back
      │
      │ NanoStores subscribe/update
      ▼
React Components (auto-re-render on atom change)
```

### 4.3 关键 Hook

| Hook | 位置 | 用途 |
|------|------|------|
| `useGatewayBoot` | `gateway/hooks/` | 网关启动流程 |
| `useMessageStream` | `session/hooks/` | 消息流接收 |
| `usePromptActions` | `session/hooks/` | 消息发送/粘贴 |
| `useSessionActions` | `session/hooks/` | 会话 CRUD |
| `useComposerActions` | `chat/hooks/` | 编辑器操作 |
| `useRouteResume` | `session/hooks/` | 路由恢复会话 |
| `usePreviewRouting` | `session/hooks/` | 预览路由 |
| `useModelControls` | `session/hooks/` | 模型选择 |
| `useCwdActions` | `session/hooks/` | 工作目录 |
| `useHermesConfig` | `session/hooks/` | 配置读取 |
| `useOverlayRouting` | `shell/hooks/` | Overlay 路由 |
| `useStatusSnapshot` | `shell/hooks/` | 状态快照 |
| `useStatusbarItems` | `shell/hooks/` | 状态栏项 |

---

## 五、API 通信层 (`hermes.ts`)

### 5.1 通信机制

```
渲染进程                   主进程                   后端
  │                        │                       │
  │── ipc.invoke('hermes:api', request) ──→       │
  │                        │── HTTP → hermes backend
  │                        │←── response ────────│
  │←── IPC response ──────│                       │
```

- 使用 `@hermes/shared` 的 `JsonRpcGatewayClient`
- 通用代理模式：`ipcMain.handle('hermes:api')` 统一代理 HTTP 请求到 backend
- 默认超时：30 秒

### 5.2 API 函数 (~40 个)

| 类别 | 函数 |
|------|------|
| **会话** | `listSessions`, `searchSessions`, `getSessionMessages`, `deleteSession`, `renameSession`, `setSessionArchived` |
| **状态** | `getStatus`, `getLogs` |
| **配置** | `getHermesConfig`, `saveHermesConfig`, `getHermesConfigDefaults`, `getHermesConfigSchema` |
| **环境变量** | `getEnvVars`, `setEnvVar`, `deleteEnvVar`, `revealEnvVar` |
| **Provider** | `validateProviderCredential` |
| **OAuth** | `listOAuthProviders`, `startOAuthLogin`, `submitOAuthCode`, `pollOAuthSession`, `cancelOAuthSession` |
| **技能** | `getSkills`, `toggleSkill` |
| **Agent** | `getAgentRoster` |
| **工具** | `getToolsets` |
| **模型** | `getGlobalModelInfo`, `getGlobalModelOptions` |
| **分析** | `getAnalytics` |
| **音频** | `getElevenLabsVoices`, `speakText`, `transcribeAudio` |
| **Profile** | `getProfiles`, `createProfile`, `setupProfile`, `deleteProfile` |

---

## 六、内嵌浏览器架构

```
React 渲染进程                          Electron 主进程
  │                                       │
  │── ipc('hermes:browser:mount') ──────→ │── 创建 BrowserView 实例
  │── ipc('hermes:browser:navigate') ───→ │── webContents.loadURL()
  │── ipc('hermes:browser:get-state') ──→ │── 获取 URL/title/canGoBack
  │── ipc('hermes:browser:get-screenshot')→│── webContents.capturePage()
  │── ipc('hermes:browser:type-text') ──→ │── input.dispatchEvent()
  │                                       │
  │  DesktopBrowserBridge (Provider)       │
  │  ├── CuaVisibleBrowserProvider        │
  │  ├── DesktopVisibleBrowserProvider    │
  │  └── action-gateway-ui (approval)     │
```

两种 Provider:
- **CuaVisibleBrowserProvider**: 远程浏览器使用 (Computer Use Agent)
- **DesktopVisibleBrowserProvider**: 本地 Electron BrowserView (桌面内嵌)

---

## 七、主题系统

| 文件 | 用途 |
|------|------|
| `themes/types.ts` | `DesktopTheme` 接口定义 |
| `themes/presets.ts` | 内置主题（nous, midnight 等） |
| `themes/context.tsx` | ThemeProvider + CSS 变量注入 |
| `themes/use-skin-command.ts` | 主题切换命令 |

---

## 八、关键文件索引

| 想找什么 | 文件 |
|----------|------|
| Electron 主进程 | `electron/main.cjs` |
| Electron preload | `electron/preload.cjs` |
| 前端入口 | `src/main.tsx` |
| 主应用组件 | `src/app/desktop-controller.tsx` |
| 路由定义 | `src/app/routes.ts` (10 路由) |
| 聊天界面 | `src/app/chat/index.tsx` |
| 编辑器组件 | `src/app/chat/composer/index.tsx` |
| 消息线程 UI | `src/components/assistant-ui/thread.tsx` |
| App Shell | `src/app/shell/app-shell.tsx` |
| 状态管理 | `src/store/*.ts` (~30 files) |
| API 客户端 | `src/hermes.ts` (~40 函数) |
| 全局类型 | `src/types/hermes.ts` |
| IPC Handlers | `electron/main.cjs` (65 handlers) |
| 后端引导 | `electron/bootstrap-runner.cjs` |
| 浏览器桥接 | `electron/browser-session.cjs` |
| 终端管理 | `electron/terminal-shell.cjs` |
| 连接配置 | `electron/connection-config.cjs` |
| 安全加固 | `electron/hardening.cjs` |
| 主题预设 | `src/themes/presets.ts` |
| 构建 stamp | `scripts/write-build-stamp.cjs` |
