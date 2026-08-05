# Claude Code project template

A reusable starter for new projects: a cost-tiered agent pipeline, an ADR-backed decision
log, and a handful of skills — copy it in, fill in the placeholders, delete what doesn't
apply.

This isn't a from-scratch design. It's a synthesis of five sources, credited in detail
under [Attribution](#attribution):

- **A real project** (a portfolio e-commerce app) — the tiered pipeline and ADR system,
  generalized away from its original stack
- **[mattpocock/skills](https://github.com/mattpocock/skills)** (MIT) — the
  model-invoked-vs-user-invoked framing for skills
- **[obra/superpowers](https://github.com/obra/superpowers)** — two condensed skills,
  `writing-skills` and `verification-before-completion`
- **[EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)**
  — confirmed frontmatter conventions against its canonical fixture
- **[zhaoxuya520/reverse-skill](https://github.com/zhaoxuya520/reverse-skill)** —
  reviewed, nothing adopted directly (see Attribution for why)
- Anthropic's official Claude Code docs (skills, sub-agents, best practices) — every
  frontmatter field below is checked against current docs, not assumed from these repos

## How to use this

See **[USAGE.md](USAGE.md)** for the full step-by-step walkthrough. Short version:

1. Copy `CLAUDE.md`, `docs/`, `.claude/agents/`, and `.claude/skills/` into your project
   root.
2. Fill in the `[bracketed placeholders]` in `CLAUDE.md` — project description, docs
   table, priority order, critical constraints, conventions, commands, environment.
3. Delete what doesn't apply. If you never do large/risky work, drop `architect` and
   `reviewer` entirely and just use `builder` → `reviewer-lite` for everything. If you
   don't want an ADR system, delete `docs/` and the "Using the docs" section of
   `CLAUDE.md`. Nothing here depends on all of it being present.
4. Commit `.claude/`, `CLAUDE.md`, and `docs/` to git so your team benefits too.

## The pipeline: cost-tiered by default

The core idea, kept from the source project: **most tasks should cost as little as
possible — cheap model, cheap agent chain, no unnecessary hops — and only escalate when a
concrete signal demands it.** `CLAUDE.md` has the full classification table; the shape is:

| Mode | Chain | When |
|---|---|---|
| **Fast** (default) | `builder` → `reviewer-lite` | Single area, no new business rule, no schema change, no direct security touch |
| **Normal** | `architect-lite` → `builder` → `reviewer-lite` | A few areas, a simple new rule, an additive migration, an integration |
| **Deep** | `architect` → `builder` → `reviewer` | A module-boundary/pattern change, a complex rule, a schema change, security/auth/payments touched directly |

The main thread classifies from the table itself — `task-classifier` only gets spawned
when scope is genuinely unclear, to avoid burning a round-trip just to classify an obvious
task.

Cost-tiering here means two separate things, and both matter: fewer hops for small tasks
(fast mode skips `architect`/`reviewer` entirely), *and* each hop that does run uses the
cheapest model that's actually sufficient for it — see the Model column below. A fast-mode
task not only skips two agents, its two remaining agents (`builder` on Sonnet,
`reviewer-lite` on Haiku) are also individually cheaper than the agents a deep-mode task
runs (`architect` and `reviewer` on Opus). The two effects compound: skipping hops alone
would still leave every remaining hop priced as if it might be the hard case.

## `.claude/agents/` — subagents

| Agent | Role | Model |
|---|---|---|
| `task-classifier` | Resolves fast/normal/deep when scope is genuinely unclear (rarely invoked) | Haiku — pattern-matching against a fixed table, not judgment |
| `architect` | Full design + ADR-writing — deep mode only | Opus — the task reached deep mode by definition, so the decision it's designing is worth the strongest model |
| `architect-lite` | A fixed 5-point plan, no ADR — normal mode | Sonnet — real design judgment, but scoped and short |
| `builder` | Implements code and tests, in every mode | Sonnet — day-to-day implementation work |
| `reviewer` | Full review (architecture, tests, security) — deep mode only | Opus — same reasoning as `architect`: deep-mode stakes justify the strongest reviewer |
| `reviewer-lite` | Fast review (blocking issues + security only) — fast/normal mode | Haiku — a bounded checklist (build/test, obvious bugs, security basics), not an architecture audit |
| `prompt-engineer` | Meta-agent: writes/edits other agents and skills consistently | Sonnet — prompt-quality judgment |
| `debugger` | Root-causes errors and failing tests — orthogonal to the tiers, use any time something's broken | Sonnet — root-causing needs real reasoning regardless of which mode triggered it |

Each agent's frontmatter (`name`, `description`, `tools`, `model`) and behavior were
checked against Anthropic's current [sub-agents docs](https://code.claude.com/docs/en/sub-agents)
during this template's design.

## `.claude/skills/` — skills

| Skill | Invocation | Use for |
|---|---|---|
| `commit` | User-invoked (`disable-model-invocation: true`) | Staging/committing once `reviewer`/`reviewer-lite` gives a ready-to-merge verdict |
| `writing-tests` | Model-invoked | Background conventions for writing/fixing tests |
| `project-conventions` | Model-invoked | Detailed conventions too long for `CLAUDE.md` |
| `writing-skills` | Model-invoked | Reference for authoring this repo's own skills/agents well |
| `verification-before-completion` | Model-invoked | Evidence-before-claims discipline for `builder`/`reviewer`/`reviewer-lite` |

### Model-invoked vs. user-invoked — a design axis, not a default

Every skill you add should be deliberately classified along this axis (named explicitly
here, credited to mattpocock/skills' `invocation.md`):

- **User-invoked** (`disable-model-invocation: true`) — reachable only by you typing
  `/name`. Use for anything with a side effect or timing you want to control (`commit` is
  the example here — you don't want the model deciding to commit because the code "looks
  ready").
- **Model-invoked** (the default — omit the field) — reachable by you or by Claude
  automatically when relevant. Use for background knowledge or reference material the
  model should reach for on its own (`writing-tests`, `project-conventions`,
  `writing-skills`, `verification-before-completion`).

The test isn't "could this be reused" — it's "could the model usefully reach for this on
its own, or does invoking it need to stay a deliberate human action?"

## The ADR system

`docs/decisions.md` is an **index + per-task usage log**; full ADR content lives
one-per-file in `docs/adr/ADR-NNNN.md`. `docs/README.md` explains the full pattern,
including the "never read a doc over ~150 lines without an offset" rule that keeps this
from costing context as the project grows. `docs/adr/ADR-0001-example.md` shows the
Context → Decision → Consequences format — delete it once you've written a real one.

## Conventions for adding your own

**Subagent** — `.claude/agents/<name>.md`:

```markdown
---
name: my-agent
description: When Claude should delegate to this agent — third person, specific triggers
tools: Read, Grep, Glob        # omit to inherit everything
model: sonnet                  # sonnet | opus | haiku | inherit
---

System prompt / instructions for the agent go here.
```

**Skill** — `.claude/skills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: Use when [specific triggering conditions] — not what the skill does
---

Skill content. Keep it under ~500 words if it loads often; put heavy reference
material in a separate file next to SKILL.md instead.
```

Before writing either, read the `writing-skills` skill — it has the rules that matter
most for descriptions and for matching the guidance's *form* to the failure it prevents.
Or just delegate to `prompt-engineer`, which applies those rules for you.

## Options not built into this starter

Two patterns came up in research but aren't included by default — cheap to add later if
you outgrow the starter:

- **Bucket folders for skills** (`engineering/`, `personal/`, `misc/`, `deprecated/`, per
  mattpocock/skills) — worth it once you have more than a handful of skills and need to
  separate promoted ones from drafts/retired ones. Not needed at 5 skills.
- **A human-facing doc per skill** (`docs/skills/<name>.md`, per compound-engineering-plugin
  and mattpocock/skills) — a mirror of each `SKILL.md` written for people browsing docs
  rather than for the model. Worth it once your skill count makes the README table
  unwieldy.

## Attribution

| Source | License | What was taken |
|---|---|---|
| Real portfolio project (this template's origin) | — | The tiered pipeline (fast/normal/deep), the agent roles and their cheap/expensive pairing, the ADR index+log split, the context-reading discipline, the progress-report line format |
| [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | The model-invoked-vs-user-invoked framing as a named design axis |
| [obra/superpowers](https://github.com/obra/superpowers) | — | `writing-skills` and `verification-before-completion`, condensed and rewritten, not copied verbatim |
| [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) | — | Used to cross-check agent/skill frontmatter conventions against its `tests/fixtures/sample-plugin`; its per-skill human-doc-mirror convention noted above as optional, not built |
| [zhaoxuya520/reverse-skill](https://github.com/zhaoxuya520/reverse-skill) | — | Reviewed for structural ideas. Its per-skill Codex sidecar is the same convention already seen in mattpocock (out of scope — this template targets Claude Code only); its routing-coherence-check script was judged too heavy/domain-specific for a starter. Nothing adopted directly. |
| Anthropic — [Skills](https://code.claude.com/docs/en/skills), [Sub-agents](https://code.claude.com/docs/en/sub-agents), [Best practices](https://code.claude.com/docs/en/best-practices) | — | Every frontmatter field and convention here is checked against these, current as of this template's writing |
