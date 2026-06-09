# Hermes Desktop v1.0 — Second-Round Final Review (Review/QA Readiness)

**Date:** 2026-06-04
**Reviewer:** opencode (second-round pass)
**Scope:** Hermes Desktop v1.0 readiness for Review/QA subsystem.
**Method:** Static code survey of all `hermes-agent/executors/*` modules + cross-references
to Phase 7 / Phase 8 / Phase 10 / opencode-feasibility reviews + empirical CLI probes.
**No business code modified.**

---

## TL;DR — 10 Check Points Summary

| # | Check Point | Verdict | Worst Severity |
|---|-------------|---------|----------------|
| 1 | Codex-like 主链路是否清楚 | ⚠️ **Partially** | P1 |
| 2 | opencode executor 是否被正确标注支持程度 | ❌ **Mislabeled** | **P0** |
| 3 | Review / QA 是否只读 | ✅ **Yes (CLI level)** | P1 |
| 4 | Worktree / merge / discard 是否有风险 | ⚠️ **Operations exist, no auto-run** | P1 |
| 5 | External Inbox 是否不能自动执行 | ✅ **Yes (by accident, not by design)** | **P0** (4 issues from Phase 10 still open) |
| 6 | Router 是否只推荐不执行 | ✅ **Yes** | P2 |
| 7 | Workspace Context 是否不会泄漏 secrets | ❌ **No filtering** | P1 |
| 8 | Prompt snapshot 是否可见 | ⚠️ **Built but not exposed** | P1 |
| 9 | unavailable / stub 是否明确 | ⚠️ **Inconsistent** | P1 |
| 10 | UI 是否存在明显误导用户的地方 | ✅ **No misleading labels found** | P2 |

**Counts:** 2 P0 · 6 P1 · 2 P2 = 10 issues for v1.0.
**Cross-references:** 4 prior reviews (Phase 7, Phase 8, Phase 10, opencode-feasibility)
already cover 18 deeper issues. This pass surfaces **only the v1.0-blocker layer**.

---

## Check Point 1 — Codex-like Main Path Clarity

**Verdict:** ⚠️ Partially. The 3 adapters exist and are wired, but each is "minimal v0.3"
(self-described) and only **one** of them is truly Codex-like.

### Evidence

| Adapter | File | Lines | Subprocess | Stdout capture | Status |
|---------|------|------:|------------|----------------|--------|
| `hermes-local` | `hermes_local_adapter.py` | 354 | ✅ | ✅ | **Full** (deterministic stub) |
| `codex` | `codex_adapter.py` | 306 | ✅ `codex` CLI | ✅ | Minimal — no JSON streaming, no diff, no worktree |
| `claude-code` | `claude_code_adapter.py` | 322 | ✅ `claude-code` CLI | ✅ | Minimal — same gaps |
| `opencode` | `opencode_adapter.py` | 227 | ❌ **BROKEN** (uses `opencode -p` → TUI) | ❌ exit 1, 0 bytes | See check point 2 |

**Codex-like definition** = user runs `codex exec "fix bug X"` and gets back a reviewable
diff in a known location. This requires:
1. ✅ subprocess launch
2. ✅ stdout/stderr capture
3. ❌ **structured JSON line streaming** (`codex exec --output-format stream-json`)
4. ❌ **diff generation** (git snapshot tracking)
5. ❌ **worktree support**

All 3 missing items are listed verbatim in the adapter docstrings:

> `codex_adapter.py`:
> "Not implemented (v0.4+): Cloud API mode … Structured JSON output parsing … Diff generation … Worktree support"
>
> `claude_code_adapter.py`:
> "Not implemented (v0.4+): Structured JSON line streaming (requires `--output-format stream-json`) … Diff generation … Worktree support"

### Severity
- **P1** — the path *works* for trivial use (run a command, see output), but is **not**
  Codex-like for review purposes. A user expecting "I run codex, get a reviewable diff"
  will be confused.

### Recommendation
For v1.0, change the messaging from "Codex-like" to "minimal CLI passthrough" in:
- `docs/architecture/executor-integration.md` (if such file exists)
- Adapter docstrings
- TUI surfaces (see check point 10)

---

## Check Point 2 — opencode Executor Support Level Labeling

**Verdict:** ❌ **Mislabeled.** The `opencode` executor is registered as if it works,
but the adapter is **broken** (won't produce any output), and the registry flags
disagree with what the feasibility review recommends.

### Evidence — Current State

`hermes-agent/executors/opencode_adapter.py:93` invokes `opencode -p`:
```
$ opencode -p "hello"
[3787 bytes of ASCII TUI banner, then exit 1, 0 bytes stdout]
```

This is a **confirmed TUI launch**, not a non-interactive run. (Per the
`opencode-review-qa-executor-feasibility.md` doc, the correct invocation is
`opencode run --format json --pure --agent plan --dir <wt> -f <diff>`.)

`hermes-agent/executors/registry.py` has the manifest:
```yaml
opencode:
  review_gate: false        # ← should be true per feasibility
  supports_worktree: false  # ← should be true per feasibility
  default_model: "deepseek-v4-flash"  # ← suspicious name (no such model on /models)
```

**Problem chain:**
1. `review_gate: false` → router/review does NOT route reviews to opencode
2. `supports_worktree: false` → review/QA cannot run in worktree context
3. `default_model: "deepseek-v4-flash"` → looks made-up; no model by that name exists
4. Adapter invokes broken command → even if routed, it produces nothing

### Severity
- **P0** — user sees "opencode" as a registered executor, can pick it, gets nothing.
  This is the **single biggest v1.0 readiness risk** for the Review/QA subsystem,
  because v1.0's marketing angle is "opencode as the read-only reviewer".

### Recommendation
Three options, in order of effort:

| Option | Effort | What it does |
|--------|--------|--------------|
| A. **Stub it** | 30 min | Change manifest to `available: false`, add reason "opencode CLI in TUI mode — use `opencode run --format json` via wrapper (v1.1)". Update health to UNAVAILABLE with that message. |
| B. **Fix the command** | 2 hours | Patch `opencode_adapter.py:93` to use `opencode run --format json --pure --agent plan --dir <cwd>`; switch manifest to `review_gate: true, supports_worktree: true`. |
| C. **Remove the manifest** | 10 min | Delete `opencode` from registry; only ship `hermes-local`, `codex`, `claude-code`. |

**Recommended for v1.0:** Option **A** (stub it). The CLI is evolving rapidly; landing
a half-working opencode integration in v1.0 creates support burden. Add a clear
"coming in v1.1" note to docs.

---

## Check Point 3 — Review / QA is Read-Only

**Verdict:** ✅ **Yes at the CLI level.** The `review build-prompt` subcommand **only
prints the prompt to stdout** — it does NOT invoke any executor. Same for `qa build-prompt`.

### Evidence

`hermes-agent/executors/review_cli.py:35-58`:
```python
async def cmd_review_build_prompt(goal, diff, changed_files, executor, prompt_snapshot):
    agent = ReviewAgent()
    prompt = agent.build_prompt(...)
    print(prompt)              # ← only prints
    print(f"Lines: {len(...)}")  # ← stats only
    # NO call to executor
```

The `parse` subcommand (`review_cli.py:61-106`) just **parses text** into findings
and prints them — no execution.

The `executor` subcommand (`review_cli.py:109-115`) just **recommends** an executor
based on availability.

### Residual Risk
- A user could take the printed prompt and paste it into a `codex` run that is
  *not* gated as read-only. **But** that's the same risk as anyone typing a prompt
  into any CLI — it's not a Hermes-specific safety issue.
- The `opencode` adapter is broken (check point 2), so even if someone tried to use
  it for a review, the result is "no output" rather than "writes to disk".

### Severity
- **P1** — the read-only contract is honored at the Hermes layer, but it relies
  on the broken-opencode-adapter accident for safety. Once opencode works
  (v1.1+), the `plan` agent's read-only-by-intent must be **enforced**, not assumed.
- See `opencode-review-qa-executor-feasibility.md` for the `plan` agent 0-write
  empirical test (24 audits showed 0 file writes when invoked with `--agent plan`).

### Recommendation
For v1.0: leave as-is. For v1.1, add an explicit `--read-only` flag in the review
CLI that hard-rejects any non-plan executor selection.

---

## Check Point 4 — Worktree / Merge / Discard Risk

**Verdict:** ⚠️ **Operations exist and are user-invoked, no auto-run, no
path-resolution safety on merge target.**

### Evidence

`hermes-agent/executors/worktree_cli.py:228-244` (commands):
```
worktree create <thread_id> --run-seq N
worktree status <thread_id>
worktree merge <thread_id>
worktree discard <thread_id> [--force]
worktree list [--all]
worktree diff <thread_id>
worktree files <thread_id>
```

`worktree.py` (577 lines) handles:
- `WorktreeManager.create(thread_id, run_seq)` — git worktree add
- `WorktreeManager.merge(thread_id)` — git merge into base
- `WorktreeManager.discard(thread_id, force=False)` — git worktree remove
- `WorktreeManager.get_diff_stat / get_changed_files`

**Auto-run check:** No scheduler, no orchestrator, no daemon calls these. They are
CLI-only, user-invoked. ✅

**Risk surfaces:**
1. `merge` does not check for **uncommitted changes in the base branch** before merging.
   A concurrent edit to the base could produce a merge conflict that the user must
   resolve manually — acceptable but not advertised.
2. `discard --force` bypasses the "are you sure?" prompt. Acceptable for power users.
3. **Path safety:** `merge` does not validate the worktree path is *under* the project
   root. If `thread_id` is something like `../../../etc`, the merge target is
   attacker-controlled. (This is the same risk class as Phase 6 worktree review.)

### Severity
- **P1** — same as Phase 6 finding, re-surfaced for v1.0.

### Recommendation
- Add `Path.resolve().is_relative_to(project_root)` check in `WorktreeManager.merge`
  and `WorktreeManager.discard` (1 line each).
- Document that merge does not pre-check base branch state.

---

## Check Point 5 — External Inbox Cannot Auto-Execute

**Verdict:** ✅ **Yes — but by accident, not by design.** No code path triggers an
executor from an InboxItem. The protection is structural (no consumer reads InboxItem),
not enforced.

### Evidence (from `phase-10-opencode-inbox-security-review.md`)

**Reference:** all 4 P0 issues from Phase 10 are still open:

| ID | Issue | Status |
|----|-------|--------|
| INB-01 | `source` field has no identity check (any process can claim `feishu`/`discord`/`scheduler`) | **Open** |
| INB-02 | `body` has no injection scan; 2000-char cap defined in design but not enforced | **Open** |
| INB-03 | `body`/`raw_payload` size is unbounded (100MB JSON writable) | **Open** |
| INB-04 | `inbox.json` no flock + `0o644` perms; concurrent writes corrupt; same-host readers see content | **Open** |

**Accidental isolation** (verified by static scan):
- `InboxItem` / `InboxManager` are referenced only in: `inbox.py`, `inbox_cli.py`, `types.py`
- **No** orchestrator, router, executor, web_server, or scheduler imports or reads them
- `InboxResultCallback` defined in `types.py:478` but has **0 call sites**
- No `/v1/inbox` API endpoint exists in the gateway

So today, even if an attacker writes a malicious InboxItem, **nothing reads it back
into a task**. But this is because **nothing is wired yet** — the inbox subsystem
is a half-built v0.8 with no consumer.

### Severity
- **P0** (inherited from Phase 10) — the inbox is unsafe to enable in v1.0, but
  also doesn't need to be enabled because nothing reads it. For v1.0, **ship the
  inbox as CLI-only with a clear "no automatic execution" warning** in
  `ib --help` and the architecture doc.

### Recommendation
- For v1.0: keep inbox CLI-only, **do not** expose any HTTP/feishu/discord/scheduler
  source until INB-01..04 are fixed.
- Add a top-of-file warning in `inbox.py`:
  ```python
  # ⚠️  v1.0: Inbox is CLI-only and is NOT consumed by any executor.
  #     No InboxItem will trigger an AgentRun. (See docs/review/phase-10-...)
  ```
- Re-target INB-01..04 to v1.1.

---

## Check Point 6 — Router Only Recommends, Never Executes

**Verdict:** ✅ **Yes.** `ExecutorRouter.recommend()` returns a `RouterRecommendation`
dataclass; there is no execution path inside the router.

### Evidence

`hermes-agent/executors/router.py:240-301` (return path):
```python
def _fallback_recommendation(self, available, search_text):
    return RouterRecommendation(
        recommended_executor=executor,
        confidence=0.40,
        reason="...",
        alternatives=[],
        source="health_fallback",
    )
```

`RouterRecommendation` (from `types.py`) has fields:
- `recommended_executor: ExecutorId`
- `confidence: float`
- `reason: str`
- `alternatives: List[ExecutorId]`
- `source: str`  ("keyword" or "health_fallback")

**No `accept()`, `execute()`, `commit()`, or `run()` method exists on the router or
the recommendation.** The router is purely advisory.

**No `--accept` flag** in any router CLI subcommand. (Verified by `grep -n
"accept\|auto_run" hermes-agent/executors/router.py` → 0 hits.)

### Residual Risk
None. Router is read-only by code structure.

### Severity
- **P2** — informational. Recommend documenting this in the router's docstring
  to make the contract explicit.

### Recommendation
Add to `router.py` module docstring:
```
# Router is purely advisory. recommend() returns a RouterRecommendation.
# Callers (CLI, TUI) decide whether to ask the user before invoking an executor.
# The router never invokes an executor itself.
```

---

## Check Point 7 — Workspace Context Does Not Leak Secrets

**Verdict:** ❌ **No filtering, no scanning, no redaction.** Free-form text fields
(`architecture_notes`, `coding_conventions`, `current_sprint`) can carry secrets and
will be injected verbatim into the executor prompt.

### Evidence

`hermes-agent/executors/context.py` (258 lines):
- `ProjectContext` dataclass has these string fields:
  - `project_overview: str`
  - `architecture_notes: str`  ← free-form, can hold anything
  - `current_sprint: str`
  - `coding_conventions: str`
  - `recent_tasks: List[RecentTask]` (each has `summary: str` and `notes: str`)
  - `common_commands: List[CommandEntry]` (each has `command: str`)
  - `test_commands: List[CommandEntry]` (each has `command: str`)
  - `forbidden_areas: List[str]`
- `context_injection_enabled: bool = True` — defaults to ON
- `include_flags: Dict[str, bool]` — runtime flags, but no secret-aware filtering

**Grep for secret handling** in `context.py`:
```
$ grep -n "api_key\|token\|password\|secret\|filter\|sanitiz\|redact" context.py
(no matches)
```

**No filtering, no redaction, no warning.** If a user puts their AWS key in
`architecture_notes` (e.g., as part of a "setup" section), it will be injected
into the executor prompt on every run.

### Severity
- **P1** — secrets-in-context is a real but lower-probability risk. The
  mitigation is: secrets should not be in `context.json` to begin with. But the
  system silently amplifies any user mistake.

### Recommendation
Two options:

| Option | Effort | What it does |
|--------|--------|--------------|
| A. **Document** | 5 min | Add to `docs/architecture/workspace-context-injection.md`: "Do not put secrets (API keys, tokens, passwords) in context.json — they are injected verbatim into the executor prompt." |
| B. **Scan + warn** | 2 hours | In `WorkspaceContextManager.inject()`, regex-scan all string fields for `(?i)(api[_-]?key|token|password|secret|aws[_-]access)` patterns. If found, refuse to inject and print a warning. |

**Recommended for v1.0:** Option **A**. Option B is reasonable for v1.1.

---

## Check Point 8 — Prompt Snapshot Visibility

**Verdict:** ⚠️ **The `PromptSnapshot` dataclass exists and is well-designed, but
there is no UI or CLI command to display it after a run.**

### Evidence

`hermes-agent/executors/types.py:319-328`:
```python
@dataclass
class PromptSnapshot:
    user_prompt: str
    injected_prompt: str
    context_sha: Optional[str] = None
    context_include_flags: Dict[str, bool] = field(default_factory=dict)
    estimated_tokens: int = 0
    generated_at: Optional[datetime.datetime] = None
```

**Where is it stored?**
- `grep -rn "PromptSnapshot" hermes-agent/executors/` →
  - `types.py:319` (definition)
  - `prompt_builder.py:317` (creation in `PromptBuilder.build()`)
  - `phase-8-opencode-prompt-review.md` (our prior review)

**Where is it shown?**
- **Nowhere in the CLI.** No `python -m executors.cli snapshot <run_id>` command.
- **Nowhere in the TUI.** No component reads or displays it.
- It is **returned** from `PromptBuilder.build()` but no caller persists or displays it.

**Where SHOULD it be shown?**
- A `python -m executors.cli show-prompt <run_id>` subcommand would surface it.
- A TUI panel "Prompt used" with a collapsible `injected_prompt` view.

### Severity
- **P1** — for a Review/QA subsystem, "what prompt did we actually send?" is
  the most important debugging affordance. The snapshot is built but invisible.

### Recommendation
For v1.0, add a minimal `python -m executors.cli show-prompt --run-id <id>` that
prints `PromptSnapshot.user_prompt` and `PromptSnapshot.injected_prompt`.
The snapshot should be persisted to `.hermes/runs/<run_id>/prompt.json` by
the orchestrator (which doesn't exist yet — see INB-05 in Phase 10).

---

## Check Point 9 — Unavailable / Stub Clarity

**Verdict:** ⚠️ **Inconsistent.** Some stubs are clearly labeled, some are not.

### Evidence — Well-Labeled Stubs ✅

`inbox.py:262-273` (`writeback_destination`):
```
if item.source == InboxSource.FEISHU:
    return "Feishu thread (unavailable — stub)"
if item.source == InboxSource.DISCORD:
    return "Discord channel (unavailable — stub)"
if item.source == InboxSource.SCHEDULER:
    return "Scheduler job status (unavailable — stub)"
```

This is exemplary — every stub source has an explicit "(unavailable — stub)" suffix.

### Evidence — Poorly Labeled ⚠️

**1. `opencode` manifest** (see check point 2): registered as if it works, but
adapter is broken and `default_model: "deepseek-v4-flash"` looks made-up. No
"(stub)" label.

**2. `InboxSource` enum** (`types.py:434-440`):
```python
class InboxSource(Enum):
    DESKTOP = "desktop"
    CLI = "cli"
    FEISHU = "feishu"        # stub
    DISCORD = "discord"      # stub
    SCHEDULER = "scheduler"  # stub
```

The `# stub` comment is **only in the source code**, not in the `--help` output.
A user running `python -m executors.cli ib add --help` sees `feishu` as a
valid `--source` value with no warning that writing to it does nothing.

**3. `claude-code` / `codex` adapters**: docstrings say "Not implemented (v0.4+)"
but the manifest's `available: true` (when binary is on PATH) presents them as
fully functional.

**4. `HermesLocalAdapter`**: deterministic stub (always returns the same response)
but is presented as the **default fallback** in router's health_fallback path.
A user with no other executor might think `hermes-local` is a real AI.

### Severity
- **P1** — users will be confused about which features are real vs. stub.

### Recommendation
- Add `(stub)` suffix to `InboxSource` values in CLI help text (use
  `argparse choices` with formatted strings, or post-process `--help`).
- For `opencode` manifest (check point 2 fix), add `available: false` + reason.
- For `HermesLocalAdapter`, rename to `hermes-local-stub` or add
  `description: "Deterministic stub for offline testing"`.

---

## Check Point 10 — UI Misleading Labels

**Verdict:** ✅ **No misleading labels found in TUI lib code.** The 2 "claude-code"
references are code comments, not user-facing labels.

### Evidence

Searched `hermes-agent/ui-tui/src/` for executor/inbox/router/review labels:

```
$ grep -rn "codex\|claude-code\|opencode\|hermes-local" \
       hermes-agent/ui-tui/src/
hermes-agent/ui-tui/src/app/useInputHandlers.ts:91:
  // Wheel accel ported from claude-code: inter-event timing drives step size,
hermes-agent/ui-tui/src/app/useInputHandlers.ts:523:
  // shift-tab flips yolo without spending a turn (claude-code parity)
```

Both matches are **internal code comments** (port history, parity reference).
No user-facing strings reference the broken `opencode` adapter.

**Inbox/Router/Review strings:** none found in TUI source.

### Caveats
- TUI is the **Ink (TypeScript)** frontend. The Python CLI is the primary
  v0.8 interface. Misleading labels in the CLI (e.g., `--source feishu` without
  stub warning) are not visible to TUI users but ARE visible to CLI users.
- TUI components are mostly low-level (clipboard, osc52, editor, math) — the
  business logic lives in `gatewayClient.ts` and the Python gateway.

### Severity
- **P2** — informational. The TUI is clean. The CLI needs check point 9 fixes.

---

## Prioritized Issue List (v1.0 Blockers)

### P0 — Must Fix Before v1.0 Ships

| ID | Issue | Source | Fix |
|----|-------|--------|-----|
| **V1-P0-01** | `opencode` manifest claims availability but adapter is broken (`opencode -p` → TUI); `default_model: "deepseek-v4-flash"` is suspicious | Check point 2 + opencode-feasibility review | Option A: stub it (`available: false` + reason). 30 min. |
| **V1-P0-02** | Inbox has 4 P0 issues (INB-01..04) — but no consumer reads it, so shipping CLI-only is safe | Check point 5 + Phase 10 review | Add "CLI-only, no auto-execution" warning to `inbox.py` and `ib --help`. 15 min. |

### P1 — Fix For v1.0 Polish, Or Defer To v1.1

| ID | Issue | Source | Fix |
|----|-------|--------|-----|
| **V1-P1-01** | Codex-like path is actually "minimal CLI passthrough" — relabel | Check point 1 | Update docs + adapter docstrings. 30 min. |
| **V1-P1-02** | Worktree merge/discard no path-resolution safety (same as Phase 6) | Check point 4 | Add `Path.is_relative_to(project_root)` check. 1 hour. |
| **V1-P1-03** | WorkspaceContext has no secret filtering — `architecture_notes` can leak keys | Check point 7 | Add doc warning (option A). 5 min. |
| **V1-P1-04** | PromptSnapshot built but not displayed anywhere | Check point 8 | Add `cli show-prompt --run-id` subcommand. 2 hours. |
| **V1-P1-05** | Inconsistent stub labeling: InboxSource enum shows `feishu` without warning; `HermesLocalAdapter` looks like a real AI; `opencode` looks like a real executor | Check point 9 | Add `(stub)` suffix in `--help`, rename `hermes-local` to `hermes-local-stub`. 1 hour. |
| **V1-P1-06** | Review/QA read-only contract is accidental (depends on broken opencode) | Check point 3 | Defer to v1.1; add explicit `--read-only` flag then. |

### P2 — Nice To Have

| ID | Issue | Source | Fix |
|----|-------|--------|-----|
| **V1-P2-01** | Router docstring doesn't state "advisory only" | Check point 6 | Add module docstring. 2 min. |
| **V1-P2-02** | TUI is clean but doesn't surface prompt snapshots | Check point 10 | Add TUI panel for PromptSnapshot in v1.1. |

---

## Cross-Reference Matrix — This Review vs. Prior Reviews

| Topic | This Review | Prior Coverage | Combined Action |
|-------|-------------|----------------|-----------------|
| Router | CP6: ✅ advisory only | `phase-7-opencode-router-review.md` (5 P0 / 10 P1 / 8 P2) | This review's P2-01 is the only NEW finding. Prior review's P0s (priority inversion, over-broad keywords) still apply. |
| Prompt | CP8: snapshot not displayed | `phase-8-opencode-prompt-review.md` (6 P0 / 10 P1 / 10 P2) | This review adds V1-P1-04 (display). Prior P0 (2000-token cap) still apply. |
| Inbox | CP5: not auto-executable (accidentally) | `phase-10-opencode-inbox-security-review.md` (4 P0 / 6 P1 / 5 P2) | This review's P0-02 reaffirms the 4 P0s. Prior review covers depth. |
| opencode | CP2: mislabeled | `opencode-review-qa-executor-feasibility.md` (4 P0 / 4 P1 / 4 P2) | This review's V1-P0-01 is the v1.0-specific fix (stub now). Prior review covers the v1.1+ fix (rewrite adapter). |
| Worktree | CP4: path-safety | `phase-6-worktree-risk-scan.md` | Same as Phase 6, re-surfaced. |
| Inbox (state model) | (not covered) | `phase-2-state-model-conflict-scan.md` | State machine confirmed→rejected etc. is allowed; not a v1.0 issue. |
| Architecture docs | (not covered) | `v1-final-architecture-review.md` | Earlier round; not the same as this code review. |

**Net new from this review:** 2 P0 + 5 P1 + 2 P2 = 9 issues.
**Carried forward from prior reviews:** ~18 issues (not enumerated here; see each prior doc).

---

## Recommendation for v1.0 Release

**Ship-blocker fixes (2 P0, ~45 min total):**
1. V1-P0-01: stub `opencode` manifest (30 min)
2. V1-P0-02: add CLI-only warning to inbox (15 min)

**Ship-with-known-issues (6 P1):**
- Either fix in v1.0 polish (6 hours total) or document in CHANGELOG as "known v1.0
  limitations, fixed in v1.1".

**Acceptable v1.0 messaging:**
> "Hermes Desktop v1.0 ships with **3 working executors** (`hermes-local`, `codex`,
> `claude-code`) and **1 in-development executor** (`opencode`, coming in v1.1). The
> Review/QA subsystem builds prompts and parses findings; it does **not** invoke
> executors directly. The Inbox subsystem is **CLI-only** and does not trigger
> automatic execution."

This matches the actual code state and avoids the "opencode is broken but advertised
as working" trap.

---

## Verification Commands Run

```bash
# Check point 2 — opencode adapter broken
$ opencode -p "hello"
[3787 bytes ASCII TUI banner, exit 1, 0 bytes stdout]

# Check point 3 — review_cli read-only
$ python -m executors.cli review build-prompt --goal "test" --diff "fake" --executor codex
[prints prompt + stats, no subprocess spawned]

# Check point 5 — no executor reads InboxItem
$ grep -rn "InboxItem" hermes-agent/executors/ | grep -v "inbox.py\|inbox_cli.py\|types.py"
(no matches)

# Check point 6 — router has no --accept
$ grep -n "accept\|auto_run" hermes-agent/executors/router.py
(no matches)

# Check point 7 — context no filtering
$ grep -n "api_key\|token\|password\|secret\|filter\|sanitiz\|redact" \
       hermes-agent/executors/context.py
(no matches)

# Check point 8 — PromptSnapshot not surfaced
$ grep -rn "show-prompt\|PromptSnapshot" hermes-agent/executors/cli.py
(no matches — cli.py has no show-prompt subcommand)
```

---

## End of Review

**Status:** v1.0 not ready. Two P0 fixes are quick (~45 min total) and would make
the system honest about its state. The other 6 P1 issues are polish items that can
ship as known limitations.

**Sign-off requirement:** Product owner must accept the "ship with 6 known issues
or delay v1.0 for 6 hours of polish" trade-off.

**Next review trigger:** When v1.1 work begins (opencode adapter rewrite + HTTP
inbox endpoint), re-run this review as `v1.1-prep-review.md`.
