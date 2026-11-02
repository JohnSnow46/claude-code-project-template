---
name: feature
description: Run a task through this repo's Trivial/Fast/Normal/Deep workflow with an explicit mode decision, bounded review loop and result contract. Use for `/feature <task description>`.
argument-hint: [task description]
disable-model-invocation: true
---

Runs `$ARGUMENTS` through the workflow in `CLAUDE.md` ("Work modes", "Agent results and
loops"), making each step explicit.

## 1. Classify

If `$ARGUMENTS` names a stage from a plan doc, read that stage first — it may prescribe
the mode. Otherwise score against the `CLAUDE.md` table, apply the **security override**,
pick the lowest mode that fits. Output one line first:

`Mode: <Trivial|Fast|Normal|Deep> — <reason>`

## 2. Run

- **Trivial** — make the edit yourself; run only the gate it can affect (none for
  comment/prose-only edits). No subagents.
- **Fast** — implement yourself, run the quality gates, self-review against the
  security baseline. No subagents.
- **Normal** — `architect-lite` only if contracts/design are unclear → implement (you, or
  `builder` for large work) → `reviewer-lite`.
- **Deep** — `architect` (if there's a design decision; else write a 5-line threat note)
  → `builder` → `reviewer`, plus `security-auditor` in parallel if security-sensitive
  (then `reviewer` skips security).

Optional, Normal/Deep only and only on their signal (see `CLAUDE.md`): `test-engineer`
after implementation for a changed user-facing flow/integration boundary;
`performance-analyst` before or after implementation for a concrete performance signal.

Before any reviewer runs, run `bash scripts/quality-gates.sh`; a FAIL goes back to the
implementer first (it doesn't count as a review cycle).

Pass each agent the task plus the previous agent's full output (plan, verified
contracts, threat note).

## 3. Handle results

Read each agent's `status`:
- `completed` → next step.
- `needs_escalation` → move up a mode and continue from the next agent in that mode,
  passing everything produced so far. Don't restart.
- `blocked` from a reviewer/auditor → `builder` (or you) fixes the listed findings → the
  same reviewer again. **Max 2 cycles.** Still blocked → stop.
- `blocked` from `builder` → stop.

Don't trust a subagent's "passes" — check its `validation` shows a command and result.

## 4. Stage end (only if this task closes a stage)

Per `CLAUDE.md`: full `reviewer` if the stage had 2+ tasks; `security-auditor` if it
touched auth/sensitive data; in parallel. In-scope findings → one fix batch (counts
toward the 2-cycle cap). Out-of-scope → report as separate tasks.

## 5. Finish

- If an ADR shaped the work, add an entry at the top of `## ADR Notes` in
  `docs/decisions.md` (template there).
- Run the quality gates once more on the final state; quote the `RESULT:` line.
- Report to the user in the result-block shape, `risks` and `unresolved_issues` always
  filled (write "none" if empty). `blocked` → list `unresolved_issues`
  first; never phrase it as done.
- Don't commit — the user runs `/commit`.
