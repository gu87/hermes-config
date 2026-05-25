---
name: browser-automation-for-blocked-sites
description: Automate browser-based tasks on sites that block curl/terminal API calls
  using Chrome DevTools Protocol (CDP) with stealth considerations.
triggers:
- site blocks curl with 405/WAF
- need to maintain browser session (cookies, localStorage)
- website has bot detection that resists CDP clicks
- HS512 vs HS256 JWT token difference (browser vs curl auth)
- Google/ddg-search blocked from terminal (network timeout, 408, empty results)
- need structured news search results from cron job / automated research
agents:
- agent-tars
---

# Browser Automation for Sites That Block Curl

## Core Problem
Many modern websites block direct API calls from curl/terminal (WAF, bot detection, token algorithm differences). Browser automation via CDP becomes necessary.

## Workflow

### Step 1 — Diagnose: Is Curl Blocked?
```bash
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt \
  -X POST 'https://target-site.com/api/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username":"USER","password":"PASS"}' \
  -w '\nHTTP_STATUS:%{http_code}'
```
If 405 (Alibaba Cloud WAF), 403, or token issues → go to browser.

### Step 2 — Launch Stealth Chrome with CDP
```bash
open -n "/Applications/Google Chrome.app" --args \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-hermes
```
**Note:** This runs WITHOUT residential proxies. Stealth warning will appear: `"Running WITHOUT residential proxies. Bot detection may be more aggressive."` This is expected but means some sites will resist automation.

### Step 3 — Navigate and Observe
Use `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`. For sites that resist CDP clicks:
- Try `browser_console` JS injection for clicks: `element.click()` 
- Try `browser_evaluate` for form fills

### Step 4 — Browser Console Login (When Curl Blocked)
Sites that return `{"code":500,"msg":"错误的登录类型"}` for password login via curl often work from browser console:
```js
fetch('/api/auth/login', {
  method: 'POST',
  body: JSON.stringify({username: 'USER', password: 'PASS', loginType: 'password'}),
  credentials: 'include'
}).then(r => r.json()).then(d => window._loginResult = d);
```
**Key:** Do NOT set `Content-Type: application/json` explicitly in fetch — let browser set it automatically. Explicit Content-Type causes "Content type 'text/plain;charset=UTF-8' not supported".

### Step 5 — Session Cookie vs localStorage
- Browser `fetch` with `credentials:'include'` returns JWT but may NOT set cookie
- Check: `localStorage` and `sessionStorage` for tokens
- If cookie-based session needed: use CDP to fill form and submit (browser sets cookies naturally)
- Chrome cookies on Mac are encrypted (Chromium safe storage) — cannot read from sqlite directly

### Step 6 — Tab Interface Clicks Not Registering
If a tab/checkbox click via CDP `browser_click` doesn't visually register:
- The site may be detecting CDP automation
- Try JS click: `document.querySelector('selector').click()` via `browser_console`
- If JS clicks also don't work → manual login required once, then use that session

## Token Type Difference (Critical)
- **Browser context**: HS512 JWT (500+ chars, starts `eyJh...`)
- **Curl context**: HS256 JWT (334 chars, starts `eyJh...`)
- These are DIFFERENT token types. Browser token needed for website operations.
- Verify token type by calling login API from both curl and browser console.

## Fallback: Manual Login Once
If all automation fails: user manually logs in browser once → session cookie set → future CDP calls work with that session.

## Chrome CDP on Mac — Understanding the Options

**Verdict: Any Chrome variant CAN work with CDP, if started with `--remote-debugging-port=9222`.**
The real distinction is whether Chrome was **launched** with that flag, not the profile type.

| Chrome Variant | CDP Works? | How |
|---------------|-----------|-----|
| Regular Chrome, new profile | ✅ | Start with `--remote-debugging-port=9222 --user-data-dir=...` |
| Regular Chrome, **default real profile** | ✅ | Quit Chrome → restart with `--remote-debugging-port=9222` (user's tabs restore) |
| Chrome for Testing (headless) | ✅ | Start with `--remote-debugging-port=9222 --headless` |
| Regular Chrome, **headless=new** | ✅ | Start with `--remote-debugging-port=9222 --headless=new` — works as well as Chrome for Testing |

### 🚨 Critical missing flag: `--remote-allow-origins=*`

**This flag is MANDATORY on Chrome v135+.** Without it, CDP HTTP endpoints respond fine but WebSocket connections get 403.

### CDP with User's Real Chrome Profile (Symlink Workaround)

Chrome requires `--user-data-dir` to point to a **non-default** path for CDP to work. Directly passing the real profile path fails with:
```
DevTools remote debugging requires a non-default data directory.
```

**Solution — symlink the Default profile to a new directory:**
```bash
mkdir -p ~/.chrome-cdp
ln -sfn "$HOME/Library/Application Support/Google/Chrome/Default" ~/.chrome-cdp/Default

# Then start Chrome with CDP
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --user-data-dir="$HOME/.chrome-cdp" \
  --no-first-run --no-default-browser-check
```

This preserves:
- ✅ All extensions (Tampermonkey, etc.)
- ✅ Bookmarks and history
- ⚠️ Login cookies may NOT transfer (bound to original profile path) — user may need to re-login to target sites

**Important:** The error `DevTools remote debugging requires a non-default data directory` means the path passed to `--user-data-dir` IS the default Chrome data dir. The symlink creates a different filesystem path while pointing to the same Default profile content.

### 🔄 Fallback: Fresh Temp Profile When Symlink Fails

If even the symlink approach fails (and/or you need a clean environment):
DevTools remote debugging requires a non-default data directory.
```
This appears even when `--user-data-dir` is explicitly set to the real profile path. Even a **symlink workaround** (`ln -s ... /tmp/chrome-real-profile`) fails — Chrome detects the same underlying directory. The root cause is unknown; only a truly fresh temp directory works.

**Workaround attempts that failed (historical — symlink now works):**
1. `--user-data-dir="/Users/gu/Library/Application Support/Google/Chrome"` → same error
2. Symlink: `ln -s "..." /tmp/chrome-real-profile` → Chrome detects it's the same dir
3. `open -a "Google Chrome" --args --remote-debugging-port=9222` → Chrome opens but CDP never binds
4. Passing flags through both `terminal(background=true)` and `subprocess.Popen` → same result

**Solution**: Use a fresh temp profile (or the symlink approach above):
```bash
rm -rf /tmp/chrome-cdp-profile
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --user-data-dir=/tmp/chrome-cdp-profile \
  --no-first-run --no-default-browser-check
```
CDP is ready within **2-3 seconds** with a fresh profile.

**Tradeoffs:**
| User Profile (symlink via ~/.chrome-cdp) | Fresh Temp Profile |
|---|---|
| ✅ User's extensions (Tampermonkey etc.) preserved | ❌ No extensions → must install |
| ✅ Bookmarks, history, settings all backed up | ✅ Clean, predictable state |
| ⚠️ Login sessions may need re-authentication | ❌ No login state → must login fresh |
| ⚠️ Reliable — symlink approach works | ✅ Always works |

**⚠️ Extension installation persistence (Chrome crash recovery):**
If Chrome is killed/crashes during extension installation from Chrome Web Store, the extension directory is created but NOT registered in Preferences. To fix:
```python
import json, os
with open('/tmp/chrome-cdp-profile/Default/Preferences') as f:
    d = json.load(f)

ext_id = 'dhdgffkkebhmkfjojejmpbldmpobfkfo'  # Tampermonkey ID
tm_dir = f'/tmp/chrome-cdp-profile/Default/Extensions/{ext_id}'
version = os.listdir(tm_dir)[0]

ext_settings = {
    ext_id: {
        "active_permissions": {"api": ["management", "storage", "unlimitedStorage"],
                               "explicit_host": ["http://*/*", "https://*/*"],
                               "manifest": ["activeTab", "storage"]},
        "from_webstore": True,
        "location": 0,
        "path": f"{ext_id}/{version}",
        "state": 1,  # enabled
        "was_installed_by_default": False,
        "was_installed_by_oem": False
    }
}
d.setdefault('extensions', {}).setdefault('settings', {}).update(ext_settings)
with open('/tmp/chrome-cdp-profile/Default/Preferences', 'w') as f:
    json.dump(d, f)
```

**When to prefer fresh profile:**
- When real profile CDP keeps failing (especially on Gu's Mac)
- For extension installation (Tampermonkey, Greasyfork scripts)
- For simple browse-and-navigate tasks (documentation, store pages)
- Any task where user login session isn't strictly needed

**When to prefer user's real profile:**
- Logged-in sessions only if CDP works with it
- If CDP fails with real profile on this Mac, use temp profile + login manually

Starting Chrome headless with only `--remote-debugging-port=9222` is NOT enough on modern Chrome (v135+). CDP HTTP endpoints (`/json/version`, `/json/list`) respond fine, but **WebSocket connections** are rejected with HTTP 403:

```
Rejected an incoming WebSocket connection from the http://localhost:9222 origin.
Use the command line flag --remote-allow-origins=http://localhost:9222 to allow
connections from this origin or --remote-allow-origins=* to allow all origins.
```

**Always include both flags together:**
```bash
--remote-debugging-port=9222 --remote-allow-origins=*
```

Without `--remote-allow-origins`, the Hermes browser tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_console`) will fail because they use WebSocket under the hood to communicate with CDP.

**⚠️ macOS profile handling: `terminal(background=true)` vs `subprocess.Popen`**

On macOS, how you start Chrome affects which profile it loads:

| Launch Method | Default Profile Used | Login Cookies Carry Over? |
|--------------|---------------------|--------------------------|
| `terminal(background=true)` with no `--user-data-dir` | Headless default profile (separate from user's real Chrome) | ❌ No |
| Python `subprocess.Popen()` with no `--user-data-dir` | User's real default profile (`~/Library/Application Support/Google/Chrome/`) | ✅ Yes |
| `terminal(background=true)` with `--user-data-dir="~/.hermes/chrome-profile"` | Explicit profile dir | Only if previously authenticated in that dir |

This is because `terminal(background=true)` detaches from the user session, so Chrome doesn't know which profile to use. `subprocess.Popen` inherits the parent process environment and finds the correct profile.

**Workaround for persistent logged-in headless Chrome:** Start Chrome with `--headless=new` via Python `subprocess.Popen` (gets user profile), then keep it alive. Or, pre-authenticate in a `--user-data-dir` and restart via `terminal(background=true)`.

### Copying User's Login Session (Two Approaches)

**Approach A — Use User's Real Chrome with CDP (preferred for one-shot grabs):**
```bash
# 1. Ask user to quit Chrome
# 2. Restart Chrome with CDP using their default profile
terminal(background=true):
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --no-first-run --no-default-browser-check
# 3. Chrome restores their tabs including logged-in sessions
# 4. Connect via http://localhost:9222/json/version
```
- ✅ User's login sessions are preserved
- ✅ No need to re-authenticate
- ⚠️ User must quit Chrome briefly
- ⚠️ Chrome restores all tabs (may be slow if many tabs)

**Approach B — Chrome for Testing Headless (preferred for persistent cron tasks):**
- Use Chrome for Testing with `--headless --user-data-dir=~/.hermes/chrome-profile`
- Login once via `browser_navigate` → `browser_type` → `browser_click`
- Session persists across restarts in `--user-data-dir`
- Best for headless server/background cron jobs

### Why Regular Chrome `--remote-debugging-port` Might Seem to Fail
If the user already has Chrome open without CDP, typing the launch command silently fails because macOS opens a new window of the *existing* process (which ignores the flag). Solution: quit Chrome first, then launch with the flag.

### Fix: Use Chrome for Testing (Playwright)
```bash
# Install Chrome for Testing (one-time)
npx agent-browser install

# Or via playwright
npx playwright install chromium

# Installed to:
#   ~/.agent-browser/browsers/chrome-148.0.7778.97/   (agent-browser)
#   ~/Library/Caches/ms-playwright/chromium-1217/      (playwright)

# Start headless with CDP
terminal(background=true):
  "/Users/gu/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
    --remote-debugging-port=9222 \
    --headless --disable-gpu --no-sandbox \
    --no-first-run --no-default-browser-check \
    --user-data-dir="$HOME/.hermes/chrome-profile"

# Verify
lsof -i :9222     # should show LISTEN
curl http://localhost:9222/json/version  # should return JSON
```

### Config Fix: Set `browser.cdp_url`
```yaml
# ~/.hermes/config.yaml
browser:
  cdp_url: http://localhost:9222
```
This tells `browser_navigate`/`browser_click`/`browser_snapshot` to use the existing CDP endpoint instead of trying to auto-launch its own Chromium.

### Session Persistence
Chrome for Testing with `--user-data-dir` persists cookies/localStorage. To maintain a login session:
1. Start Chrome for Testing headless on port 9222
2. Login via `browser_navigate` → `browser_type` → `browser_click`
3. The session is saved in `~/.hermes/chrome-profile/`
4. As long as Chrome stays alive and CDP port stays up, the session persists
5. **Do NOT kill this Chrome process** between sessions

### Auto-launch vs CDP Override
When `browser.cdp_url` is empty (default):
- Hermes tries to auto-launch its own headless Chromium on port 9222
- Falls back to searching Playwright's installed browsers
- The `_chromium_installed()` check scans `~/Library/Caches/ms-playwright/chromium-*` directories
- If no Chromium found, `browser_navigate` fails with "Auto-launch failed" error

When `browser.cdp_url` is set:
- Hermes connects to the existing CDP endpoint directly
- Skips auto-launch entirely
- More reliable for persisted sessions

## Pitfalls

- **Xiaohongshu login: agreement popup is mandatory intermediate step**: Clicking navbar "登录" → agreement popup ("阅读并同意《用户协议》etc.") appears. You MUST click "同意并继续" BEFORE clicking "获取验证码". Without agreement acceptance, the SMS API (`/api/sns/web/v2/login/send_code`) never fires — button click silently does nothing. The verification flow is: login button → agree terms → phone input → get code (now works) → enter code → submit.
- **Stealth mode**: `--user-data-dir` reuse may help maintain session, but new browser instance is cleaner for debugging
- **WAF blocking curl**: Not just 403 — Alibaba Cloud returns 405 with HTML error page
- **Checkbox required**: Many login forms require agreement checkbox BEFORE login button works
- **Tab switching via CDP**: ARIA tab elements may not respond to CDP clicks; try JS injection
- **Empty accessibility tree**: Heavy JS sites (React/Vue) may produce accessibility trees with 10-20 elements while HTML is 800KB+. Always fall back to `TreeWalker` text extraction from browser console if `browser_snapshot` shows only header/nav elements
- **Wrong URL**: Always check the actual URL after navigation — redirects may send you somewhere unexpected (e.g., `/subscribe-pay` → `/login`). The correct URL for Zhipu AI purchase is `https://open.bigmodel.cn/coding-plan/personal/overview` — NOT `/subscribe-pay`
- **CDP WebSocket URLs are dynamic**: Never hardcode WebSocket debugger URLs from previous sessions. Always fetch via `http://localhost:9222/json` and filter by page URL. Third-party iframes (e.g., 客服 SDK at `qiyukf.com`) must be filtered out. **Avoid raw CDP WebSocket entirely** — use `browser_navigate`/`browser_click`/`browser_snapshot` MCP tools which handle this internally
- **Chrome must be pre-running with CDP**: The automation script cannot start Chrome itself while maintaining a logged-in session. Chrome for Testing must already be running with `--remote-debugging-port=9222 --headless` and a logged-in session before automation begins. Use `terminal(background=true)` to start it before any cron job fires.

## Flash Sale / Limited-Stock Grab Strategy

**Core insight: For popular flash sales, the target page becomes inaccessible ~5 minutes before the sale time due to traffic surge.** Navigating at `HH:59:50` is too late — the page 502s or hangs.

### Strategy: Early Page Occupation

1. **Navigate to the purchase page BEFORE the cutoff** (at least 10 minutes early):
   ```python
   # DO NOT wait until 59:50 — that's too late
   # Navigate at 09:40-09:45 for a 10:00 sale
   browser_navigate(url="https://target.com/buy")
   ```

2. **Keep the CDP WebSocket connection alive** with periodic pings:
   ```python
   # Every 25-30s, check page is still responsive
   browser_evaluate("document.title")
   ```

3. **At the exact sale time, execute rapid clicks** (multiple attempts in quick succession):
   - First millisecond: click purchase button via JS injection
   - 500ms later: click again (some pages show modal after first click)
   - 1s later: click confirm/pay button

4. **Fallback chain:**
   - Primary: CDP browser click (fastest, most reliable)
   - Secondary: API call (if purchase API is accessible)
   - Tertiary: Notify user to manually act

### ⚠️ Headless Chrome Rate Limiting

**Headless Chrome is often detected by flash sale sites**, resulting in "抢购人数过多，请刷新再试" or similar rate-limiting messages. The buttons remain `disabled=true` in the DOM, but JS injection can bypass the disabled state.

**If headless gets rate-limited:**
1. Kill headless Chrome
2. Start **non-headless** Chrome instead (omit `--headless`, `--headless=new`):
   ```bash
   terminal(background=true):
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
       --remote-debugging-port=9222 \
       --remote-allow-origins=* \
       --no-first-run --no-default-browser-check \
       --user-data-dir="/Users/gu/.hermes/chrome-profile" \
       "https://target.com/buy"
   ```
3. The non-headless window pops up on the user's screen — user may need to log in manually
4. After login, continue CDP automation via Hermes browser tools

**Rate limiting signals (DOM-level):**
- Button text changes from "立即订阅" / "购买" to "抢购人数过多，请刷新再试"
- Button becomes `disabled=true` even though sale hasn't started yet
- Same behavior across all tiers (Lite, Pro, Max all show same message)
- Refreshing the page doesn't clear it (server-side rate limit tied to IP/browser fingerprint)

**Workaround when JS `element.click()` fails on disabled buttons:**
```js
// Force-click: remove disabled attribute, then dispatch real click
btn = document.querySelector('button.buy-btn');  // Find the actual button
btn.disabled = false;
btn.removeAttribute('disabled');
btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
// Or use the most reliable approach:
btn.click();
```
Note: Some sites have event listeners that check `disabled` state before processing — in that case, only a non-headless browser (real user agent fingerprint) will work.

### Pre-sale Checklist
| Task | When | Tool |
|------|------|------|
| Start Chrome with CDP | 09:30+ | `terminal(background=true)` with `--remote-debugging-port=9222` |
| Verify CDP ready | After Chrome starts | `curl http://localhost:9222/json/version` |
| Navigate to purchase page | Before cutoff (09:45) | `browser_navigate(url)` |
| Verify logged-in | After navigation | Check for avatar/logout button |
| Keep alive | Every 25s | `browser_evaluate("document.title")` |
| Fire purchase | At sale time | Rapid click sequence |
| Notify user | After result | `send_message` |

### 🧨 Hermes `browser_navigate` Timeout Behavior

Hermes `browser_navigate` has a **60-second timeout**. If the page takes longer than 60s to load (e.g., due to traffic surge, slow API responses), the tool fails with:
```
Command timed out after 60 seconds
```

**Impact:** If you're managing a running Chrome via CDP and also trying to use `browser_navigate`, the tool may timeout while waiting for the page to respond. However, the CDP session itself is still alive — just the `browser_navigate` call timed out.

**Workarounds:**
1. **Try again** — a second `browser_navigate` call often succeeds since the page is already partially loaded
2. **Use CDP directly** — `curl http://localhost:9222/json/list` to check tab state, then use Python websocket for targeted operations
3. **For monitoring loops** — use the CDP `Runtime.evaluate` via Python (if page stays in same tab) instead of `browser_navigate`

### Page Layout Instability (Zhipu GLM Coding Plan 2026-05-02 → 05-03)

The target page layout changed significantly between consecutive days:
- **Button text**: `"暂时售罄｜05月03日 10:00 补货"` → `"特惠订阅"` (even when sold out)
- **Price display**: Monthly pricing with discount → various pricing modes
- **Tab structure**: `"连续包季/包月/包年"` tabs appeared/disappeared
- **Login requirement**: Page may show "特惠订阅" buttons even when user is NOT logged in

**Lesson**: Never assume page structure is stable. Use flexible selectors, check login state separately, and verify button behavior by clicking (not just reading text/DOM).

### 10:00 Flash Sale Full State Chain (2026-05-03 Verified)

After 10:00 restock, the state chain is NOT "sold out → available → pay". Instead:

```
Before 10:00:  "特惠订阅" [enabled]  (UI clickable, but backend soldOut:true)
     ↓ 10:00 restock
Backend switches soldOut:true → false (frontend stays "特惠订阅")
     ↓ click
"订阅中..." [disabled]  →  "抢购人数过多，请刷新再试" [disabled]
     ↓ 限流状态 (server-side rate limit)
Refresh or wait 5-15s
     ↓
"特惠订阅" [enabled]  →  click again
     ↓
"订阅中..." [disabled]  →  "抢购人数过多，请刷新再试" [disabled]
     ↓ ... repeat for several minutes ...
     ↓ 限流 finally clears
Payment modal appears → 用户扫码支付
```

**Key points:**
- The "抢购人数过多" state means you WERE fast enough (stock was there), but the server rate-limited you
- Just keep refreshing + clicking — eventually the rate limit clears
- Button state cannot be trusted to determine stock availability
- Only the Pay modal is definitive proof of purchase

### Previous Flash Sale Attempts

#### 2026-05-01 — ❌ Failed. Button never became clickable.
Stock sold out in <500ms. Headless was detected at 09:55.

**Timeline:**
```
09:55  → Page switched to "抢购人数过多" (headless detected)
09:57  → Switched to non-headless Chrome, user logged in manually
09:59  → Page showing "暂时售罄｜10:00 补货" [disabled]
10:00  → Button transitioned directly to "抢购人数过多" without ever showing "特惠订阅"
```

**Key finding: Non-headless Chrome with real user login ALSO got rate-limited at 10:00.**  
The anti-bot system checks at the SERVER level (IP/cookie fingerprint), not just headless detection. **The unlocked-button window is <100ms** — the restock transitions directly from "暂时售罄" → "抢购人数过多" without ever showing "特惠订阅" as enabled.

**Polling frequency is critical:**
- 500ms polling was NOT fast enough — stock came and went between two polls
- Need **100ms polling** at minimum
- Dual strategy: CDP click + pre-authenticated API call at the exact same millisecond

**API purchase confirmed NOT available:**
- `POST /api/biz/tokenAccounts/purchase` → 404
- Purchase is UI-only, must go through the DOM button click

**What to try next:**
1. **100ms polling** instead of 500ms
2. **Pre-fetch API credentials** and have both CDP + direct API call ready at 10:00:00.000
3. **Use a different browser fingerprint** (e.g., regular Chrome without `--headless`, but with a different IP via proxy)
4. **Bypass the disabled button**: Some sites have the "特惠订阅" button already in DOM but set `disabled=true` — remove disabled and click before the stock refreshes visually
5. **Pre-click**: Submit the purchase form/API before 10:00 with a future-dated timestamp that the server processes at 10:00 (unlikely to work but worth trying)

### 🧨 CDP WebSocket Instability on Page Reload

**Critical finding (2026-05-03):** Python CDP WebSocket connections **cannot survive `Page.reload`**. After calling `Page.reload`, the WebSocket connection drops with:
```
ConnectionClosedError: sent 1011 (internal error) keepalive ping timeout
```

This means any automation loop that does "refresh → check DOM → click → if failed, refresh again" **cannot use a persistent CDP WebSocket connection**.

**Symptom timeline:**
1. First 3-4 cycles: work fine (WS alive)
2. `Page.reload` terminates the WS connection
3. WS client gets `keepalive ping timeout` error
4. Reconnection to the same tab works, but the new page has a new WS endpoint
5. Catching this in a loop is fragile (consecutive failures accumulate)

### Tool Reliability Quick Reference

| Method | Survives Page.reload? | DOM Read | Click | Long-run | Best for |
|--------|----------------------|----------|-------|----------|---------|
| **Hermes browser tools** (`browser_navigate`, `browser_snapshot`, `browser_click`) | ✅ Fresh connection each call | ✅ | ✅ | ⚠️ 60s timeout per call | Series of discrete page ops (read → decide → act) |
| **Page-injected JS setInterval** | ✅ Runs inside page, unaffected by WS | ⚠️ Code lost if page navigates away | ✅ | ✅ Indefinitely | Monitoring loops where tab stays open |
| **Raw CDP Python WS** (`websockets` lib) | ❌ Crashes on Page.reload | ✅ | ✅ | ❌ WS drops after ~3-4 interactions | One-shot ops (navigate, screenshot, read DOM) |
| **Raw CDP Python WS** with reconnection loop | ⚠️ Fragile, WS URL changes on reload | ✅ | ✅ | ⚠️ | Only if Hermes browser tools unavailable |

**Rule of thumb:** Use Hermes browser tools for all interactive work. Reserve CDP Python WS for single-shot operations where Hermes tools have issues (e.g., Chrome 147 WebSocket 404 bug). Use page-injected JS setInterval for dedicated monitoring loops.

**Workaround code pattern (for Hermes browser tools):**
```python
# DO NOT use persistent CDP WebSocket
# Instead, use the Hermes browser tool which handles connections internally
browser_navigate(url)
browser_snapshot()  # Fresh connection
browser_click(ref)  # Fresh connection
```

**For pure-JS monitoring (injected via console):**
```javascript
// This runs inside the page — survives refreshes if the page is still the same origin
var _monitor = setInterval(function() {
  var btn = document.querySelector('.buy-button');
  if (btn && !btn.disabled) {
    btn.click();
    clearInterval(_monitor);
  }
}, 500);
```

### 🧨 Pitfall: Cron Prompt Accidental Overwrite

The `cronjob(action='update')` tool requires BOTH `job_id` AND `prompt` parameters. If you call update with just `job_id` and a placeholder prompt (e.g., `"placeholder"`), it **overwrites the existing prompt with that placeholder**.

**How to avoid:**
1. Before calling `cronjob(action='update')`, always read the current prompt from `~/.hermes/cron/jobs.json`
2. If you need to change only schedule/repeat/deliver, preserve the existing prompt
3. After any update, verify the prompt wasn't corrupted: `cronjob(action='list')` shows a preview

**Recovery from accidental overwrite:**
1. Check past session history for the original prompt content
2. If traceable from session context, reconstruct it from user's intent
3. Write it back into `~/.hermes/cron/jobs.json` directly (JSON patch)

### Login Session Loss on Chrome Restart

**Critical finding:** Chrome restart (even with `--user-data-dir=~/.chrome-cdp` symlinked to Default profile) **always loses the login session** for Zhipu AI and similar sites.

**Why:** Session cookies are bound to the original profile path. When Chrome starts with a symlinked directory, the path is different, so the encrypted cookies are unreadable.

**Workflow when restart is needed:**
1. Launch Chrome with CDP flags
2. Navigate to target site
3. Check if logged in (look for avatar/control center in navbar, not button text)
4. If not logged in — login via browser tools or ask user to login manually
5. Never assume login persists across restarts

### Chrome Cookie Encryption on macOS (for API Fallback)
Chrome v127+ encrypts cookie values using AES-256-GCM with a key stored in the macOS Keychain:

```python
# To decrypt (requires Keychain authorization dialog):
import subprocess, hashlib
from Crypto.Cipher import AES

# Get encryption key from Keychain
result = subprocess.run(['security', 'find-generic-password', '-w',
    '-a', 'Chrome', '-s', 'Chrome Safe Storage'], capture_output=True, text=True)
chrome_key = result.stdout.strip()  # May timeout waiting for GUI auth

# Derive AES key
key_bytes = hashlib.sha256(chrome_key.encode()).digest()

# Decrypt encrypted_value BLOB (format: v10 + nonce(12) + ciphertext + tag(16))
encrypted_value = row[0]  # from SQLite cookies.encrypted_value
nonce = encrypted_value[3:15]
ciphertext = encrypted_value[15:-16]
tag = encrypted_value[-16:]
plaintext = AES.new(key_bytes, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ciphertext, tag)
```

**⚠️ Limitation:** The `security` command triggers a macOS GUI dialog asking the user to authorize keychain access. If the user is remote / on Feishu, this silently times out. Better to use Approach A (user's real Chrome with CDP) instead.

## Social Media Link Content Extraction (Xiaohongshu, etc.)

Shortened social media links (xhslink.com, etc.) resolve through `browser_navigate`. **Key: page title often contains the full post content even when the accessibility snapshot is empty** — read the title, not just the snapshot.

### Xiaohongshu xsec_token Access Pattern

Xiaohongshu blocks anonymous access to notes. Two methods:

**Method A — xsec_token (Hermes browser only, no login needed):**
Use the FULL redirect URL from the xhslink shortlink. The URL includes `xsec_token` and `xsec_source` params that grant read access:
```python
# Step 1: Resolve short link to get xsec_token
curl -sL http://xhslink.com/o/<shortcode> -o /dev/null -w "%{url_effective}"

# Step 2: Navigate with full URL (includes xsec_token)
browser_navigate("<full-url-with-xsec-token>")

# Step 3: Content is in the page snapshot inside an element with the post text
```

**Method B — bb-browser (requires Chrome login):**
```bash
bb-browser site xiaohongshu/note <note-id>
```
Requires the user to be logged into xiaohongshu on Chrome. The note ID is the hex string in the URL path (`/explore/69f6ca5e...`).

### macOS Chrome CDP for Hermes Browser Tools

Reliable startup sequence (essential for Hermes `browser_navigate` after a Chrome kill/restart):

```bash
# 1. Kill ALL Chrome processes
pkill -9 -f "Chrome" 2>/dev/null; sleep 3

# 2. Launch Chrome binary directly (NOT via `open -a`)
# Use a dedicated user-data-dir — this forces a new instance
terminal(background=true):
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="/tmp/hermes-chrome-profile" \
    --no-first-run --no-default-browser-check \
    --new-window "https://target-site.com"

# 3. Wait sufficiently (10-15s on Mac for first launch)
sleep 15

# 4. Verify CDP is ready
curl http://127.0.0.1:9222/json/version
```

**Critical macOS-specific observations:**
- `open -a "Google Chrome" --args --remote-debugging-port=9222` **DOES NOT WORK** — Chrome reuses existing process, ignores the flag
- Chrome binary directly (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`) **MUST** be used
- `--user-data-dir="/tmp/..."` is required — even after a full kill, Chrome may not bind CDP without a fresh profile dir
- 10-15s wait is needed on Mac (vs 2-3s for headless/Chrome for Testing)

### bb-browser as Complementary Tool

**bb-browser** (`npm install -g bb-browser`, v0.11.3) offers 126+ community adapters for platform-specific content extraction. It works via CDP to your real Chrome and reuses its login state:

```bash
# Install
npm install -g bb-browser

# Pull community adapters
bb-browser site update

# Use platform adapters (requires Chrome logged into the site)
bb-browser site xiaohongshu/note <note-id>
bb-browser site bilibili/search "keyword"
bb-browser site zhihu/hot

# OpenClaw mode (no Chrome extension needed)
bb-browser site xiaohongshu/note <note-id> --openclaw
```

**bb-browser MCP server** for Claude Code/Cursor:
```json
{
  "mcpServers": {
    "bb-browser": {
      "command": "npx",
      "args": ["-y", "bb-browser", "--mcp"]
    }
  }
}
```

**Note:** bb-browser adapters tier system:
- **Tier 1** (1 min): direct `fetch()` + cookies → Reddit, GitHub
- **Tier 2** (3 min): Bearer token + CSRF → Twitter/X, Zhihu
- **Tier 3** (10 min): Webpack/Pinia injection → Xiaohongshu, Twitter search

### Four-Layer Agent Research Toolchain (Gu's Architecture)

| Layer | Tool | Purpose |
|-------|------|---------|
| 1️⃣ 望远镜 | Trafilatura + DuckDuckGo Search | Public web search & article extraction |
| 2️⃣ 内线 | AutoCLI (`@vk007/autocli`) | 119 providers, signed-in platform access |
| 3️⃣ 技能包 | Agent-Reach | Nostr-based decentralized agent network |
| 4️⃣ 浏览器 | bb-browser | 126 adapters, browser-as-API |

All are generic CLI tools, not bound to any specific agent. Hermes, Claude Code, Codex, OpenClaw can all use them.

→ Detailed technique: `references/social-content-extraction.md`
→ Alternative paradigm: `references/browser-harness-comparison.md`

### ⚠️ Limitation & Workaround: Image-Only Notes (Xiaohongshu Carousel)

Xiaohongshu notes often use **4-image carousels** where the main content is embedded in images, not DOM text nodes. The DOM only contains:
- Title + description (short summary, ~100 chars)
- 4 `<img>` tags with Xiaohongshu CDN URLs (require auth cookies to download)
- The detailed content per slide is ONLY in the images

**Challenge:** `browser_snapshot` / `browser_console` TreeWalker → extracts only the title + short description (~100 chars). `browser_vision` may fail if the current model lacks vision support (e.g., DeepSeek-based vision returns 404). Direct image download (`curl`) fails because Xiaohongshu CDN requires auth cookies.

**Three-tier approach (preferred order):**

**Tier 1 — Browser get_images + Vision (fastest):**
1. `browser_get_images()` → returns all image URLs on the page
2. Identify the carousel images (1080×1800px are the note slides, skip avatars/logos)
3. Download them via `curl -sL -o /tmp/imgN.webp '<CDN-URL>'` (CDN URLs from `browser_get_images` include time-limited access tokens)
4. Use `vision_analyze(image_url='/tmp/imgN.webp', question='...')` or delegate to a vision-capable subagent
5. If the current model doesn't support vision, compile results or send screenshot via `MEDIA:` path

**Tier 2 — OCR via subagent delegation (when model lacks vision):**
```python
# Step 1: Get image URLs from the page
browser_navigate(url)
imgs = browser_get_images()
# Filter: skip avatars (small), logos, keep 1080px images
carousel_images = [img for img in imgs if img['width'] >= 1000]

# Step 2: Download locally
for i, img in enumerate(carousel_images):
    curl(f"curl -sL -o /tmp/img{i+1}.webp '{img['src']}'")

# Step 3: Delegate to a vision-capable subagent or use OCR
# If Claude is available as subagent:
delegate_task(agent_id='claude', goal='OCR all images in /tmp/', 
              toolsets=['terminal', 'file'],
              context=f'Read these images: /tmp/img1.webp... (/tmp/img{len(carousel_images)}.webp)')

# If only terminal tools available:
# Use tesseract OCR (preprocess with Python PIL first for Chinese text)
python3 << 'EOF'
import pytesseract
from PIL import Image
for i in range(1, 5):
    img = Image.open(f'/tmp/img{i}.webp')
    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
    print(f'=== Img {i} ===')
    print(text)
EOF
```
**Pitfall:** `curl` from terminal may fail to download Xiaohongshu CDN images because terminal session cookies differ from browser session. The CDN URLs from `browser_get_images` are time-limited but usually work without extra auth. If they fail, use `execute_code` (which shares the Hermes environment) instead of raw terminal.

**Tier 3 — Fallback to screenshot sharing:**
- The full page screenshot is saved locally even when vision analysis fails
- Share via `MEDIA:/path/to/screenshot.png` so the user can read the image content directly

**Strategy:** First extract DOM text (title + description). If content is image-based (carousel with 2+/4 indicator → poor text extraction), deploy Tier 1 → Tier 2 → Tier 3 in order. Don't just share a screenshot — try to extract the text first.

→ Detailed workflow: `references/xiaohongshu-carousel-ocr-workflow.md`

### ✅ Verified End-to-End: Xiaohongshu Link → Obsidian (2026-05-05)

This exact flow was tested and verified on Gu's Mac:

1. **Receive xhslink short URL** → `curl -sL` to resolve → extract `xsec_token`
2. **Chrome CDP** already running on port 9222 (launchd auto-start, persistent `~/.hermes/chrome-profile/`)
3. **`browser_navigate`** with full URL (including `xsec_token`) → loads note content
4. **Extract** text from `browser_snapshot` StaticText elements
5. **Save** as Markdown to 个人知识库 vault 的 `3-知识/raw/<title>.md`（默认 vault 是个人知识库，不是懂球帝工作）

**Prerequisites verified:**
- Chrome running with `--remote-debugging-port=9222 --user-data-dir=~/.hermes/chrome-profile`
- launchd plist `com.hermes.chrome-cdp` loaded (auto-starts at login)
- Xiaohongshu login session persisted in profile
- All tools (bb-browser v0.11.3, Trafilatura v2.0.0, AutoCLI v0.1.3) installed and working

**Script path:** `~/.hermes/bin/chrome-cdp.sh` (manual start alternative)

### 🖥️ Desktop Control Workflow for User Login

When the user sends a link that requires login and says they're "不在电脑前" (not at the computer):

**Do NOT** just bring the window to front and ask them to log in. Instead:

1. Start Chrome with CDP (see macOS setup above)
2. Navigate to the target site via `browser_navigate`
3. Click the login button via `browser_click`
4. Ask the user for credentials via chat
5. Use `browser_type` to fill in the form fields
6. Complete the login flow

The Hermes `browser_type` and `browser_click` tools work through CDP — you can type into textboxes and click buttons by referencing their element IDs from the `browser_snapshot` output. Use refs like `@e22` for the phone input, `@e23` for the verification code button, etc.

**Xiaohongshu login via desktop control:**

**⚠️ Agreement popup is a mandatory intermediate step.** Clicking "登录" → agreement ("阅读并同意《用户协议》etc.") appears first. You must accept it BEFORE clicking "获取验证码" — otherwise the SMS sending API won't fire (button click appears to work but no SMS is sent).

```python
# After Chrome CDP is running and page is loaded:
# 1. Click "登录" button (usually in navbar, ref varies ~@e10 or @e16)
browser_click(ref="@e10")  # or whichever "登录" button ref

# 2. Agreement popup appears: "阅读并同意" with 《用户协议》《隐私政策》《儿童/青少年个人信息保护规则》
#    Two buttons: "同意并继续" (ref varies) and "取消"
#    ⚠️ MUST agree first, or 获取验证码 won't work
browser_click(ref="@e11")  # "同意并继续"

# 3. Phone input field appears (ref ~@e22)
browser_type(ref="@e22", text="138xxxxxxxx")

# 4. Click "获取验证码" button (ref ~@e23 or @e25)
#    Button text changes to "重新发送（174s）" after success
browser_click(ref="@e25")

# 5. Wait for user to provide verification code from SMS
# 6. Enter code and click "登录" (ref ~@e7)
```

Note: Xiaohongshu uses phone+verification-code login on web. No password field. The verification code is sent to the user's phone. The agreement API call (`/api/sns/web/v2/login/send_code` → 200) only fires after agreement is accepted.

### Toolchain: Four-Layer Architecture (Installed & Verified)

Gu's Agent research toolchain is fully installed and verified on this Mac:

| Layer | Tool | Version | Status |
|-------|------|---------|--------|
| 1️⃣ 望远镜 | Trafilatura (pip) | 2.0.0 | ✅ `trafilatura -u URL --output-format json` |
| 2️⃣ 内线 | AutoCLI (npm -g @vk007/autocli) | 0.1.3 | ✅ 119 providers, `autocli --version` |
| 3️⃣ 技能包 | Agent-Reach (OpenClaw plugin) | 0.6.14 | ✅ Nostr agent network |
| 4️⃣ 浏览器 | bb-browser (npm -g bb-browser) | 0.11.3 | ✅ 126 adapters, `bb-browser site update` done |

**bb-browser install & verify:**
```bash
npm install -g bb-browser
bb-browser --version          # 0.11.3
bb-browser site update        # Pulls 126 community adapters
bb-browser site list          # Shows all available platforms
```

**Trafilatura install & verify:**
```bash
pip install trafilatura
trafilatura -u "https://example.com" --output-format json  # Extracts article text
```

**AutoCLI install & verify:**
```bash
npm install -g @vk007/autocli
autocli --version             # 0.1.3
autocli doctor                # Check installation health
autocli login --browser       # Shared browser login (one-time)
autocli developer github me --json  # Use any of 119 providers
```

All tools are generic CLI — not bound to Hermes, Claude Code, or any specific agent.

## Search Engine Fallback: DuckDuckGo via Browser (When Google Is Blocked)

### Core Problem
Google search is frequently blocked from curl/terminal in Chinese-network environments (timeouts, 408 errors). Standard search tools (`mcp_scrapling_fetch_s_fetch_page` to Google, `curl` to Google) all fail. **DuckDuckGo via browser_navigate works because the browser has a different User-Agent and network path.**

### When to Use
- Google search via `mcp_scrapling_fetch` times out after 30s+
- `curl` to Google returns empty or 408 (network layer blocked)
- You need recent news/trends but have no access to Google News API
- Background cron jobs that need web research (no user present to troubleshoot)

### Workflow

#### Step 1 — First, try the direct approach anyway (it might work):
```python
# scrapling_fetch with basic mode (fastest if it works)
mcp_scrapling_fetch_s_fetch_page(url="https://www.google.com/search?q=<query>&hl=zh-CN&tbs=qdr:d")
```
If timeout or empty → proceed.

#### Step 2 — Navigate to DuckDuckGo with your query via browser:
```python
browser_navigate(url="https://duckduckgo.com/?q=<URL-encoded query>&t=h_&ia=web")
```
DuckDuckGo's full web interface has much simpler bot detection than Google. It renders reliably in the browser accessibility tree.

#### Step 3 — Filter to news results (key technique):
The accessibility snapshot includes a navigation bar with tabs: 全部, 图片, 新闻, 视频. Click the "新闻" tab ref from the snapshot:
```python
# After browser_navigate:
snapshot = browser_snapshot()
# Find the "新闻" / "News" link element ref and click it
browser_click(ref="e76")  # ref varies per session, use actual from snapshot
```
This switches to news-only results, which are structured as article elements with clear headings and timestamps.

#### Step 4 — Extract structured news from browser_snapshot:
After clicking "新闻", the page structure changes to show articles in a clean format. Each article contains:
- **heading**: Article headline (clickable)
- **StaticText**: Source name + time (e.g., "2 days ago" / "Vietnam Investment Review")
- **link**: Full article URL

Extract via `browser_snapshot().snapshot` — look for these patterns:
```text
- heading "Hisense launches FIFA World Cup 2026 campaign" [level=3, ref=...]
  - StaticText "2 days ago"
  - StaticText "vir.com.vn"
```

#### Step 5 — Get more detail by clicking articles:
For key stories, click the article heading link to navigate to the full article:
```python
browser_click(ref="e68")  # Click the article heading
# Read the full content via browser_snapshot()
```

#### Step 6 — Scroll for more results:
```python
browser_scroll(direction="down")
```
DuckDuckGo loads news results in roughly 10-item batches per page.

### Chinese-Language Search (for Chinese-market intelligence)
DuckDuckGo handles Chinese queries natively. Use the same technique:
```python
browser_navigate(url="https://duckduckgo.com/?q=世界杯+营销+品牌+赞助+2026&t=h_&ia=news")
```
Switch to "新闻" tab after loading. Chinese news results come from sources like 腾讯网, 21经济网, etc.

⚠️ **Important:** DuckDuckGo may show "找不到关于 <query> 的新闻文章" for obscure Chinese queries — in that case, broaden the query or fall back to web results (click "全部" tab).

### Pitfalls
- **browser_snapshot element refs are ephemeral**: Each page load generates new refs (@e57, @e68). Never hardcode refs — always read them from the current snapshot.
- **DuckDuckGo may show "升级到我们的浏览器" banner**: This is just a promotional UI element. Scroll past it — the search results are below.
- **Time filters don't work via DDG URL parameters**: DDG ignores ?tbs=qdr:d style parameters. Use browser-based tab navigation instead (but DDG's news tab already shows recent results).
- **Article URLs may be truncated in snapshot**: The URL shown in snapshot ends with "..." for long URLs. Click through to get the real URL.
- **Some sites behind paywall**: WWD, Forbes, Fast Company articles may be paywalled. Their snippets are still useful for intelligence.
- **No user present — don't wait for login pages**: In cron job context, if the target article redirects to a login page, just use the snippet from search results.

### Comparison: When to Use DuckDuckGo via Browser vs Other Approaches

| Approach | When to Use | Works on This Env? |
|----------|-------------|-------------------|
| **DuckDuckGo via browser** (this section) | Google/curl blocked, need structured news results | ✅ Verified (2026-05-13) |
| **Trafilatura** (Layer 1 望远镜) | Need article text extraction, known URL | ✅ `trafilatura -u URL --output-format json` |
| **AutoCLI** (Layer 2 内线) | Need signed-in platform access (Twitter, etc.) | ✅ 119 providers |
| **bb-browser** (Layer 4 浏览器) | Platform-specific content extraction | ✅ 126 adapters |
| **curl directly to DDG lite** | Simple search, no JS rendering needed | ⚠️ DDG lite often returns empty in Chinese network |
| **mcp_scrapling_fetch to DDG** | Quick one-shot fetch | ⚠️ Times out like Google |

### Reference
→ This technique was verified on 2026-05-13 during a cron job collecting World Cup marketing news. The full session transcript is in session history.

## Zhipu AI (open.bigmodel.cn) Specifics
→ Persistent Chrome CDP setup via launchd: `references/chrome-cdp-persistence-launchd.md`
→ Timed grab script: `references/zhipuai-grab-script-20260501.md`
→ 2026-05-01 actual attempt (rate limiting, non-headless fallback): `references/zhipuai-timed-grab-20260501.md`
→ 2026-05-01 full timeline (fixes, decisions, post-mortem): `references/zhipuai-2026-05-01-attempt.md`
→ 2026-05-03 timeline + tool comparison + state chain: `references/zhipuai-2026-05-03-attempt.md`

### URLs
- **Login**: `https://open.bigmodel.cn/login`
- **Coding Plan (NOT subscribe-pay)**: `https://open.bigmodel.cn/coding-plan/personal/overview`
  - The `/subscribe-pay` page redirects to login or shows blank hero — **do not use**
  - Always navigate directly to `/coding-plan/personal/overview` for purchase flow
- **API base**: `https://open.bigmodel.cn/api`

### Login
- API: `POST /api/auth/login` with `{"username":"...","password":"...","loginType":"password"}`
- From browser console only (curl blocked by Alibaba Cloud WAF, all 405)
- After login: token stored in `localStorage`, not cookie
- Logged-in account shown in top-right avatar menu (账号ID visible in dropdown)
- Purchase API: `POST /api/biz/tokenAccounts/purchase` → 404 (not accessible via API, UI only)

### Coding Plan Products (as of 2026-04-30)
| Tier | Full Price | Discounted | Status |
|------|-----------|------------|--------|
| Lite | ￥49/月 | ￥44.1/月 | ❌ 暂时售罄 |
| **Pro** | **￥149/月** | ￥134.1/月 | ❌ 暂时售罄 |
| Max | ￥469/月 | ￥422.1/月 | ❌ 暂时售罄 |

All tiers restock at **05月01日 10:00** (次日早上10点).

### DOM Extraction When Accessibility Tree Is Empty
Sites using heavy JS frameworks may return accessibility tree with only 12 elements despite 829KB HTML body. Use `TreeWalker` from browser console:
```js
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
const texts = [];
let node;
while (node = walker.nextNode()) {
  const t = node.textContent.trim();
  if (t && t.length > 1) texts.push(t);
}
texts.join('\n');
```

### Other APIs
- Product list: `GET /api/biz/tokenResPack/productIdInfo`
- isLimitBuy: `GET /api/biz/tokenAccounts/isLimitBuy?productFunctionType=CODING_PLAN`

## Mission Control Ecosystem (Two Different Repos!)
Two unrelated projects share the name "mission-control" — do NOT confuse them:

| | builderz-labs/mission-control | crshdn/mission-control |
|--|--|--|
| Description | AI agent orchestration platform (task dispatch, multi-agent workflows, spend monitoring) | Autonomous Product Engine (AI researches markets, generates features, ships code as PRs) |
| Stars | 4468 | 1975 |
| Port | **3000** | **4000** |
| Directory | `~/builderz/` | `~/mission-control/` |
| Status | ✅ Running (PID 97598, via `pnpm dev`) | ✅ Running (next-server v14.2.21) |
| Git remote | `https://github.com/builderz-labs/mission-control` | `https://github.com/crshdn/mission-control` |
| Setup | `pnpm install` then `PORT=3000 pnpm dev` | Already running |
| Access | `http://localhost:3000/setup` | `http://localhost:4000/` |

**Both can run simultaneously** — separate directories, separate ports, no conflicts.

## ⚠️ Pitfall: Accidentally Killing Chrome for Testing

`kill $(pgrep -f "Google Chrome")` catches **ALL** Chrome processes, including the headless "Google Chrome for Testing" running CDP on port 9222. This will break `browser_navigate` until Chrome for Testing is restarted.

**Safe killing (only regular Chrome):**
```bash
# Kill only real-profile Chrome with user-data-dir containing extensions
pgrep -f "Library/Application Support/Google/Chrome" | xargs kill 2>/dev/null

# Or use -x for exact process name match (won't match "for Testing" variants)
kill $(pgrep -x "Google Chrome") 2>/dev/null
```

**Restart Chrome for Testing after accidental kill:**
```bash
npx agent-browser install  # ensure browser binary exists
terminal(background=true):
  "/Users/gu/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
    --remote-debugging-port=9222 \
    --headless --disable-gpu --no-sandbox \
    --no-first-run --no-default-browser-check \
    --user-data-dir="$HOME/.hermes/chrome-profile"

# Verify
sleep 8 && lsof -i :9222 && curl http://localhost:9222/json/version
```

**Note:** After restart, you must re-login to websites because the session is in `--user-data-dir`. Use `browser_navigate` → `browser_type` → `browser_click` to re-authenticate.

## CDP Diagnostic Checklist

When browser_navigate fails with "Auto-launch failed: All CDP discovery methods failed for 127.0.0.1:9222" or "CDP WebSocket connect failed: HTTP error: 404 Not Found":

1. **Is Chrome for Testing running?** → `ps aux | grep "Chrome for Testing" | grep -v grep`
2. **Is port 9222 listening?** → `lsof -i :9222`
3. **Is config.cdp_url set?** → `grep cdp_url ~/.hermes/config.yaml`
4. **Can CDP respond?** → `curl http://localhost:9222/json/version` (should show Browser, webSocketDebuggerUrl)
5. **Has config changed since agent started?** Config changes need agent restart to take effect (config is read at tool import time, not hot-reloaded)

Quick fix for most issues:
```bash
# 1. Kill stale processes
kill $(pgrep -f "Chrome for Testing") 2>/dev/null; kill $(pgrep -f agent-browser) 2>/dev/null
sleep 2

# 2. Set config
python3 -c "
import yaml
with open('/Users/gu/.hermes/config.yaml') as f: cfg = yaml.safe_load(f)
cfg.setdefault('browser', {})['cdp_url'] = 'http://localhost:9222'
with open('/Users/gu/.hermes/config.yaml', 'w') as f: yaml.dump(cfg, f)
print('cdp_url set')
"

# 3. Start Chrome for Testing headless
terminal(background=true):
  "/Users/gu/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
    --remote-debugging-port=9222 --headless --disable-gpu --no-sandbox \
    --no-first-run --no-default-browser-check \
    --user-data-dir="$HOME/.hermes/chrome-profile"

# 4. Wait and verify
sleep 10 && lsof -i :9222 && curl -s http://localhost:9222/json/version | head -3
```

### 🚨 Known Issue: Chrome 147 + Hermes Browser Tools CDP WebSocket 404

**Observed on Gu's Mac (Chrome 147.0.7727.137):** Even when CDP HTTP endpoints (`/json/version`, `/json/list`) work normally with valid webSocketDebuggerUrl, the Hermes browser tools all fail with:
```
CDP WebSocket connect failed: HTTP error: 404 Not Found
```
The actual Hermes error source (from logs: `~/.hermes/logs/gateway.error.log`):
```
ERROR tools.browser_cdp_tool: browser_cdp unexpected error
  File ".../tools/browser_cdp_tool.py", line 112, in _cdp_call
    async with websockets.connect(
```

**Root cause:** Unknown. The CDP WebSocket URLs returned by Chrome 147 use standard format (`/devtools/browser/<uuid>`) and work with raw Python `websocket-client`, but Hermes's internal `websockets` async library may generate a different connection path.

**Workaround:** Use raw CDP WebSocket via Python `websocket-client` in execute_code/terminal:
```python
import json, websocket
ws = websocket.create_connection("ws://localhost:9222/devtools/page/<tab-id>")
ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": "..."}}))
result = json.loads(ws.recv())
ws.close()
```
Or navigate via HTTP: `curl http://localhost:9222/json/new?url=https://target.com`

**If raw CDP also fails:** Fall back to user-installed approach (user opens links manually in their own Chrome).

**Prevention:** Use Chrome for Testing (Playwright) instead of regular Chrome if Hermes browser tools are essential.

## When to Use This Skill
- Curl returns 405/403 on API that should work
- Need browser session/cookies for subsequent page loads
- Website has bot detection that resists terminal automation
- Token type difference suspected (HS512 browser vs HS256 curl)
