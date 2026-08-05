# ADR-0001: Example — single-tenant data model

> This is a worked example showing the ADR format, not a real decision for your project.
> Delete it (and its line in `docs/decisions.md`'s `## Index`) once you've written your
> first real ADR.

**Date:** YYYY-MM-DD
**Status:** Accepted

**Context.**
[What situation forced a decision? What were the constraints? Keep this to what's
necessary to understand the decision — not a full requirements doc.]

Example: "The app serves a single customer/location. Multi-tenant support (multiple
independent accounts with data isolation) would meaningfully complicate the model and
authorization, and nothing today needs it."

**Decision.**
[The actual decision, stated precisely enough that someone reading only this section
knows what to build. Name the concrete mechanism — entities, boundaries, patterns — not
just the intent.]

Example: "Model a **single tenant**. The `Account` entity exists as one record
(configuration only). We do not add per-tenant isolation or a `TenantId` field to
entities."

**Consequences.**
[What this decision implies — both what becomes simpler and what becomes a deliberate
limitation. Note what would need to change if the decision were reversed, so a future
reader knows the cost of revisiting it.]

Example:
- Core entities belong implicitly to the one account — no tenant filtering needed.
- If multi-tenant support becomes necessary later, that's a new ADR and a real refactor
  (adding a `TenantId` to the relevant entities) — deliberately deferred, not accidentally
  missing.
