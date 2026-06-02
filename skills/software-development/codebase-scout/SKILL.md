---
name: codebase-scout
description: "Fast, scoped codebase scouting before multi-file edits, debugging, or delegation."
version: 1.0.0
author: Hermes Agent (adapted from withkynam/vibecode-pro-max-kit vc-scout)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [scout, codebase, discovery, grep, rg, delegation, context]
    related_skills: [codebase-inspection, systematic-debugging, spike]
agents:
- deepseek-tui
- claude
- codex
- hermes-internal
---

# Codebase Scout

Use this skill before work that may touch multiple files, multiple packages, or unclear ownership boundaries. The goal is to return a small, factual map of relevant files and open questions before anyone edits code.

This is a Hermes adaptation of `vc-scout` from `withkynam/vibecode-pro-max-kit`. It does not import Flowser/RIPER agents or process folders.

## When To Use

- User asks where behavior lives.
- A bug may span several layers.
- A task mentions routing, config, model, gateway, WebUI, Agent, skill, or MCP and the exact files are not known.
- Before delegating to Claude Code or DeepSeek-TUI for implementation.
- Before reviewing a large diff when changed files are not enough to understand impact.

Skip for single-file trivial edits where the target file is already known.

## Workflow

1. Restate the search target in one sentence.
2. Run local search first:
   ```bash
   rg "symbol_or_error" .
   rg --files | rg "keyword|directory|extension"
   git grep "symbol_or_error"
   ```
3. Read only the top relevant files. Prefer entrypoints, config files, tests, and callers.
4. If the scope is large, split by directory and ask another Agent for a read-only scan. Each subtask must include exact directories and a strict "do not modify files" constraint.
5. Return a scout report. Do not propose a fix unless the user asked for implementation.

## Scout Report Format

```markdown
## Scope
[What was searched]

## Relevant Files
- `path` - why it matters

## Relationships
- `A` calls/loads/generates `B`

## Risks
- [config drift, stale tests, unclear ownership, etc.]

## Open Questions
- [only questions that block safe implementation]
```

## Delegation Pattern

For DeepSeek-TUI:

```text
Read-only scout. Do not modify files.
Search target: ...
Directories: ...
Return only: relevant files, relationships, risks, open questions.
Follow the DeepSeek Worker Search Policy.
```

For Claude Code:

```text
Read-only scout. Use Read/Grep/Glob only.
Search target: ...
Do not edit files or run destructive commands.
Return a concise scout report.
```
