# Feishu Agent Entry Reference Comparison

Comparative analysis of Lark/Feishu multi-agent entry patterns to decide whether Hermes can stay Feishu-first without introducing Discord as a primary IM.

Date: 2026-06-03

---

## 1. Project Summaries

| Project | Language | Description | Status |
|---------|----------|-------------|--------|
| **larksuite/openclaw-lark** | TypeScript | Official OpenClaw Feishu channel plugin. Single-agent, production-grade Feishu integration with streaming cards, interactive cards, allowlist/gate policies, per-group config, comment handling, reaction events. | Active, by ByteDance |
| **hyperlist/feishu-multi-agent** | Markdown/Skills | Configuration guide for running multiple OpenClaw agents behind one Feishu bot. Uses OpenClaw's built-in `bindings` for group-to-agent routing. No custom runtime. | Active, documentation-only |
| **hackerphysics/openclaw-lark-multi-agent** | TypeScript | Bridge layer: multiple Lark/Feishu bot apps → one OpenClaw Gateway. Per-bot model binding, per-chat session isolation (`lma-<bot>-<chatId>`), discussion mode (`/discuss`), chairman role, message dedup, durability. | Active, bridge |
| **langbot-app/LangBot** | Python | Multi-platform chat bot framework (Feishu, QQ, Discord, Telegram, WeChat, DingTalk, Slack, etc.). Plugin-based architecture with `AbstractMessagePlatformAdapter`, YAML config per platform. Feishu is one of many adapters. | Active, framework |

---

## 2. DM vs Group Chat Handling

### OpenClaw Lark (official)

- **Two-layer policy model**: Layer 1 checks which groups are allowed (groupPolicy: `open` / `allowlist` / `disabled`). Layer 2 checks which senders are allowed within a group (merged allowlist from global + per-group + default).
- **DM policy**: Separate `dmPolicy: "allowlist"` with its own `dm.allowFrom` list. Users not on the list get a pairing reply asking them to request access.
- **Mention gating in groups**: `requireMention` flag controls whether bot responds only when @mentioned. `respondToMentionAll` controls whether @all/@everyone triggers the bot.
- **Bot self-filter**: Bot's own messages are filtered out at the gate level.

### OpenClaw-Lark-Multi-Agent (bridge)

- **Per-bot identity**: Each bot app has its own `appId` / `appSecret`. DM routing is per-user per-bot.
- **Targeted mention**: When someone @mentions a specific bot by name, only that bot handles it. Other bots in Free mode skip the message.
- **Mention-only trigger**: Bots can be configured to respond only when mentioned, preventing free-for-all group chat chaos.
- **Anti-loop**: Each bot has its own streak counter. One bot's budget does not affect another.

### Feishu-Multi-Agent (config guide)

- **Binding model**: `match.peer.kind = "group"` or `"dm"` with explicit `oc_xxx` / `ou_xxx` IDs. One group → one agent.
- **DM isolation**: Different users can be routed to different agents via DM bindings.
- **No cross-binding**: One group cannot bind to multiple agents simultaneously.

### LangBot

- **Platform abstraction**: Feishu is just one `AbstractPlatformAdapter`. DM vs group is handled in the adapter layer, with routing decided by the pipeline (configurable per-platform).
- **No built-in allowlist**: Permission model is simpler — relies on Feishu app scope and platform settings rather than a two-layer gate.

### Hermes (current)

- **Session key model**: `build_session_key()` produces a key based on chat_id, user_id, and thread_id. Group and DM use the same key structure but different `peer_kind`.
- **WebSocket long connection**: Feishu adapter uses `lark_oapi` WebSocket for message receive.
- **Approval buttons**: Hermes has interactive card buttons for approve/deny actions (e.g., session approval, command confirmation).
- **Allowlist**: `FEISHU_ALLOWED_USERS` env var for sender filtering.

---

## 3. Thread/Reply Support

### OpenClaw Lark (official)

- **Thread support**: Feishu threads (`thread_id`, `root_id`) are fully parsed. `replyInThread` option sends responses as thread replies.
- **Thread-scoped sessions**: `threadSessionKey` derived from `chatId:threadId` or `chatId:threadId:userId` for per-thread isolation.
- **Topic thread**: Messages with `root_id` but no `thread_id` are treated as topic replies.

### OpenClaw-Lark-Multi-Agent (bridge)

- **Thread capability check**: `isThreadCapableGroup()` determines if a group supports threads.
- **Per-bot thread session**: Each bot in a thread gets its own session key, preventing cross-bot context pollution.

### Feishu-Multi-Agent (config guide)

- **No explicit thread model**: Session keys are `agent:{agent_id}:{channel}:{peer_kind}:{peer_id}`. Thread-level isolation is not described.

### Hermes (current)

- **Thread ID extraction**: `feishu_session_binding_bridge.py` extracts `thread_id` from `SessionSource` and maps it to `external_thread_id` in `EntryEvent`.
- **Session binding**: Thread ID feeds into `_session_for()` resolution — threads can map to separate sessions or be grouped under the same chat session.
- **Gap**: Current Feishu adapter references `thread_id` but the full thread-scoped reply behavior (replying within a Feishu thread rather than the main chat) is not yet implemented.

---

## 4. Interactive Card Support

### OpenClaw Lark (official)

- **CardKit v2**: Full support for Feishu's interactive card protocol. Cards have states: `thinking` → `streaming` → `completed`.
- **Streaming cards**: Real-time typewriter effect via `StreamingCardController`. Card content is updated in-place using Feishu's `cardElement.content()` API.
- **Interactive buttons**: Card action events (`card.action.trigger`) are dispatched through a plugin interactive handler pipeline. Actions carry `namespace`, `action`, and `payload`.
- **Reasoning display**: Built-in support for `<thinking>` / `Reasoning:` blocks, shown in a separate collapsible section within the card.
- **Tool use display**: Step-by-step tool use traces rendered as interactive card elements.
- **Markdown normalization**: Extensive style pipeline converts agent markdown into Feishu-compatible markdown (table mode, mention normalization, link handling).

### OpenClaw-Lark-Multi-Agent (bridge)

- **Delegates to OpenClaw**: Card rendering is handled by the underlying OpenClaw Gateway. The bridge layer does not manage card lifecycle.
- **Markdown rendering**: Uses `buildFeishuCardElements` for markdown-to-card conversion.

### Hermes (current)

- **Card buttons**: Hermes uses interactive card buttons for approval flows (approve/deny session, confirm/resolve command). This is a targeted use, not full CardKit.
- **No streaming cards**: Agent responses are sent as plain text or markdown cards, not with the typewriter streaming effect.
- **No tool-use card rendering**: Tool calls are not visually presented as interactive card steps.

---

## 5. Binding/Session Model

| Project | Session Key | Isolation Level | Multi-Agent |
|---------|-------------|-----------------|-------------|
| OpenClaw Lark | `session:{accountId}:{chatId}` with optional `:threadId` or `:threadId:userId` | Per-chat or per-thread-per-user | Single agent per session |
| OpenClaw-Lark-Multi-Agent | `lma-<botname>-<chatId>` | Per-bot-per-chat | Multi-bot, each with own session |
| Feishu-Multi-Agent | `agent:{agent_id}:{channel}:{peer_kind}:{peer_id}` | Per-agent-per-peer | Multi-agent via Binding config |
| LangBot | Platform-specific | Per-bot-per-chat | Multi-platform multi-bot |
| **Hermes (v2.10)** | `EntryEvent.session_id` + `SessionBinding` | Per-entrypoint-per-thread | Multi-agent via managed_agents |

### Key Insight

Hermes v2.10's `SessionBinding` model is already more general than any of the reference projects. `EntryEvent` captures `entrypoint`, `external_channel_id`, `external_thread_id`, and `external_user_id` independently, which allows:

- Workspace = `tenant_id` or `chat_id`-derived namespace
- Session = thread-specific or chat-specific
- Cross-entrypoint session resolution (e.g., Feishu thread → CLI session for the same task)

---

## 6. Permission/Allowlist Model

### OpenClaw Lark (official)

```
Layer 1: groupPolicy → "open" | "allowlist" | "disabled"
  ↓
Layer 2: groupAllowFrom → ["*"] | ["ou_xxx", ...]
  ↓
Per-group override: groups.<oc_xxx>.allowFrom
DM: dmPolicy + dm.allowFrom
```

- `open`: any group/sender allowed
- `allowlist`: explicit list of group IDs and/or sender open_ids
- `disabled`: block all group access
- Pairing: unknown DM users get a "request access" interactive card

### OpenClaw-Lark-Multi-Agent (bridge)

- Per-bot `requireMention` and Free-mode
- Targeted mentions are exclusive: @BotA does not trigger BotB
- Bot self-filtering is per-bot, not global

### Hermes (current)

- `FEISHU_ALLOWED_USERS` env var for simple allowlist
- Approval buttons for session-level authorization
- No per-group policy beyond the env var
- v2.10 EntryAdapter has no built-in permission gate — it normalizes and defers to the Feishu transport adapter's existing gate

---

## 7. Notification/Approval Patterns

### OpenClaw Lark (official)

- **Approval is SDK-level**: OpenClaw plugin SDK provides framework for approval gates, but the official Feishu plugin does not implement a separate approval card pattern.
- **Confirmation cards**: OpenClaw supports `confirm` card state for sensitive operations. `ConfirmData` includes `operationDescription`, `pendingOperationId`, and optional `preview`.

### OpenClaw-Lark-Multi-Agent (bridge)

- **Slash commands**: `/discuss`, `/chairman`, `/locale`, `/status` are bridge-level commands processed before forwarding to OpenClaw.
- **No approval cards**: Approval is delegated to the underlying OpenClaw agent runtime.

### Hermes (current)

- **Approval buttons**: Feishu interactive card buttons for approve/deny. State tracked in `FeishuAdapter` memory (`_approval_states`, `_update_prompt_states`).
- **Real approval flow**: When a user taps "Approve" or "Deny", the Feishu adapter resolves it and releases the pending action. This is already more mature than the reference projects for notification/approval use cases.

---

## 8. What Hermes Should Borrow

### High-value patterns

1. **Two-layer permission gate** (from OpenClaw Lark): Replace `FEISHU_ALLOWED_USERS` env var with a proper `groupPolicy` + `groupAllowFrom` model. Per-group config is much more usable than a flat env var.

2. **Streaming card rendering** (from OpenClaw Lark): The CardKit v2 streaming-card lifecycle (`thinking` → `streaming` → `completed`) is a significantly better UX for long-running agent responses. Hermes currently sends plain text; streaming cards would dramatically improve the Feishu experience.

3. **Thread-scoped sessions** (from OpenClaw Lark): `threadSessionKey` = `chatId:threadId` or `chatId:threadId:userId`. This maps well to Hermes's existing `external_thread_id` field in `EntryEvent`.

4. **Per-group configuration** (from OpenClaw Lark): `groups.<oc_xxx>.{enabled, requireMention, allowFrom, respondToMentionAll}` is more granular than a global env var.

5. **Mention-aware routing** (from OpenClaw-Lark-Multi-Agent): When multiple agents serve the same Feishu space, `@mention` should be the routing signal. Not needed right now but the pattern is worth preserving in the EntryAdapter.

### Medium-value patterns

6. **Discussion mode** (from OpenClaw-Lark-Multi-Agent): The `/discuss` + chairman pattern is interesting for Hermes multi-agent coordination, but should be a Phase 6+ feature, not a current priority.

7. **Message deduplication** (from OpenClaw-Lark-Multi-Agent): The `delivered_replies` + `pending_triggers` pattern prevents duplicate processing on restart. Hermes already has `feishu_seen_message_ids.json` but the bridge's approach is more formal.

8. **Comment handling** (from OpenClaw Lark): Drive/doc comment events as a synthetic message source. Hermes doesn't currently handle Feishu doc comments.

---

## 9. What Hermes Should Avoid

1. **Dependence on OpenClaw SDK runtime**: OpenClaw's plugin architecture (`openclaw/plugin-sdk`) is deeply integrated. Hermes should not import or depend on it. The reference value is the pattern, not the code.

2. **Global admin open_id for model-drift notifications**: The bridge's pattern of a single `adminOpenId` for error notifications is not a good fit for Hermes's multi-agent architecture.

3. **Flat session key construction**: `lma-<bot>-<chatId>` is too rigid. Hermes's `SessionBinding` with `workspace_id` / `session_id` / `entrypoint` is already more flexible.

4. **Replacing existing transport**: Hermes's Feishu adapter (`gateway/platforms/feishu.py`, 5115 lines) is mature and battle-tested. The OpenClaw pattern should inform functionality additions, not replace the transport layer.

5. **CardKit v2 protocol dependency**: While streaming cards are valuable, Hermes should not lock into Feishu's specific card protocol version. Abstract behind a response renderer interface.

6. **LangBot's flat platform abstraction**: LangBot treats all platforms equally with `AbstractPlatformAdapter`. This flattening loses Feishu-specific capabilities. Hermes's EntryAdapter approach (preserving `external_thread_id`, `tenant_id`, etc.) is better.

---

## 10. Recommendation for Phase 5B / 5C

### Can Hermes stay Feishu-first without Discord?

**Yes, definitively.** The comparison shows:

1. **Feishu has all the building blocks**: Thread support, interactive cards, per-group policy, session isolation, approval patterns are all native Feishu capabilities. Discord adds nothing Hermes cannot achieve with Feishu.

2. **Feishu is the richer platform**: Thread support, interactive cards, approval buttons, comment events, per-group config — Feishu's API surface is wider than Discord's for the specific use case of agent orchestration.

3. **The real gap is implementation, not platform**: What's missing in Hermes is not a different IM — it's streaming cards, per-group policy, and thread-scoped replies. These are Feishu features, not Discord features.

### Phase 5B: Feishu session binding integration

**Recommended scope:**

1. Wire `FeishuEntryAdapter` → existing `feishu_session_binding_bridge.py` → `SessionBinding` store. This is already 80% done.
2. Map `chat_id` → `external_channel_id`, `thread_id` → `external_thread_id`, `open_id` → `external_user_id`. Already defined in `EntryEvent`.
3. Keep Feishu transport (`gateway/platforms/feishu.py`) untouched. The sidecar architecture is correct.

### Phase 5C: Feishu UX enhancements (not part of current plan, but for planning)

**Future improvements that close the UX gap with OpenClaw:**

1. **Streaming card support**: Implement `thinking` → `streaming` → `completed` lifecycle using Feishu CardKit v2 API. This is the single biggest UX improvement possible.

2. **Two-layer permission gate**: Replace `FEISHU_ALLOWED_USERS` with `groupPolicy` + `groupAllowFrom` config, similar to OpenClaw's two-layer model.

3. **Thread-scoped sessions**: When `thread_id` is present, reply within the Feishu thread rather than in the main chat. This requires `replyInThread` support in the Feishu adapter.

4. **Per-group config**: Allow individual groups to have different `requireMention`, `allowFrom`, and `respondToMentionAll` settings.

5. **Comment event handling**: Add `drive.notice.comment_add_v1` event support for doc/wiki comment responses.

### Discord assessment: Not needed for now

Discord is a viable future adapter (Phase 8+) for users who prefer it. But it should not be the primary IM. Feishu provides:

- Better thread/topic isolation for multi-agent contexts
- Better interactive card support for approval/confirmation flows
- Better per-group permission control
- Native integration with the Chinese work environment where Hermes's users operate
- Already-deployed infrastructure (马尔蒂尼 bot, Feishu gateway, approval buttons)

Discord's advantage — channel/thread hierarchy — can be replicated in Feishu via thread IDs and topic-based session. Feishu's advantage — interactive cards for approval — is much harder to replicate in Discord.

**Resolution: Stay Feishu-first. Add Discord as an optional entry adapter in Phase 8+, not as a co-primary.**

---

## Appendix: Reference file mapping

| Pattern | OpenClaw Lark file | OpenClaw-Lark-Multi-Agent file | Hermes equivalent |
|---------|-------------------|-------------------------------|-------------------|
| Permission gate | `src/messaging/inbound/gate.ts` | (delegated to OpenClaw) | `FEISHU_ALLOWED_USERS` env var |
| Session key | `reply-dispatcher.ts` → sessionKey | `feishu-bot.ts` → `lma-<bot>-<chatId>` | `gateway/session.py` → `build_session_key()` |
| Interactive cards | `src/card/builder.ts`, `streaming-card-controller.ts` | (delegated) | `feishu.py` → card button handlers |
| Binding config | `src/channel/config-adapter.ts` | `config.json` → bindings | `agents.yaml` |
| Thread support | `dispatch.ts` → `resolveThreadSessionKey` | `feishu-bot.ts` → per-chat session | `feishu_session_binding_bridge.py` |
| Discussion mode | N/A | `discussion-manager.ts` | Not yet implemented |
| Message dedup | `src/messaging/inbound/dedup.ts` | `message-store.ts` → SQLite | `feishu_seen_message_ids.json` |
