<!-- Template notes in HTML comments like this one are stripped before CLAUDE.md reaches
Claude, so they cost no context. Only write what Claude can't find by reading the repo
(code.claude.com/docs/en/best-practices); keep the file well under 200 lines. Check it
with /doctor prompt-audit. Personal notes go in CLAUDE.local.md (gitignored). -->

# [Project Name]

[One or two sentences: what the project does, who it's for, and the stack.]

## Docs (don't duplicate their content here)

- [Area docs, one per area, each with a `## Index`: `docs/[area].md` — see docs/README.md]
- Architectural decisions: `docs/decisions.md` (index + `## ADR Notes`) → `docs/adr/ADR-NNNN.md`

## Work modes

Pick the mode yourself (no question, no classifier agent). Default **Trivial**, then
**Fast**; when unsure, pick the lower mode and escalate if a real signal appears mid-task.

| Signal | Trivial | Fast | Normal | Deep |
|---|---|---|---|---|
| Scope | 1 file, a few lines | 1 area, small change | new feature, 2-3 modules, integration | module boundary/pattern change |
| Business rule | none (no logic change) | none | single, simple | complex / multi-entity |
| Schema/migration | none | none | additive | changes existing data/relations |
| Examples | typo, copy, config value, rename within one file, comment/doc edit | UI, styling, small fix, simple CRUD, docs, config | endpoint with logic, new module, DB change | major refactor, critical infra |
| Workflow | You edit → only the gate it can affect. No subagents. | You implement → quality gates → self-review against the baseline. No subagents. | `architect-lite` if unclear → implement → gates → `reviewer-lite` | `architect` or a threat note → implement (`builder` only for parallel parts) → gates → `reviewer` ∥ `security-auditor` |

**Security override:** a change that directly touches authentication, authorization,
permissions/roles, payments, cryptography, secrets, or sensitive personal data is
**Deep**, however small. Indirect contact (e.g. a new endpoint behind existing auth) isn't.

Above Trivial, or for ADR/docs work: follow the `workflow` skill (steps, loops, docs).

## Security baseline (every change, every mode)

- No hardcoded secrets/credentials; config via env/secret store.
- Validate untrusted input at the boundary; parameterized queries only.
- Authorization enforced server-side; least privilege by default.
- No sensitive data in logs, errors or over-wide responses; errors don't leak internals.
- No insecure defaults (open CORS, disabled TLS checks, debug in prod).
- Never disable a security control, test or check to make something pass.
- New dependency only when needed; prefer maintained, widely used ones.
- Follow the framework's own security mechanisms instead of hand-rolling them.
- Security issue outside the task? Report it; don't ignore it or fix it silently.

## Quality gates and results

Before reporting done: `bash scripts/quality-gates.sh` (Trivial: only the affected gate).
In team/high-security profiles a `Stop` hook also runs them when you end a turn with code changes.
Any FAIL → fix or report `blocked`; never claim success on failed/unrun checks. Subagents end with:

```
status: completed | blocked | needs_escalation
summary: …
files_changed: …
validation: <commands run + RESULT: line; unrun gates as "not run: <reason>">
risks: …
unresolved_issues: …
```

Commit/push only when asked (`/commit`). Stage by name, review the staged diff, no `--no-verify`/force-push.

**Priority order:** [e.g. "correctness/security > working feature > consistency"; no unneeded scale.]

## Critical constraints

<!-- Load-bearing invariants, each pointing to its doc/ADR. A rule with zero exceptions
belongs in a hook or deny rule instead; rules for one part of the code go in .claude/rules/. -->
[Delete this section until you have one.]

## Gotchas

<!-- Where the code misleads: an old pattern new code must not copy, a directory that
looks unused but isn't, anything you've had to correct twice. -->
- [e.g. src/legacy/ is still live — don't copy its patterns into new code]

## Global conventions

<!-- Only decisions Claude can't infer from existing code. -->
- [e.g. use the error helpers in src/lib/errors.ts, never throw raw strings]

## Commands

```bash
[install]
[test]          # plus: how to run a single test
[lint/typecheck/build]
[run/dev]
bash scripts/quality-gates.sh   # all gates, from .claude/quality-gates.conf
```

## Environment

Security profile: `env.CLAUDE_TEMPLATE_PROFILE` in `.claude/settings.json` ([docs/security.md](docs/security.md)).
[Review process, CI, anything about the dev environment Claude can't infer.]
