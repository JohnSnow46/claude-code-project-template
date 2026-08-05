# [Project Name]

[One or two sentences: what the project does, who it's for, and the stack — e.g. "Language/framework, storage, how it's structured (layers/modules)."]

## Docs (don't duplicate their content here)

| Area | File |
|---|---|
| [e.g. domain model / core concepts] | `docs/[area].md` (has `## Index`) |
| [e.g. API/interface layer] | `docs/[area].md` (has `## Index`) |
| [Add one row per area doc you create — see docs/README.md for the pattern] | |
| Architectural decisions | `docs/decisions.md` = index → `docs/adr/ADR-NNNN.md` = content; `## ADR Notes` = per-task usage log |

## Work modes (`.claude/agents/`)

Default mode is **fast**. The main thread picks the mode itself from the table below —
no question to the user, and no dedicated classifier agent to spawn. When in doubt, pick
the lower mode and escalate only if an architectural decision genuinely comes up
mid-implementation.

| Signal | Fast (small) | Normal (medium) | Deep (large) |
|---|---|---|---|
| Areas/modules touched | 1 | 2-3 | changes a module boundary or pattern |
| New business/domain rule | none | single, simple | complex / spans multiple entities |
| Schema or migration change | none | single, additive | changes existing schema/relations |
| Security/auth/payments touched | no | indirectly | directly |
| Examples | new page, UI component, styling, simple CRUD endpoint | new module, external integration | large refactor, architecture change, critical decision |

**Workflow per mode:**
- **Fast** (default): `builder` → `reviewer-lite`.
- **Normal**: `architect-lite` → `builder` → `reviewer-lite`.
- **Deep**: `architect` → `builder` → `reviewer`.

`architect`/`reviewer` (full) — deep mode ONLY. `architect-lite` doesn't write ADRs or
touch `docs/decisions.md`/area docs — it gives a short plan (goal, files touched,
solution, risks, validation). `reviewer-lite` checks only what blocks merging
(build/test, security, obvious bugs) — it skips the full architecture/style audit.

Number of areas touched is a **supporting** signal, not sufficient on its own: a simple
CRUD endpoint naturally touches more than one area, and still stays fast mode unless it
introduces a new business rule, a non-additive migration, or touches
security/auth/payments directly. Don't escalate mode just because a change touches more
than one file.

### Mandatory rules

**Default behavior:** small tasks MUST go through `builder` → `reviewer-lite`. Don't
spawn full `architect`/`reviewer` until a task clearly meets the normal/deep criteria
above.

**Scope discipline:** agents deliver working changes, not documentation. Docs (ADRs,
full architect plans) get written only where a real new decision is made and it actually
helps later work — not as a goal in itself.

**Completion conditions:** each agent stops once it reaches its defined output (see its
file in `.claude/agents/`). It doesn't keep exploring unrelated parts of the repo "while
it's there."

**Priority order:** [fill in for this project — e.g. "1) working feature, 2) fast
iteration, 3) consistency with existing code" for a portfolio project, or "1) safety/
correctness, 2) working feature, 3) consistency" for something production-critical.
Don't design for scale/flexibility the project doesn't need without an explicit ask.]

## Using the docs

1. Task in a known area → check `## ADR Notes` in `docs/decisions.md` first.
2. No hit → `## Index` in `docs/decisions.md`, pick specific ADR numbers.
3. Open (or delegate to `architect`) ONLY `docs/adr/ADR-NNNN.md` for the numbers you
   picked — never the whole `docs/adr/` directory, never `docs/decisions.md` in full as
   a way to reach ADR content.
4. Never `Read` a file over ~150 lines in the main thread (area docs, single ADRs)
   without an offset — use its `## Index` + `Read` offset/limit, or delegate a specific
   question to a subagent with a capped response (max ~15 points, no quoting, no
   transcribing). Only a summary comes back to the main thread. Exception: a file you're
   about to edit.
5. Search before reading: grep for the pattern → `Read` with offset/limit. Never `Read`
   without a limit on a file of unknown size.
6. After a task in **normal/deep mode**: the main/orchestrating thread (not any
   subagent), once the whole agent chain finishes (architect/architect-lite → builder →
   reviewer/reviewer-lite), appends an entry to the top of `## ADR Notes` in
   `docs/decisions.md` (template in that file) — ADRs used and their impact on the
   implementation, plus ADRs read-but-unused. In **fast mode**, skip this step if nothing
   from the ADRs was used.
7. Don't ask if you can check: `git log --oneline -20`, `git status`, repo files.
   `AskUserQuestion` only for product decisions that can't be inferred from the repo, max
   one round of questions per session.
8. After research, before implementation: "Research done, ~Nk tokens loaded. Suggest
   `/compact`."

## Critical constraints

[Fill in with this project's load-bearing invariants — the kind of rule that, if
violated, causes a real incident rather than a style nit. Point each one at the doc/ADR
that has the full reasoning, e.g.:
- "[Constraint]" → `docs/[area].md` §N, ADR-NNNN.
Delete this section if the project has none yet.]

## Global conventions

- [Naming, nullability/typing defaults, async conventions, error-handling pattern —
  whatever differs from the language/framework default.]
- [Module structure: one handler/component = one file = one test, if that's the
  convention.]
- [Test naming convention, e.g. `MethodName_Scenario_ExpectedResult`.]

## Commands

```bash
[install]
[test]
[lint/typecheck]
[build]
[run/dev]
```

## Environment

[Editor/IDE, review process (local diff vs GitHub/GitLab PRs), CI setup, anything about
the dev environment Claude can't infer from the repo.]

---

Keep this file short — every line loads into every conversation, and a bloated
CLAUDE.md causes Claude to ignore half of it. For each line, ask: *"would removing this
cause a mistake?"* If not, cut it.

Rules that only matter sometimes (detailed conventions, one-off workflows) belong in a
skill under `.claude/skills/`, not here — skills load on demand. See
[README.md](README.md) for the full picture of this template's agents and skills.
