# Usage guide

Step by step. [README.md](README.md) is the overview.

## 1. Copy it in

```bash
cp -r CLAUDE.md docs .claude scripts .github /path/to/your-project/
```

Merge by hand anything your project already has (`CLAUDE.md`, `.github/workflows/`).
Add the secret entries from this repo's `.gitignore` to yours.

## 2. Fill in `CLAUDE.md`

Replace every `[placeholder]`:

1. **Title/one-liner** — what it does, the stack.
2. **Docs table** — one row per area doc you actually create (step 6). Empty is fine.
3. **Priority order** — the line that most changes day-to-day behavior (e.g.
   "correctness/security > working feature > consistency").
4. **Critical constraints** — leave empty until a real invariant exists.
5. **Global conventions, Commands, Environment** — naming, how to build/test/run
   (including a single test), review process. Claude can't guess these reliably.
6. **Response language** (optional) — one line in Global conventions (e.g. "Respond in
   Polish") covers every agent.

Leave the Work modes table, the security override and the Security baseline alone unless
you have a reason; tune them later (step 4). Keep the file short — it loads into every
conversation; the validator fails above 130 lines.

## 3. Fill in `.claude/settings.json`

**`permissions.allow`** — pre-approved commands. Ships with `Read`/`Grep`/`Glob` and
read-only git. Add your build/test/lint commands in the same form, matching `CLAUDE.md`'s
Commands:

```json
"Bash(npm test *)",
"Bash(npm run lint *)",
"Bash(npm run build *)"
```

Don't put `[placeholders]` inside `Bash(...)` — they'd match literally.

**`permissions.ask`** — `git push` always asks.

**`permissions.deny`** — wins over `allow`. Ships with bulk `git add`, force push, and
`Read` of `.env`, `.env.*`, `*.pem`, `*.key`. Note `.env.*` also hides `.env.example`
from `Read`; if Claude needs it, narrow the rule (e.g. to `.env.local`,
`.env.production`).

**`hooks`** — `guard-bash.sh` runs before every Bash call. It does nothing unless the
command involves git; then it blocks bulk staging, `commit -a`, `--no-verify` and force
push anywhere in the command, and runs the secret scan on `git commit`. Needs `bash` (Git
Bash on Windows, which Claude Code already uses).

Optional format-on-save hook — add next to the existing one, with your formatter:

```json
"PostToolUse": [
  { "matcher": "Edit|Write",
    "hooks": [{ "type": "command", "command": "npx prettier --write ." }] }
]
```

## 4. Work normally

Just ask. The main thread picks a mode from `CLAUDE.md`:

- **"Make the login button spinner match the brand color"** → Fast. Claude edits the
  file, runs the relevant check, self-reviews, done. If you see subagents here, the mode
  table is too loose for your project — tighten it.
- **"Add CSV export to the orders page"** → Normal. Maybe `architect-lite` if the orders
  API is unfamiliar, then implementation, then `reviewer-lite`.
- **"Add 2FA to login"** → Deep (touches authentication). Threat analysis, `builder`,
  `reviewer` + `security-auditor`. If it shows up as Fast or Normal, the security
  override isn't being applied — check `CLAUDE.md`.

Want each step visible? Use `/feature <task>`. When a task ends `blocked` you get the
open findings — decide, then ask again. Commit with `/commit` when you're happy.

Before a production deploy, ask for a `security-auditor` pass over everything since the
last deploy.

## 5. Skills

- `/feature` and `/commit` run only when you type them.
- `writing-skills` and `verification-before-completion` load automatically when relevant.
- `writing-tests` and `project-conventions` are placeholders. Fill them in, then delete
  the `disable-model-invocation: true` line so Claude loads them on its own.

## 6. Docs and ADRs

When you make a real architectural decision:

1. Delete `docs/adr/ADR-0001-example.md` and its line in `docs/decisions.md`.
2. Let `architect` (Deep mode) write the ADR, or write it yourself in the same format.
3. When an area doc grows past ~150 lines, give it a `## Index` (see `docs/README.md`).

## 7. Checks and CI

`.github/workflows/checks.yml` runs on every push:

- **Mandatory** (any stack): secret scan, config validation, tests for the validator and
  hook. Needs only bash, git, Python 3 — nothing to install.
- **Optional**: `scripts/check-deps.sh` finds manifests (npm/pnpm/yarn, pip, Go, Cargo,
  Bundler, Composer, .NET) and runs the audit tool if installed. Add your toolchain's
  setup step to that job, or delete the job.
- **Yours**: add build/test/lint jobs for your project.

Run the same locally — see the Checks section in the README.

## 8. Adding or trimming agents and skills

- **Add** — read `writing-skills`, end agents with the result block from `CLAUDE.md`,
  then run `python scripts/validate_template.py`.
- **Trim** — delete the file, then run the validator: it lists every remaining reference
  (in `CLAUDE.md`, `feature/SKILL.md`, README) to fix.
- Common trims: no deep work → drop `architect` and `reviewer`; no ADRs → drop `docs/`
  and the ADR lines in `CLAUDE.md`; solo project with no review habit → keep
  `reviewer-lite` anyway for Normal work, it's the cheapest independent check you have.
