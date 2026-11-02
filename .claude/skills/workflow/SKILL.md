---
name: workflow
description: Use when starting a task above Trivial, choosing or escalating a work mode, orchestrating subagents or a review loop, closing a stage or preparing a deploy, or reading/writing ADRs and area docs.
---

How to run each mode from the `CLAUDE.md` table, and how to use `docs/`.

## Per-mode steps

- **Trivial** — make the edit yourself; run only the gate it can affect (comment/prose
  only: none, report "not run: prose only"). No self-review write-up, no subagents.
- **Fast** — you implement (you are the builder) → quality gates → self-review against
  the security baseline. No subagents.
- **Normal** — short assessment (`architect-lite` only if contracts/design are unclear)
  → implement (you, or `builder` if the work is large) → quality gates → `reviewer-lite`.
- **Deep** — `architect` only for a real design decision (for a security change without
  one, write a 5-line threat note yourself) → `builder` → quality gates → `reviewer`, plus
  `security-auditor` in parallel if security-sensitive.

**Optional agents** (Normal/Deep only, and only when the signal exists): `test-engineer`
when a user-facing flow or integration boundary changes and the project has
E2E/integration tests; `performance-analyst` when there's a concrete performance signal
(slowdown, budget, hot path or large-table query changed).

Spawn an agent only when it pays for itself (isolated context for large work, or an
independent review). Never two agents checking the same concern. Pass each agent the
task plus the previous agent's output (plan, verified contracts, threat note).

## Results and loops

Read each subagent's `status` (result block in `CLAUDE.md`):

- Max **2** reviewer → builder correction cycles; after that, stop with `blocked` and
  report the open findings.
- `needs_escalation` → move up a mode and continue with what exists; don't restart.
- Never report success with failed/unrun verification or an open Blocking/Critical
  finding — say `blocked` and why. Don't trust a subagent's "passes" without a command
  and result under `validation`.

## Quality gates

`bash scripts/quality-gates.sh` (or only the gates the change can affect:
`… test lint`). Order: test → lint → typecheck → build → security; commands live in
`.claude/quality-gates.conf`. Run them before any reviewer; a FAIL goes back to the
implementer and doesn't count as a review cycle. Put the `RESULT:` line and failure
counts under `validation`; a gate you didn't run is listed as "not run: <reason>".

## Stage-end / pre-deploy

If the project tracks stages, when a stage with 2+ tasks closes run a full `reviewer`
over the stage; if it touched auth/sensitive data, also `security-auditor`. Before every
production deploy, `security-auditor` runs once over everything since the last deploy.

## Using the docs

- Read only files related to the task; grep before reading; widen scope only when needed.
- ADRs: `## ADR Notes` → `## Index` in `docs/decisions.md` → open only the specific
  `docs/adr/ADR-NNNN.md`. Files over ~150 lines: read via their `## Index` + offset.
- Don't ask what you can check (`git status`, `git log`, repo files). Batch questions;
  ask only for decisions that can't be inferred from the repo.
- If an ADR shaped the implementation, add an entry at the top of `## ADR Notes`; past
  ~20 entries, move the oldest to `docs/adr-notes-archive.md`.
- No reports or docs for trivial tasks.
