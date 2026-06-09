# Phase 5B Design: Feishu Thread/Session Binding

## 1. Current Feishu Flow in This Repository

### Message flow

```
Feishu WebSocket event
  → FeishuAdapter._on_message_receive_v1()
  → FeishuAdapter._process_inbound_message()
  → extract text, media, mentions, thread_id
  → build SessionSource (platform, chat_id, chat_type, user_id, thread_id, chat_name)
  → build_session_key(source, group_sessions_per_user, thread_sessions_per_user)
  → record_feishu_session_binding(source, session_key)  # v2.10 sidecar
  → normalize to MessageEvent
  → dispatch to AIAgent / gateway runner
```

### Key file: `gateway/platforms/feishu.py` (5115 lines)

- `build_source()` constructs `SessionSource` dataclass (platform, chat_id, chat_type, user_id, thread_id, chat_name, user_id_alt, is_bot)
- `_process_inbound_message()` extracts `thread_id` from `message.thread_id` or `message.root_id`
- `build_session_key()` from `gateway/session.py` produces a key like `feishu:p2p:<hash>` or `feishu:group:<hash>`
- Card actions come through `_on_card_action_trigger()` and `_handle_card_action_event()`
- Approval buttons use `_handle_approval_card_action()` with `session_key` stored in card state
- `_FEISHU_ALLOWED_USERS` env var for sender allowlist

### Key file: `gateway/session.py`

- `SessionSource` dataclass: platform, chat_id, chat_name, chat_type, user_id, user_name, thread_id, user_id_alt, is_bot
- `build_session_key()` produces deterministic keys: `feishu:{peer_kind}:{hash(chat_id)}:{hash(user_id)}` with optional thread component
- `group_sessions_per_user` flag: True = per-user-per-group sessions, False = per-group sessions
- `thread_sessions_per_user` flag: True = per-user-per-thread sessions

### Key file: `gateway/platforms/feishu_session_binding_bridge.py` (62 lines)

- Sidecar: called from `_process_inbound_message()` after session_key is built
- Constructs raw payload from `SessionSource` and calls `FeishuEntryAdapter.normalize_event()`
- Calls `put_binding()` to record mapping
- Failures are caught and logged; main Feishu flow continues

### Key file: `agent/managed_agents/feishu_entry_adapter.py` (187 lines)

- `FeishuEntryAdapter` normalizes raw Feishu payloads into `EntryEvent`
- `_workspace_for()`: `tenant_id` → `ws-feishu-{tenant_id}`, fallback → `ws-feishu-{chat_id}`
- `_session_for()`: `session_key` → passthrough, `thread_id` → `ses-feishu-thread-{thread_id}`, fallback → `ses-feishu-{chat_id}`
- Required fields: `chat_id`, `message_id`, `open_id`, `content`
- Stateless: no I/O during resolution

### Card actions: approval buttons

- Three approval levels: `approve_once`, `approve_session`, `approve_always`
- `_approval_states` dict tracks `{approval_id: {session_key, message_id, chat_id}}`
- `resolve_gateway_approval(session_key, choice)` in gateway approval module
- Great pattern for explicit session selection — already exists and works

### What is NOT currently happening

1. **Thread replies** are received but not used to scope sessions differently from parent chat. `thread_id` is extracted but only used as part of session key hash — there is no `replyInThread` behavior.
2. **No per-group permission gate**. Only `FEISHU_ALLOWED_USERS` env var.
3. **No card-driven session selection**. Cards exist for approvals but not for "which session should this message go to?"
4. **No ambiguity detection**. When a message arrives in a group and could match multiple sessions, there is no ambiguity guard.

---

## 2. FeishuEntryAdapter Role from Phase 5A

### What Phase 5A established

- `FeishuEntryAdapter` is a **normalization-only** adapter
- It converts raw Feishu payloads → canonical `EntryEvent`
- It does NOT call agents, create tasks, route, or write ledger events
- Required fields: `chat_id`, `message_id`, `open_id`, `content`
- It maps `thread_id` / `root_id` → `external_thread_id`
- It maps `tenant_id` → `workspace_id`, `chat_id` → fallback workspace
- It produces `_workspace_for()` and `_session_for()` identifiers
- Registered in `EntryAdapterRegistry` with `entrypoint = "feishu"`
- Tested with mock payloads, not live Feishu events

### What it does NOT do

- Does NOT resolve which Hermes session should handle a message
- Does NOT decide whether a message should be processed at all
- Does NOT produce interactive card responses
- Does NOT detect or handle ambiguity

Phase 5B adds the resolution logic on top of Phase 5A's normalization.

---

## 3. Binding Model

### 3.1 Private chat → current-session binding

A private Feishu chat (p2p) maps 1:1 to a single Hermes session per user.

```
p2p chat (ou_A ↔ bot)
  → entrypoint=feishu, external_channel_id={dm_chat_id}
  → workspace_id = ws-feishu-{dm_chat_id}
  → session_id = ses-feishu-{dm_chat_id}
```

**Resolution**: `resolve_binding("feishu", external_channel_id=dm_chat_id, external_thread_id=None)` returns `(workspace_id, session_id)`.

**Current session**: If the user has been redirected to a different session (e.g., by card button), a binding overrides the default: `put_binding("feishu", dm_chat_id, None, workspace_id, overridden_session_id)`.

No ambiguity is possible in p2p chat — there is exactly one session per user per channel.

### 3.2 Group chat → workspace binding

A Feishu group chat (oc_xxx) maps to a Hermes workspace, not a single session.

```
group chat (oc_xxx)
  → entrypoint=feishu, external_channel_id=oc_xxx
  → workspace_id = ws-feishu-{oc_xxx}
  → session_id depends on message context (see below)
```

**Within a group**, the session depends on:
1. Thread ID — if the message is in a Feishu thread
2. Explicit card selection — if the user chose a session via card button
3. Default — the group's workspace-level default session

### 3.3 Thread/root-message → session binding

Feishu threads provide natural session isolation within a group.

```
group chat (oc_xxx) + thread (om_thread123)
  → entrypoint=feishu, external_channel_id=oc_xxx, external_thread_id=om_thread123
  → workspace_id = ws-feishu-{oc_xxx}
  → session_id = ses-feishu-thread-{om_thread123}
```

**Resolution**: `resolve_binding("feishu", oc_xxx, om_thread123)` returns `(ws-feishu-{oc_xxx}, ses-feishu-thread-{om_thread123})`.

When `thread_sessions_per_user=False` (current default), all users in the same thread share one session. When `thread_sessions_per_user=True`, each user gets their own session within the thread.

### 3.4 Card button → explicit session binding

Hermes already has interactive card button infrastructure for approvals. Phase 5B extends this to allow card-driven session selection.

**Pattern**:

```
Interactive card: "Which task should this message go to?"
  → Button 1: "Task A (impl)" → session_id = ses-abc123
  → Button 2: "Task B (review)" → session_id = ses-def456
  → Button 3: "New task" → triggers new task flow
```

When a user taps a button:
- `card_action_trigger` event arrives with `action.value = {action: "select_session", session_id: "ses-abc123"}`
- Hermes resolves the explicit session binding
- `put_binding("feishu", oc_xxx, om_thread_or_none, ws-feishu-{oc_xxx}, ses-abc123)` is written
- Future messages in that group/thread are routed to the selected session

**Override scope**: The binding should be scoped to `(entrypoint, external_channel_id, external_thread_id)`. A new thread or a new p2p chat does NOT inherit the override.

---

## 4. Resolution Order

When a Feishu message arrives, the session is resolved in this priority order:

```
1. Explicit card session_id
   → User tapped a card button that specified a session_id.
   → Look up: get_binding("feishu", channel_id, thread_id)
   → If found, use it directly.

2. Explicit alias
   → Reserved for future: "/task abc123" command sets session.
   → Not yet implemented; placeholder in resolution chain.

3. Private current-session binding
   → For p2p chats only.
   → get_binding("feishu", dm_chat_id, None)
   → If a binding exists from a card button or previous redirection, use it.
   → Otherwise, fall through to next rule.

4. Thread/root-message binding
   → If message has thread_id or root_id:
     get_binding("feishu", chat_id, thread_id)
     → If found, use it.
     → Otherwise, derive: ses-feishu-thread-{thread_id}

5. Group workspace binding
   → For group chats without thread context:
     get_binding("feishu", chat_id, None)
     → If found, use it.
     → Otherwise, derive: ses-feishu-{chat_id}

6. Ambiguity card
   → If in a group chat with multiple active sessions for the same workspace,
     AND no explicit binding exists,
     AND no thread context:
     → Send an interactive card asking the user to select a session.
     → Do NOT pick a default session silently.

7. Reject / no global fallback
   → If none of the above resolve, use the default:
     workspace_id = DEFAULT_WORKSPACE_ID ("hermes-local")
     session_id = DEFAULT_SESSION_ID ("hermes-legacy")
   → Do NOT silently redirect to another user's session.
   → Do NOT create a global "all group messages" session.
```

**Key principle**: Never silently choose a session. If the context is ambiguous, send an ambiguity card.

---

## 5. SessionBinding Key Format

### Current format (v2.10)

```
"{entrypoint}:{external_channel_id}:{external_thread_id}"
```

Examples:
- `"feishu:oc_abc123:"` — group chat, no thread
- `"feishu:oc_abc123:om_thread456"` — group chat with thread
- `"feishu:ou_dm789:"` — private chat

### Proposed extensions for 5B

1. **Add `external_user_id` dimension** for per-user sessions:

```
"{entrypoint}:{external_channel_id}:{external_thread_id}:{external_user_id}"
```

But ONLY when `thread_sessions_per_user=True` or `group_sessions_per_user=True`. When these flags are False, the user dimension is omitted for backward compatibility.

2. **Binding value includes session metadata**:

```python
@dataclass(frozen=True)
class SessionBindingValue:
    workspace_id: str
    session_id: str
    source: Literal["card", "thread", "alias", "default"]
    created_at: str
```

This allows the dashboard to show WHY a session was bound (card selection vs thread vs default).

### Migration

- Existing bindings file (`data/session_bindings.json`) uses `tuple[workspace_id, session_id]` values
- New bindings add `source` and `created_at` fields
- Read path: if value is a 2-tuple, fill defaults; if value is a dict, use new fields
- Write path: always write new format
- Backward compatible: 2-tuple values still resolve correctly

---

## 6. Legacy Compatibility

### Compatibility requirements

1. **Existing session keys must continue to work**: `feishu:p2p:<hash>` and `feishu:group:<hash>` produced by `build_session_key()` must still resolve to the correct sessions.

2. **Missing session bindings fall back to defaults**: `resolve_binding()` returns `(DEFAULT_WORKSPACE_ID, DEFAULT_SESSION_ID)` when no binding exists.

3. **Sidecar must remain non-critical**: `record_feishu_session_binding()` is wrapped in `try/except`. Failures must not break the main Feishu message flow.

4. **No double-dispatch**: A message must be processed exactly once, regardless of whether the sidecar succeeds or fails.

5. **Old binding file format**: `data/session_bindings.json` with 2-tuple values must be readable by the new code.

### What changes

- `SessionBindingValue` replaces plain tuples (backward compatible read)
- `resolve_binding()` gains a `source` field in its return value
- Card button handler gains a "select_session" action type
- Ambiguity detection is a pure new addition, no existing behavior changes

---

## 7. No Double-Dispatch Strategy

### Risk

When the Feishu adapter processes a message, it:
1. Builds `SessionSource` → `session_key`
2. Calls `record_feishu_session_binding()` (sidecar)
3. Dispatches to `AIAgent` / gateway runner

If the sidecar somehow triggers a second dispatch (e.g., by writing a binding that causes a re-process), we get double-dispatch.

### Prevention

1. **Sidecar is write-only**: `record_feishu_session_binding()` only writes to the binding store. It does NOT produce new events or trigger new dispatches.
2. **Binding read is lazy**: `resolve_binding()` is only called when the next message arrives, never retroactively.
3. **Message dedup**: `feishu_seen_message_ids.json` already prevents the same `message_id` from being processed twice. The sidecar does not bypass this.
4. **Card actions are single-shot**: `_is_card_action_duplicate()` already deduplicates card button taps within `_FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS` seconds.

### Additional safeguard for 5B

- Each card action should include a `dedupe_token` (e.g., message_id + timestamp hash)
- The binding write should be idempotent: writing the same binding twice has no effect

---

## 8. How to Avoid Touching the 5101-line Feishu Transport Too Much

### What we can do WITHOUT modifying `feishu.py`

1. **Extend `feishu_session_binding_bridge.py`**: Add resolution logic, ambiguity detection, and card session selection to the bridge, not the transport.

2. **Extend `FeishuEntryAdapter`**: Add `resolve_session_with_ambiguity()` method that implements the full resolution chain.

3. **Add a new `feishu_session_resolver.py`**: Pure function module that takes `EntryEvent` + `SessionBinding` store → resolved `(workspace_id, session_id)` + `ambiguity_detected: bool`.

4. **Add card templates**: New `feishu_session_cards.py` module that builds interactive card JSON for session selection. Called from the card action handler, not from the main message flow.

### What requires minimal modification to `feishu.py`

1. **Card action handler**: Add a `"select_session"` action type to `_handle_card_action_event()`. This is ~10 lines.

2. **Ambiguity hook**: In `_process_inbound_message()`, after the sidecar call, add an optional call to the resolver. If ambiguity is detected, send an interactive card instead of dispatching to the agent. This is ~20 lines.

3. **Thread reply support**: In the send path, when `source.thread_id` is present, set `replyInThread=True`. This requires understanding how the Feishu API's thread reply works, which is a separate concern from this design but should be noted.

### Total touch estimate

- `feishu.py`: ~30-50 lines of changes (card action + ambiguity hook + thread reply flag)
- New files: `feishu_session_resolver.py` (~200 lines), `feishu_session_cards.py` (~100 lines)
- Modified files: `feishu_session_binding_bridge.py` (~50 lines added), `session_binding.py` (~80 lines added for `SessionBindingValue`)

---

## 9. Implementation Slices

### 5B1: Binding helpers

**Goal**: Extend `SessionBindingValue` and key format.

**Files**:
- `agent/managed_agents/session_binding.py` — add `SessionBindingValue` dataclass, extend `put_binding()` and `resolve_binding()`, backward compatible read
- `agent/managed_agents/feishu_entry_adapter.py` — add `resolve_session_with_ambiguity()` method

**Changes**:
- `put_binding()` signature adds `source` and `created_at` parameters (both optional, defaults to "default" and ISO timestamp)
- `resolve_binding()` returns `SessionBindingValue` instead of plain tuple; callers that only need `(workspace_id, session_id)` can destructure
- Reading old format: if value in file is a 2-list, construct `SessionBindingValue(source="default", created_at="")`
- `resolve_session_with_ambiguity()`: implements full resolution chain from section 4, returns `(SessionBindingValue | None, ambiguous: bool)`

**Tests**:
- `put_binding` writes new format, reads old format
- `resolve_binding` returns default when no binding exists
- `resolve_session_with_ambiguity` returns correct priority for each resolution level
- Card binding takes precedence over thread binding over workspace binding

### 5B2: Resolver tests

**Goal**: Test the full resolution chain with realistic Feishu payloads.

**Files**:
- `tests/agent/test_feishu_session_resolver.py` — new test file

**Test cases**:

| # | Scenario | Input | Expected |
|---|----------|-------|----------|
| 1 | Private chat, no prior binding | p2p, ou_dm123, no thread | workspace=default, session=default, ambiguous=False |
| 2 | Private chat, card binding exists | p2p, ou_dm123, binding from card | workspace=card_ws, session=card_ses, ambiguous=False |
| 3 | Group chat, no thread, no binding | group, oc_abc, no thread | workspace=derived, session=derived, ambiguous=True if multiple sessions |
| 4 | Group chat, thread context | group, oc_abc, om_thread456 | workspace=derived, session=thread-derived, ambiguous=False |
| 5 | Group chat, card binding exists | group, oc_abc, binding from card | workspace=card_ws, session=card_ses, ambiguous=False |
| 6 | Group chat, multiple active sessions, no thread | group, oc_abc, no binding, 3 active sessions | ambiguity card should be sent |
| 7 | Legacy tuple binding | old format in store | resolves correctly with source="default" |

### 5B3: Optional bridge into existing Feishu transport

**Goal**: Wire the resolver into the existing message flow with minimal changes to `feishu.py`.

**Files**:
- `gateway/platforms/feishu_session_binding_bridge.py` — extend `record_feishu_session_binding()` to also call the resolver; add `check_ambiguity()` function
- `gateway/platforms/feishu.py` — add `select_session` card action handler (~10 lines) and ambiguity hook (~20 lines)

**Changes to `feishu.py`**:
1. In `_process_inbound_message()`, after the sidecar call, add:
   ```python
   from gateway.platforms.feishu_session_binding_bridge import check_ambiguity
   ambiguity = check_ambiguity(source, session_key)
   if ambiguity.needs_card:
       await self._send_ambiguity_card(chat_id, message_id, ambiguity.sessions)
       return  # do not dispatch to agent
   ```
2. In `_handle_card_action_event()`, add:
   ```python
   if action_type == "select_session":
       # resolve session_id from card action value
       # call put_binding with source="card"
       # acknowledge and proceed
   ```

**Tests**:
- `_process_inbound_message` does not dispatch when ambiguity card is sent
- `_handle_card_action_event` for `select_session` writes binding with source="card"
- Sidecar failure does not prevent ambiguity check
- Sidecar failure does not cause double-dispatch

---

## 10. Tests Required

### Unit tests (5B1)

| Test | Module | Validates |
|------|--------|-----------|
| `test_session_binding_value_new_format` | `session_binding` | `SessionBindingValue` serialization/deserialization |
| `test_session_binding_value_old_format` | `session_binding` | Reading 2-tuple values as `SessionBindingValue(source="default")` |
| `test_put_binding_with_source` | `session_binding` | `put_binding` with `source="card"` |
| `test_resolve_binding_missing` | `session_binding` | Returns default when no binding |
| `test_resolve_binding_card_overrides_thread` | `session_binding` | Card binding takes priority |
| `test_resolve_session_p2p_no_binding` | `feishu_entry_adapter` | p2p chat without prior binding |
| `test_resolve_session_p2p_with_card_binding` | `feishu_entry_adapter` | p2p chat with card override |
| `test_resolve_session_group_with_thread` | `feishu_entry_adapter` | Group + thread resolves to thread session |
| `test_resolve_session_ambiguity_detected` | `feishu_entry_adapter` | Group + no thread + multiple sessions = ambiguous |
| `test_resolve_session_no_ambiguity_single` | `feishu_entry_adapter` | Group + no binding + one session = not ambiguous |

### Integration tests (5B2)

| Test | Validates |
|------|-----------|
| `test_resolver_full_chain_explicit_card` | Card binding wins over all other signals |
| `test_resolver_full_chain_thread` | Thread binding derived when no card binding |
| `test_resolver_full_chain_group_default` | Group binding derived when no thread or card |
| `test_resolver_legacy_binding_compatibility` | Old tuple format reads correctly |

### Bridge integration tests (5B3)

| Test | Validates |
|------|-----------|
| `test_ambiguity_card_sent` | Group message with multiple sessions sends card |
| `test_select_session_card_action` | Card action writes binding with source="card" |
| `test_no_double_dispatch_on_sidecar_failure` | Sidecar error does not cause re-processing |
| `test_thread_reply_session_binding` | Thread message records thread-level binding |

---

## 11. Risks

### Low risk

- **`SessionBindingValue` migration**: Backward compatible read, additive write. Old bindings continue to work.
- **`FeishuEntryAdapter` resolution additions**: Pure function, no I/O, no side effects.
- **Resolver module**: New file, no existing code changes.

### Medium risk

- **Card action handler in `feishu.py`**: Adding a new `action_type` to `_handle_card_action_event()`. Existing card actions (approve, update_prompt) must not be affected. Requires careful testing of the card dedup logic.
- **Ambiguity hook in `_process_inbound_message()`**: Must return early when ambiguity card is sent, preventing dispatch to agent. Must not return early when there is no ambiguity.
- **Thread reply support**: Feishu's `replyInThread` API may require changes to the send path. Implementation details need verification against Feishu SDK docs.

### High risk

- **Group session ambiguity detection in production**: Detecting "multiple active sessions for the same workspace" requires querying the Run Ledger, which is not currently accessible from the Feishu transport. The ambiguity check must be behind a feature flag and default to off.
- **Card button state consistency**: If a user selects a session via card, but the binding store is not yet persisted when the next message arrives, the wrong session may be selected. Requires filesystem sync before card acknowledgment.

### Mitigations

1. **Feature flag**: `FEISHU_AMBIGUITY_CARD_ENABLED=false` by default. When false, group messages without thread use the default session (current behavior).
2. **Sync write**: `put_binding()` uses synchronous file write. Card action handler should not acknowledge until write is confirmed.
3. **Thread reply is optional**: Even without `replyInThread`, thread context correctly scopes sessions. Reply-in-thread is a UX improvement, not a correctness requirement.

---

## 12. Go / No-Go Recommendation

### Go for 5B

The design is safe to implement because:

1. **No existing behavior changes by default**: The sidecar already runs. 5B1 (binding value extension) is additive. 5B2 (resolver tests) is new test code. 5B3 (bridge integration) is behind feature flags.

2. **The resolution chain is deterministic**: There is always a correct answer — card binding wins, then thread, then group, then ambiguity card, then default. No randomness, no silent fallthrough.

3. **The Feishu transport is touched minimally**: ~30-50 lines of additions, no deletions, no refactoring.

4. **Legacy compatibility is preserved**: Old binding format reads correctly. Missing bindings fall back to defaults. Sidecar failures are non-critical.

### No-go conditions

- Do NOT implement if the Run Ledger cannot be queried from the resolver (needed for ambiguity detection). **Mitigation**: behind feature flag, default off.
- Do NOT implement if card action dedup is unreliable. **Mitigation**: verify existing dedup works before adding new action types.
- Do NOT implement thread reply (`replyInThread`) without verifying Feishu SDK API support. **Mitigation**: thread-scoped session resolution works without reply-in-thread.

### Implementation order

| Slice | Estimated effort | Risk | Dependencies |
|-------|-----------------|------|-------------|
| 5B1 | 2-3 hours | Low | None |
| 5B2 | 1-2 hours | Low | 5B1 |
| 5B3 | 3-4 hours | Medium | 5B1, 5B2, feature flag |

**Recommendation**: Start with 5B1, verify tests pass, then 5B2, then 5B3 with feature flag disabled. Enable feature flag only after integration testing.
