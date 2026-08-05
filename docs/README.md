# Docs conventions

This folder holds reference docs Claude (and you) consult mid-task — not narrative
documentation. Two conventions make that cheap on context:

## 1. One doc per area, each with an `## Indeks` section

As the project grows, split reference docs by area (domain model, API layer, whatever
areas make sense for your architecture) instead of one giant doc. Give each file a short
`## Indeks` section near the top — one line per subsection, so the index alone tells you
whether the full section is worth opening.

```markdown
## Indeks
- Ordering flow → §2
- Auth/roles → §5
- Webhook handling → §7
```

Agents (and CLAUDE.md, step 4 of "Using the docs") are instructed to read the index first,
then jump to a specific section with `Read`'s `offset`/`limit`, rather than reading the
whole file. This is the single biggest lever for not blowing the context window on docs
that grow over time.

This template ships no area docs by default — Pizza (the project this convention is
generalized from) had `domain-model.md`, `api-layer.md`, `application-layer.md`,
`infrastructure-layer.md` because it has four Clean Architecture layers. Your project's
areas will be different; create the docs that match your actual structure.

## 2. ADRs: index + content are separate files

`decisions.md` is the **index** (one line per ADR + a per-task usage log). Full ADR
content lives one-per-file in `adr/ADR-NNNN.md`. Never duplicate ADR content into the
index — see `decisions.md` for the full rule and the `architect` agent for who's allowed
to write ADRs.

`adr/ADR-0001-example.md` shows the format. Delete it once you've written a real one.

## Why this matters

Both conventions exist for the same reason: a large doc read in full, every time it's
even tangentially relevant, is one of the fastest ways to fill the context window and
degrade output quality (see [Anthropic's guidance on this](https://code.claude.com/docs/en/best-practices)).
Index-first + offset-read keeps the cost proportional to what's actually needed.
