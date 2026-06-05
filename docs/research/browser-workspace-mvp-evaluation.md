# Hermes Browser Workspace MVP Evaluation

Date: 2026-06-05 (revised 2026-06-06)
Status: Read-only research/design note
Scope: No code change. No runtime/config change. No dependency decision.

## Revision Note

This document has been revised from an earlier version that prioritized external
real-browser adapter integration (mcp-chrome, webpage-mcp, BrowserMCP). The
revised direction is **embedded Hermes Browser Workspace first, external browser
adapter as fallback**. See the Embedded vs External Decision section for the
rationale.

## Executive Summary

Hermes Browser Workspace should be **an embedded, persistent browser surface
inside Hermes itself**, not a connector to an external user browser. Design
reference: Orion — light, fast, clean, extensible.

The core product goal is:

```text
User and Agent share the same browser workspace.
```

For Hermes, the useful primitive is a **local, embedded browser context
provider** that keeps login state, inherits system proxy, supports multiple
tabs, and exposes what is visible on the page to the Agent. External browser
adapters remain as a fallback path for users who prefer their own Chrome, but
the primary design and MVP investment targets the embedded workspace.

Recommended direction:

1. Keep Hermes Desktop as an Agent Coding Workbench.
2. Build Browser Workspace as an embedded browser surface (Electron WebContents
   or equivalent), persisted across sessions.
3. Expose browser context via a `BrowserContextProvider` interface so Hermes is
   not tied to a single rendering engine or adapter.
4. For MVP, only support read-only browser observation by the Agent.
5. Treat page control as a later approval-gated capability.
6. Build a Hermes-native plugin layer for context enrichment (GitHub PR, Vercel
   logs, Linear issues, ChatGPT/Claude conversations) rather than depending on
   Chrome Web Store extensions.

## Embedded vs External Decision

### Why embedded-first now

| Factor | Embedded | External (mcp-chrome etc.) |
|---|---|---|
| Connection stability | Full control over lifecycle | Depends on Chrome remote debugging, which is fragile across restarts |
| Login persistence | Hermes-owned profile directory, survives across sessions | Depends on user's Chrome profile, which may be cleared or locked |
| System proxy | Inherits from Electron/Chromium, trivially configured | Depends on Chrome's own proxy settings, not always consistent |
| Multi-tab isolation | Guaranteed, same process tree | Depends on extension API stability |
| Screenshot / DOM / selection | Direct WebContents API, zero overhead | Extension message-passing roundtrip |
| Clipboard access | Direct, synchronous | Extension permission model varies by OS |
| Agent read-only enforcement | Built into the provider boundary, not dependent on extension tool allowlist | Extension tool surface must be externally restricted |
| Plugin layer | Hermes-native, can inject context enrichers directly | Must use Chrome extension APIs or external scripting |

### Why external adapters remain as fallback

- Some users have deeply customized Chrome profiles (extensions, bookmarks,
  password managers) that are impractical to replicate.
- Some enterprise environments require specific browser versions or security
  configurations.
- External adapters can serve as a migration path for users who are not yet
  ready to trust an embedded browser with their credentials.

The fallback path should be:

```text
Hermes Embedded Browser (primary)
  ↓ if user preference or enterprise policy requires external
mcp-chrome / BrowserMCP adapter (fallback)
```

This document still evaluates external candidates for reference, but they are
no longer the primary MVP path.

## Existing Hermes Boundary

Existing accepted desktop direction:

```text
Chat -> Agent Run -> Timeline -> Changed Files -> Review -> Continue / Retry / Accept / Done
```

Browser Workspace must preserve this main line.

Correct placement:

```text
Hermes Desktop
  = Agent Control Plane / Agent Coding Workbench

Browser Workspace
  = Embedded Shared Web Context Provider
```

Do not make the browser the first screen. The first screen should remain Chat.
Browser context belongs in the right rail or prompt context selector.

## Design Reference: Orion

Orion (by Kagi) is the design reference for the embedded browser experience:

- Lightweight, fast, native-feeling WebKit/Chromium surface.
- Clean chrome, minimal UI clutter.
- Persistent profiles with login state.
- Extensible via a native plugin/extension layer.
- Not a browser-shell product — it is a focused web workspace.

Hermes Browser Workspace should aim for a similar feel: a clean, persistent web
surface that the user and Agent both use, not a general-purpose browser.

## Problem Statement

The user often works in browser-based tools:

- ChatGPT
- Claude
- GitHub
- Vercel
- Linear
- Feishu

Today those activities happen outside Hermes. The user knows what they are
looking at, but the Agent does not. External browser adapters introduce
connection fragility and profile conflicts. An embedded browser provides a
stable, shared workspace.

Browser Workspace should close that gap by making the current browser state
available as structured context, from a browser surface that Hermes owns.

## Product Non-goals

MVP must not include:

- Agent auto-clicking pages.
- Agent auto-typing into pages.
- Agent auto-submitting forms.
- Agent auto-sending ChatGPT/Claude messages.
- Agent auto-merging PRs.
- Agent auto-deploying or changing production resources.
- Replacing the desktop workbench with a browser-first shell.
- Building a VPN/proxy layer inside Hermes.
- Rebuilding a full browser distribution (Chromium/Electron built-in is sufficient).
- Compatibility with Chrome Web Store extensions in MVP.

## MVP User Scenarios

### Scenario 1: GitHub PR

User opens a GitHub PR in the embedded browser. Hermes should know:

- Current URL.
- Page title.
- Page type: GitHub Pull Request (via Hermes-native plugin).
- PR title if available (via plugin parsing).
- Selected text if any.
- A readable page summary.
- Screenshot reference.

Agent can answer:

```text
Summarize the current PR.
Explain the risk in the selected diff.
Draft a review comment based on the current page.
```

### Scenario 2: Vercel Deployment Failure

User opens a Vercel deployment or build log page. Hermes should know:

- Deployment URL.
- Page title.
- Selected log text.
- Clipboard text if the user copied an error.
- Screenshot reference.
- DOM/readable text summary.

Agent can answer:

```text
Analyze the build failure I am looking at.
Turn the copied error log into a fix plan.
```

### Scenario 3: Linear Issue

User opens a Linear issue. Hermes should know:

- URL and title.
- Issue-like page type.
- Visible task description summary.
- Selected text.

Agent can answer:

```text
Turn the current Linear issue into a Hermes task.
```

### Scenario 4: ChatGPT Web Session

User uses ChatGPT Plus web UI without API access. Hermes should know:

- Current ChatGPT page URL/title.
- Conversation text summary where technically available.
- Selected text.
- Clipboard text.
- Screenshot reference.

Agent can answer:

```text
Help me write the next prompt for this ChatGPT conversation.
Summarize what is happening in this thread.
```

MVP should not auto-send the next prompt.

### Scenario 5: Claude Web Session

Same as ChatGPT:

- Understand current page context.
- Help draft next prompt.
- Do not auto-send.

## MVP Acceptance Matrix

The MVP should be judged by whether it can reliably produce these fields from
the embedded browser:

| Capability | Required For MVP | Notes |
|---|---:|---|
| Current active tab URL | Yes | Basic identity of user context |
| Current active tab title | Yes | Human-readable context |
| Window/tab list | Yes | Needed for explicit tab selection |
| Recent browsing history | Yes | Useful context trail, scoped to this workspace |
| Screenshot | Yes | Needed for visual/debug pages |
| Readable page text / DOM summary | Yes | Core Agent context |
| Selected text | Yes | High-value user intent signal |
| Clipboard text snippet | Yes | High-value error-log workflow |
| Page type detection | Yes | Start with Hermes-native plugins, fall back to URL rules |
| Persistent browser profile | Yes | Survives app restart |
| Login state persistence | Yes | No re-login on restart |
| System proxy inheritance | Yes | Electron built-in |
| Console logs | Nice to have | Useful for web debugging |
| Network logs | Nice to have | Useful for Vercel/GitHub/API debugging |
| Cross-tab semantic search | Later | Useful but not MVP-critical |
| Click/type/navigate | No | Later approval-gated control |
| Form submission | No | Later approval-gated control |
| Chrome Web Store extension support | No | Hermes-native plugin layer instead |

## MVP Validation

Before declaring the embedded browser MVP ready, the following must be
verified on a real Hermes build:

| Validation | Required | Notes |
|---|---|---|
| ChatGPT can log in and login persists across app restart | Yes | Critical: proves profile and cookie persistence |
| Claude can log in and login persists across app restart | Yes | Same as above |
| GitHub can log in and login persists across app restart | Yes | Core development workflow surface |
| Vercel can log in and login persists across app restart | Yes | Core deployment workflow surface |
| System proxy is used by the embedded browser | Yes | Must work in corporate environments |
| Screenshot produces a valid image from the embedded browser | Yes | `webContents.capturePage()` or equivalent |
| DOM summary is readable and under a size cap | Yes | Must not inject megabytes of DOM into prompt |
| Selected text is accurately captured | Yes | Critical Agent context signal |
| Clipboard snippet is available when user copies text | Yes | Critical error-log workflow |
| Agent cannot trigger click/type/submit/navigate | Yes | Read-only enforcement must be verified at the provider boundary |
| Tabs survive app restart | Yes | Profile persistence |
| Multiple tabs work independently | Yes | Tab isolation |
| Hermes-native plugin matches at least one supported page type | Yes | Plugin interface validation |
| Browser context can be explicitly inserted into a prompt | Yes | Prompt integration validation |

Fail condition: any of the "Yes" validations fails.

## Hermes-native Plugin Layer

External browser adapters depend on Chrome Web Store extensions for context
enrichment. The embedded browser should use a Hermes-native plugin layer
instead.

### MVP Plugin Targets

| Plugin | Page Pattern | What It Provides |
|---|---|---|
| GitHub PR | `github.com/*/pull/*` | PR title, author, base/head branch, file list, CI status |
| Vercel Log/Deployment | `vercel.com/*` | Deployment status, build log text, error extraction |
| Linear Issue | `linear.app/*` | Issue title, description, assignee, status, labels |
| ChatGPT Conversation | `chatgpt.com/*`, `chat.openai.com/*` | Conversation title, message list summary, selected message |
| Claude Conversation | `claude.ai/*` | Conversation title, message list summary, selected message |

### Plugin Interface

Plugins are registered by URL pattern and expose a simple interface:

```text
activate(tab: TabInfo) -> boolean       // does this plugin apply to this tab?
extract(tab: TabInfo) -> PageContext     // extract structured context
```

A plugin should be a small TypeScript/JS module, not a Chrome extension
manifest. The plugin layer is built into the Hermes renderer process and
has direct access to the embedded browser's WebContents.

### Plugin Precedence

1. If a registered plugin matches the current page URL, use its structured
   output as the primary page context.
2. If no plugin matches, fall back to the generic DOM summary + URL-based
   page type heuristics.
3. Plugins are Hermes-native; Chrome Web Store extensions are not loaded.

## Recommended MVP Architecture

### Primary: Embedded Browser Workspace

```text
Hermes Agent Workbench
  -> Browser Workspace Service
    -> Embedded Browser (Electron WebContents / Chromium)
      -> Persistent profile directory (~/.hermes/browser/)
      -> System proxy inheritance
      -> Multi-tab management
      -> Screenshot / DOM / Selection / Clipboard capture
    -> Plugin Layer (Hermes-native)
      -> GitHub PR plugin
      -> Vercel Log plugin
      -> Linear Issue plugin
      -> ChatGPT Conversation plugin
      -> Claude Conversation plugin
    -> BrowserContextProvider interface
      -> Read-only access boundary
```

### Fallback: External Browser Adapters

When the embedded browser cannot be used (user preference, enterprise policy,
specialized profile requirements):

```text
Hermes Agent Workbench
  -> Browser Context Service
    -> BrowserContextProvider interface
      -> mcp-chrome adapter (fallback)
      -> BrowserMCP adapter (fallback)
      -> webpage-mcp adapter (fallback)
```

### Read-only Provider Interface

Initial provider methods (same for embedded and external adapters):

```text
get_current_context()
get_windows_and_tabs()
get_recent_history(limit, since)
get_screenshot(tab_id)
get_dom_summary(tab_id)
get_selected_text(tab_id)
get_clipboard_snippet()
get_recent_browser_events(limit)
```

Explicitly excluded from MVP provider:

```text
navigate()
switch_tab()
click()
type()
submit()
inject_script()
close_tab()
bookmark_add()
bookmark_delete()
```

### Snapshot Shape

Proposed Hermes-owned shape:

```json
{
  "captured_at": "2026-06-05T00:00:00+08:00",
  "source": {
    "provider": "hermes-embedded-browser",
    "mode": "read_only"
  },
  "active_tab": {
    "id": "tab-123",
    "window_id": "window-1",
    "url": "https://github.com/org/repo/pull/123",
    "title": "Fix memory leak",
    "page_type": "github_pull_request",
    "plugin_match": "github-pr",
    "selected_text": "",
    "clipboard_text_preview": "",
    "dom_summary": "",
    "screenshot_ref": ""
  },
  "tabs": [
    {
      "id": "tab-123",
      "url": "https://github.com/org/repo/pull/123",
      "title": "Fix memory leak",
      "active": true
    }
  ],
  "recent_history": [],
  "recent_events": []
}
```

### Page Type Detection

Start with deterministic rules as fallback when no plugin matches:

| Page Type | Rule |
|---|---|
| `github_pull_request` | Host is `github.com` and path contains `/pull/` |
| `github_issue` | Host is `github.com` and path contains `/issues/` |
| `vercel_deployment` | Host contains `vercel.com` and page title/path suggests deployment/build/log |
| `linear_issue` | Host contains `linear.app` and page text/title matches issue shape |
| `chatgpt_conversation` | Host contains `chatgpt.com` or `chat.openai.com` |
| `claude_conversation` | Host contains `claude.ai` |
| `feishu_doc` | Host contains `feishu.cn`, `larksuite.com`, or configured tenant domain |

Plugins take precedence over rules. Avoid LLM-only page classification in MVP.

## Desktop UI Placement

Browser Workspace should appear as a right-rail tab:

```text
Right Rail
  Files
  Diff
  Logs
  Artifacts
  Browser
```

Browser tab should show:

- Current page title.
- URL.
- Page type (with plugin indicator).
- Screenshot thumbnail.
- Selected text.
- Clipboard preview.
- DOM/readable summary.
- Recent browser events.
- "Insert current page context" action.

It should not show:

- Full browser chrome as the primary view (the browser surface should be
  togglable, not replacing Chat).
- Auto-action buttons in MVP.
- Hidden browser automation state that the user cannot inspect.

## Prompt Integration

User-facing prompt affordances:

```text
Use current browser page
Use selected text
Use copied text
Use screenshot
Use recent browser history
```

Agent prompt injection should be explicit and scoped:

```text
Current browser context:
- URL:
- Title:
- Page type:
- Plugin:
- Selected text:
- Clipboard preview:
- DOM summary:
- Screenshot reference:
```

Do not silently inject full browser history or all tab content into every run.
Browser context can contain private information and should be opt-in per
task/run until explicit policy exists.

## Permission Model

### Level 1: Observe

Agent can read selected browser context.

Allowed:

- Active tab URL/title.
- Selected text.
- Screenshot.
- DOM summary.
- Recent history when user enables it.
- Clipboard snippet when user enables it.

MVP target. Enforced at the `BrowserContextProvider` boundary.

### Level 2: Suggest

Agent can propose browser operations.

Allowed:

- "Click this button."
- "Copy this selector."
- "Open this deployment log."

User performs action manually.

Post-MVP.

### Level 3: Act With Approval

Agent can execute browser operations after Hermes approval.

Allowed only with explicit confirmation:

- Click.
- Type.
- Navigate.
- Submit.
- Download.
- Upload.

Post-MVP and must reuse Hermes approval/review gate.

### Level 4: Autonomous Browser Workflow

Out of scope until a separate safety decision.

## Security And Privacy Notes

Browser context is sensitive because it may include:

- Logged-in SaaS pages.
- Tokens in URLs.
- Private chats.
- Internal build logs.
- Customer/user data.
- Browser history.
- Clipboard contents.

MVP should apply these rules:

1. Read-only by default. No Agent-initiated browser actions.
2. No silent capture of all tabs.
3. No silent injection of browser context into every Agent run.
4. Clip DOM summaries by size.
5. Redact obvious secrets from URLs and text previews.
6. Store screenshots only with explicit task/run association.
7. Treat clipboard as a user-intent signal but still require visibility in UI.
8. No browser action tool enabled without approval gate.
9. Embedded browser profile stored under `~/.hermes/browser/`, isolated from
   the user's default system browser profile.

## External Candidate Evaluation (Fallback Reference)

The following external projects were evaluated as potential fallback adapters.
They are **not** the primary MVP path, but are documented here for future
reference if the embedded browser path is unavailable for a specific deployment.

### 1. hangwin/mcp-chrome

Repository: https://github.com/hangwin/mcp-chrome

Fit: Strong as a fallback adapter.

Why it matters:

- Chrome extension-based MCP server.
- Directly uses the user's daily Chrome browser.
- Explicitly claims reuse of existing configurations and login states.
- Fully local MCP server.
- Supports cross-tab context.
- Exposes screenshots, network monitoring, web content extraction, interactive elements, console output, history, and bookmarks.

How Hermes would use it as fallback:

- As a candidate `BrowserContextProvider` backend.
- Initially whitelist only read tools.
- Keep interaction tools disabled in MVP.

Risk for primary path:

- Product center is "AI take control of your browser", while Hermes MVP is
  "Agent observes browser context".
- External connection fragility across Chrome restarts.
- Chrome remote debugging hardening makes stable connection difficult.

Verdict: Primary fallback adapter. Not the embedded MVP path.

### 2. mcpland/webpage-mcp

Repository: https://github.com/mcpland/webpage-mcp

Fit: Secondary fallback.

Why it matters:

- Uses Chrome extension platform and native APIs.
- Uses native messaging plus stdio rather than localhost HTTP.
- Based on `hangwin/mcp-chrome`.

Risk:

- Much smaller ecosystem.
- Needs local installation validation.

Verdict: Secondary fallback if mcp-chrome has a blocking gap.

### 3. BrowserMCP/mcp

Repository: https://github.com/BrowserMCP/mcp

Fit: Conceptually strong, engineering risk high.

Why it matters:

- MCP server plus Chrome extension.
- Uses the user's existing browser profile.

Important limitation:

- Repository currently cannot be built on its own due to monorepo dependencies.

Verdict: Good reference, weak dependency. Tertiary fallback.

### 4. browser-use

Repository: https://github.com/browser-use/browser-use

Fit: Partial. Automation reference only.

Why it is not a fit for Hermes MVP:

- Core model is Agent operates a browser, not shared browser context.
- Existing Chrome profile reuse can run into profile locks.
- Better as an automation framework reference.

Verdict: Reference for action schemas only.

### 5. microsoft/playwright-mcp

Repository: https://github.com/microsoft/playwright-mcp

Fit: Partial. Schema and accessibility snapshot reference.

Why it is not a fit:

- Playwright-based flows typically launch or own a browser context.
- Fights the goal of a shared, persistent browser workspace.

Verdict: Schema and automation reference only.

### 6. ChromeDevTools/chrome-devtools-mcp

Repository: https://github.com/ChromeDevTools/chrome-devtools-mcp

Fit: Debugging reference.

Why it is not a fit:

- Connecting to a running Chrome instance is complicated by remote debugging
  hardening.
- Better suited to debugging than shared browser workspace.

Verdict: Useful later for deep debugging surfaces.

### 7. nanobrowser

Repository: https://github.com/nanobrowser/nanobrowser

Fit: Product interaction reference only.

Why it is not a fit:

- Product goal is closer to an AI browser Operator.
- Hermes does not need another browser-side task/chat product.

Verdict: Reference for in-browser UX concepts.

### 8. Stagehand / Skyvern

Fit: Low.

- They optimize for web automation/RPA rather than shared browser context.

Verdict: Do not spend MVP time here.

## Recommended Next Step

Do not implement yet.

Next step should be a local, disposable PoC of the embedded browser surface:

1. Create a minimal Electron `BrowserView` or `webview` with a persistent
   profile under `~/.hermes/browser/`.
2. Open real logged-in pages: GitHub, ChatGPT, Claude, Vercel, Linear.
3. Verify login state persists across app restart.
4. Verify system proxy is inherited.
5. Verify screenshot, DOM summary, selected text, and clipboard capture.
6. Build one sample plugin (GitHub PR) to validate the plugin interface.
7. Record exact outputs in a follow-up evidence document.

Only after that should Hermes integrate the Browser Workspace into the right
rail and prompt context system.

The external adapter fallback path should be validated only if the embedded
browser PoC has a blocking gap.

## Source Links Checked

- `hangwin/mcp-chrome`: https://github.com/hangwin/mcp-chrome
- `mcpland/webpage-mcp`: https://github.com/mcpland/webpage-mcp
- `BrowserMCP/mcp`: https://github.com/BrowserMCP/mcp
- `browser-use/browser-use`: https://github.com/browser-use/browser-use
- `microsoft/playwright-mcp`: https://github.com/microsoft/playwright-mcp
- `ChromeDevTools/chrome-devtools-mcp`: https://github.com/ChromeDevTools/chrome-devtools-mcp
- `nanobrowser/nanobrowser`: https://github.com/nanobrowser/nanobrowser
- Orion Browser (design reference): https://kagi.com/orion/
