# [Project Name]

[One or two sentences: what the project does, who it's for, and the stack.]

## Docs (don't duplicate their content here)

| Area | File |
|---|---|
| [e.g. domain model / API layer — one row per area doc, see docs/README.md] | `docs/[area].md` (has `## Index`) |
| Architectural decisions | `docs/decisions.md` (index + `## ADR Notes`) → `docs/adr/ADR-NNNN.md` |

## Work modes

Pick the mode yourself (no question, no classifier agent). Default **Trivial**, then
**Fast**; when unsure, pick the lower mode and escalate if a real signal appears mid-task.

| Signal | Trivial | Fast | Normal | Deep |
|---|---|---|---|---|
| Scope | 1 file, a few lines | 1 area, small change | new feature, 2-3 modules, integration | module boundary/pattern change |
| Business rule | none (no logic change) | none | single, simple | complex / multi-entity |
| Schema/migration | none | none | additive | changes existing data/relations |
| Examples | typo, copy, config value, rename within one file, comment/doc edit | UI, styling, small fix, simple CRUD, docs, config | endpoint with logic, new module, DB change | major refactor, critical infra |

**Security override:** a change that directly touches authentication, authorization,
permissions/roles, payments, cryptography, secrets, or sensitive personal data is
**Deep**, however small. Indirect contact (e.g. a new endpoint behind existing auth) is
not — apply the baseline below.

| Mode | Workflow |
|---|---|
| **Trivial** | You make the edit → run only the gate it can affect (none for comment/prose-only edits; say "not run: prose only"). No subagents. |
| **Fast** | You implement (you are the builder) → quality gates → self-review against the security baseline. No subagents. |
| **Normal** | Short assessment (`architect-lite` only if contracts/design are unclear) → implement (you, or `builder` if the work is large) → quality gates → `reviewer-lite`. |
| **Deep** | `architect` (only for a real design decision; for a security change without one, write a 5-line threat note yourself) → `builder` → quality gates → `reviewer` ∥ `security-auditor` (if security-sensitive). |

**Optional agents** (Normal/Deep only, and only when the signal exists): `test-engineer`
when a user-facing flow or integration boundary changes and the project has E2E/integration
tests; `performance-analyst` when there's a concrete performance signal (slowdown, budget,
hot path or large-table query changed).

Spawn an agent only when it pays for itself (isolated context for large work, or an
independent review). Never two agents checking the same concern.

**Stage-end / pre-deploy:** if the project tracks stages, when a stage with 2+ tasks
closes run a full `reviewer` over the stage; if it touched auth/sensitive data, also
`security-auditor`. Before every production deploy, `security-auditor` runs once over
everything since the last deploy.

## Security baseline (every change, every mode)

- No hardcoded secrets/credentials; config via env/secret store.
- Validate untrusted input at the boundary; parameterized queries only.
- Authorization enforced server-side; least privilege by default.
- No sensitive data in logs, errors or over-wide responses; errors don't leak internals.
- No insecure defaults (open CORS, disabled TLS checks, debug in prod).
- Never disable a security control, test or check to make something pass.
- New dependency only when needed; prefer maintained, widely used ones.
- Follow the framework's own security mechanisms instead of hand-rolling them.

Found a security issue outside the task? Report it — don't ignore it because the task is
Fast, and don't fix it silently out of scope.

## Agent results and loops

Every subagent ends with:

```
status: completed | blocked | needs_escalation
summary: …
files_changed: …
validation: <commands run + result>
risks: …
unresolved_issues: …
```

- Max **2** reviewer → builder correction cycles; after that, stop with `blocked` and
  report the open findings.
- `needs_escalation` → move up a mode and continue with what exists; don't restart.
- Never report success with failed/unrun verification or an open Blocking/Critical
  finding — say `blocked` and why.

## Quality gates

Before reporting `completed` in any mode, run `bash scripts/quality-gates.sh` (or the
gates the change can affect: `… test lint`). Order: test → lint → typecheck → build →
security; commands live in `.claude/quality-gates.conf`. Any FAIL → fix it or report
`blocked`. Put the `RESULT:` line and failure counts under `validation`; a gate you didn't
run is listed as "not run: <reason>", never omitted.

## Context discipline

- Read only files related to the task; grep before reading; widen scope only when needed.
- ADRs: `## ADR Notes` → `## Index` in `docs/decisions.md` → open only the specific
  `docs/adr/ADR-NNNN.md`. Files over ~150 lines: read via their `## Index` + offset.
- Don't ask what you can check (`git status`, `git log`, repo files). Ask only product
  decisions, one round max.
- If an ADR shaped the implementation, add an entry to `## ADR Notes` afterwards.
- No reports or docs for trivial tasks.

## Git

Commit/push only when asked (`/commit`). Stage by name, review the staged diff, no `--no-verify`/force-push.

**Priority order:** [e.g. "1) correctness/security, 2) working feature, 3) consistency".
Don't design for scale the project doesn't need.]

## Critical constraints

[Load-bearing invariants that cause incidents if violated, each pointing to its doc/ADR.
Delete this section until you have one.]

## Global conventions

- [Naming, typing/nullability defaults, error-handling pattern, test naming.]

## Commands

```bash
[install]
[test]          # plus: how to run a single test
[lint/typecheck]
[build]
[run/dev]
bash scripts/quality-gates.sh   # all gates, from .claude/quality-gates.conf
```

## Environment

Security profile: `env.CLAUDE_TEMPLATE_PROFILE` in `.claude/settings.json` ([docs/security.md](docs/security.md)).
[Review process, CI, anything about the dev environment Claude can't infer.]
