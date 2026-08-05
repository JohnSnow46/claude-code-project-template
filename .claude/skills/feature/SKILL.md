---
name: feature
description: Run a full feature/task through this repo's mode pipeline — classify fast/normal/deep, delegate to the matching agent chain, and log ADR usage. Use for `/feature <task description>` instead of manually picking agents and remembering to update docs/decisions.md.
argument-hint: [task description]
disable-model-invocation: true
---

Runs `$ARGUMENTS` through this repo's full mode pipeline: classify → delegate to the
matching agent chain → log ADR usage. Makes the process in `CLAUDE.md` ("Work modes",
"Using the docs" step 6) explicit instead of relying on the mode being remembered.

## 1. Classify

Read the tiering table in `CLAUDE.md` under "Work modes". Score `$ARGUMENTS` against its
signals (areas touched, new business/domain rule, schema/migration change,
security/auth/payments touched). Pick the lowest mode that fits — don't escalate on area
count alone.

Before doing anything else, output one line:

`Mode: <Fast|Normal|Deep> — <one-line reason>`

## 2. Run the chain

Delegate via the Task tool, in order, waiting for each agent to finish before starting
the next:

- **Fast**: `builder` → `reviewer-lite`
- **Normal**: `architect-lite` → `builder` → `reviewer-lite`
- **Deep**: `architect` → `builder` → `reviewer`

Pass each agent the task description plus the previous agent's output (plan/ADR,
implementation summary). Don't skip an agent in the chosen chain and don't add one that
isn't listed for it.

If mid-chain an agent flags the task as bigger than the chosen mode (e.g.
`architect-lite` recommends `architect`, or `builder`/`reviewer` finds the design
insufficient), re-classify to the new mode and resume — don't restart. Continue from the
next agent up in the new mode's chain (e.g. `architect-lite` flagging up to Deep means
the next step is `architect`, not a second run of `architect-lite`), passing it
everything the original chain already produced (plan/ADR, implementation summary) as
input. Don't restart the new mode's chain from its first agent if some of that work
already happened under the old mode.

## 3. Log ADR usage (normal/deep only)

Skip this step entirely in fast mode.

Once every agent in the chain has finished, append one entry to the top of `## ADR
Notes` in `docs/decisions.md` (directly below `<!-- Newest entries go directly below
this line. -->`), using the exact template already there:

```markdown
### YYYY-MM-DD — <short task description>
- ADRs used: ADR-NNNN (<one-line impact on the implementation>)
- ADRs read but not used: ADR-NNNN (<why it didn't apply>)
```

Use today's date. If no ADRs were read at all, omit the "read but not used" line rather
than leaving a placeholder.

## What this skill does NOT do

- Doesn't write ADR content itself — that's `architect`'s job during the deep-mode
  chain.
- Doesn't second-guess a passing `reviewer`/`reviewer-lite` verdict.
- Doesn't commit — run `/commit` separately once the chain reports ready-to-merge.
