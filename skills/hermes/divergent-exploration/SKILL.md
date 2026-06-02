---
name: divergent-exploration
description: "Hermes divergent exploration mode — for open-ended, high-stakes strategy, architecture, naming, API design, fuzzy debugging, and \"multiple different approaches\" requests. Runs isolated parallel frame exploration before convergence, using Intelligence for divergence and Pirlo/Ambrosini for scoring, clustering, and trap review."
tags: [hermes, reasoning, divergent-thinking, multi-agent, strategy, architecture]
agents: [hermes]
---

# Hermes Divergent Exploration

Use this when Hermes needs to see the option space before choosing a path.
This is not a default thinking style. It is an expensive mode for open-ended
decisions where premature convergence would be costly.

## Gate

Invoke when the user explicitly asks for:

- "diverge", "发散", "brainstorm", "多种打法", "完全不同的方案"
- "ADHD mode", "并行发散", "先探索再收敛"
- architecture, product strategy, naming, public API design, positioning,
  migration planning, or fuzzy bugs with no known root cause

Do not invoke for:

- factual lookup, syntax help, or one-correct-answer questions
- known-root-cause bug fixes
- requests phrased as "quick", "just", "standard", "canonical", "直接给我"
- low-stakes edits where a direct answer is cheaper and clearer
- **creative content / brand campaign proposal reviews.** Divergent exploration
  frames (Competitor, Regulator, Builder) bias toward risk and operations. When
  a user asks for feedback on a creative proposal, first clarify the review
  type: creative (content, mechanism, breakthrough potential) vs. operational
  (risk, compliance, execution) vs. both. If they want creative review only,
  do NOT use this skill — give a structured creative assessment instead.

If unsure, answer directly and offer divergent exploration as an option.

For creative review requests that do NOT warrant divergent exploration, see
`references/creative-review-framework.md` for the alternative output shape.

## Core Invariant

Divergence must be isolated. Branches must not see each other's outputs.
Do not simulate this by writing five perspectives in one response. Use
separate delegated tasks or clearly separate fresh-context calls.

Convergence happens only after all branches return.

## Default Frames

Pick 3 to 5 frames. Use 3 for light exploration, 5 for high-stakes work.

| Frame | Use For | Prompt Bias |
|---|---|---|
| Builder | engineering, architecture | "What would actually ship with the fewest moving parts?" |
| Competitor | strategy, product, security | "How would an adversary beat, copy, or break the obvious answer?" |
| User | product, UX, adoption | "What does the user actually feel, avoid, misunderstand, or value?" |
| Regulator | risk, compliance, reliability | "What must be provable, auditable, reversible, or refused?" |
| Zero-budget | MVP, operations | "What is the cheapest crude version that preserves the load-bearing value?" |
| Wildcard | stale or overfit spaces | "Remove the main assumption and force a weird cross-domain analogy." |

For marketing or business tasks, prefer Competitor, User, Regulator,
Zero-budget, and Wildcard. For coding tasks, prefer Builder, Competitor,
Regulator, Zero-budget, and Wildcard.

## Phase 1: Diverge

Delegate one isolated branch per frame, preferably to Intelligence.

Each branch prompt should include only:

- the user's problem
- relevant constraints/context
- exactly one frame
- the generator instruction below

Generator instruction:

```text
You are in DIVERGENT mode. You are a generator, not a critic.
Generate 5 to 8 short, distinct ideas under this frame.
Each idea must be one phrase or one sentence.
Do not evaluate, rank, hedge, or merge ideas.
The first three obvious answers are banned; push past them.
Output JSON only:
[{"text":"...","rationale":"..."}]
```

When using `delegate_task`, run the branches in parallel when the tool/runtime
allows it. If parallel delegation is unavailable, make the isolation explicit
and do not pass prior branch output into later branches.

## Phase 2: Converge

After all branches return, run a critic pass. Use Pirlo for product/business
and Ambrosini for risk-heavy technical or operational decisions.

Score each idea:

- `novelty`: 0-10, distance from the obvious answer
- `viability`: 0-10, whether it could actually work
- `fit`: 0-10, whether it addresses the user's problem

Weighted score:

```text
total = novelty * 0.35 + viability * 0.40 + fit * 0.25
```

Also identify traps: attractive ideas with hidden costs, false economies,
premature abstraction, scaling failure, compliance risk, or operational burden.

Cluster ideas by underlying angle, not keywords. Good labels describe the
strategic shape, such as "manual-first plays", "trust-boundary plays",
"remove-the-platform plays", or "consumer-emotion plays".

## Phase 3: Deepen

Pick the top 2 to 3 non-trap ideas. For each, produce:

- how it would work in practice
- the load-bearing risk
- the first concrete step
- one reason it might beat the obvious answer

For implementation tasks, hand the selected path to the execution agent only
after this step. Do not start coding during divergence.

## Delegation Chain Templates

These are manual orchestration templates, not `agent-registry.json` schema.
Use them to run real tasks consistently before promoting any chain into code.

| Task Type | Chain | Stop Rule |
|---|---|---|
| Strategy / proposal | Intelligence -> Pirlo -> Designer -> Ambrosini | Stop after Pirlo when the user only needs text or direction. |
| Coding / config change | Hermes Internal -> Claude -> Ambrosini | Skip Claude for read-only diagnosis; skip Ambrosini for trivial R0/R1 edits. |
| Research / competitive analysis | Intelligence -> Pirlo | Add Ambrosini only when the result affects a risky decision. |

Use the templates this way:

1. State the selected chain and why it fits.
2. Run each step with a narrow handoff: input, output expectation, constraints.
3. Pass only the previous step's final artifact forward, not raw scratch work.
4. Collapse the chain result into one user-facing answer with risks and next step.

Do not add new registry fields such as `delegation_chains` until three real
runs show the same chain is useful and stable. `agent-registry.json` is a
generated artifact in this repo, so schema experiments belong in source config
and Coordinator code, not direct registry edits.

## Output Shape

Keep the final answer compact and decisive:

1. **Brief**: restate the problem and why divergent exploration was used.
2. **Map**: clusters with short ideas and score chips like `[N7 V8 F9]`.
3. **Shortlist**: 2 to 3 picks, with one marked as the recommended non-obvious
   but viable choice.
4. **Traps**: seductive ideas to avoid, with one-line reasons.
5. **Next Step**: the first concrete action.

Do not dump 30 raw ideas without convergence. The value is wide exploration
followed by an opinionated choice.

## Pitfalls

1. **Intelligence agent may be unavailable.** The skill says "Delegate one isolated
   branch per frame, preferably to Intelligence." In practice, Intelligence can
   fail due to model API issues (OpenCode 404, MiniMax quota exceeded, timeout).
   When this happens, do NOT block the entire divergence phase — Coordinator
   executes the frames directly with strict isolation (no cross-contamination
   between frame reasoning). The quality is slightly lower but the divergence
   value is preserved. This fallback has been validated in a real session
   (2026-05-30, 5-frame architecture exploration).

2. **Frame isolation must be enforced even in fallback mode.** When Coordinator
   self-executes frames, it must complete ALL frame reasoning BEFORE beginning
   to compare or cluster. Mixing divergence and convergence in the same pass
   defeats the purpose. Write each frame's ideas as a standalone block, then
   switch to critic mode.

3. **Prompt-bias enforcement matters more than delegation fidelity.** A delegated
   branch that gets a vague prompt produces worse ideas than Coordinator
   self-executing with a tightly scoped frame prompt. If delegation is flaky,
   prefer self-execution with sharp frame prompts over retrying delegation
   with generic ones.

4. **Creative proposals ≠ divergent exploration targets.** On 2026-05-30, a user
   shared a Xiaomi brand ambassador campaign PDF and asked for feedback. The
   skill was loaded and produced a full divergent run (5 frames, 39 ideas,
   clustering, scoring) — but the user later clarified they wanted a **creative
   review** (content, creative mechanism, breakthrough potential), not a
   risk/competitive/operational analysis. The divergent frames (Competitor,
   Regulator, Builder) systematically bias toward operational concerns and away
   from creative evaluation. **Lesson:** when a user shares a creative/marketing
   proposal, explicitly ask whether they want creative review or operational
   review BEFORE invoking this skill. Default to asking, not assuming.

## Cost Control

Use the smallest useful mode:

- Light: 3 frames x 4 ideas, no separate deepening unless requested.
- Standard: 5 frames x 5 ideas, critic clustering, top 2 deepened.
- Heavy: 5 frames x 8 ideas, critic + Ambrosini risk review, top 3 deepened.

Default to Light unless the user explicitly asks for a full divergent run or
the decision is high-stakes.
