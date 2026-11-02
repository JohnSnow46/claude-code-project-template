# Usage guide

Step by step. [README.md](README.md) is the overview.

## 1. Copy it in

```bash
cp -r CLAUDE.md THIRD_PARTY_NOTICES.md docs .claude scripts .github .gitattributes .pre-commit-config.yaml /path/to/your-project/
```

Merge by hand anything your project already has (`CLAUDE.md`, `.github/workflows/`,
`.gitattributes`). Add the secret entries from this repo's `.gitignore` to yours.
`.gitattributes` keeps the hook scripts on LF line endings; a CRLF checkout on Windows
breaks bash.

Then, once per clone:

```bash
python3 scripts/configure.py profile solo     # or team / high-security — see README "Profiles"
bash scripts/install-git-hooks.sh             # secret scan before every commit
```

Install [gitleaks](https://github.com/gitleaks/gitleaks#installing). It's optional for
`solo`, required for `team` and `high-security`.

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

**`permissions.ask`** — `git push`, `git reset --hard`, `git clean` always ask.

**`permissions.deny`** — wins over `allow`. Ships with bulk `git add`, force/mirror
push, and `Read`/`Edit` of `.env`, `.env.*`, keys and keystores **at any depth**, plus
`~/.ssh`, `~/.aws`, `~/.gnupg`. `.env.example/.sample/.template` are carved out with
`!` rules, so Claude can still read the template.

**`hooks`** — two PreToolUse hooks, both fail closed (`onFailure: block`):
`guard-bash.sh` before every Bash call and `guard-files.sh` before the file tools. What
they deny, what they ask about, and their limits: [docs/security.md](docs/security.md).
Needs `bash` (Git Bash on Windows, which Claude Code already uses).

Don't hand-edit rules a profile owns. Switch profiles with `scripts/configure.py`. The
validator flags drift between `settings.json` and its declared profile.

Optional format-on-save hook — add next to the existing one, with your formatter:

```json
"PostToolUse": [
  { "matcher": "Edit|Write",
    "hooks": [{ "type": "command", "command": "npx prettier --write ." }] }
]
```

## 4. Quality gates

```bash
bash scripts/quality-gates.sh --detect   # suggestion for your stack
```

Copy the suggestion into `.claude/quality-gates.conf` and check each command runs. Write
`none` for a gate your stack doesn't have (e.g. `typecheck=none` for Go). Leaving a gate
empty means "not configured yet": skipped under `solo`, a failure under `team`/
`high-security`. Claude runs the gates before reporting any task as done; so does CI.

## 5. Work normally

Just ask. The main thread picks a mode from `CLAUDE.md`:

- **"Fix the typo in the signup page heading"** → Trivial. Claude edits the line, skips
  the gates (prose only) and says so. No self-review write-up, no subagents.
- **"Make the login button spinner match the brand color"** → Fast. Claude edits the
  file, runs the relevant check, self-reviews, done. If you see subagents here, the mode
  table is too loose for your project — tighten it.
- **"Add CSV export to the orders page"** → Normal. Maybe `architect-lite` if the orders
  API is unfamiliar, then implementation, then `reviewer-lite`.
- **"Add 2FA to login"** → Deep (touches authentication). Threat analysis, `builder`,
  `reviewer` + `security-auditor`. If it shows up as Fast or Normal, the security
  override isn't being applied — check `CLAUDE.md`.
- **"Checkout times out with 500 items in the cart"** → Normal, with
  `performance-analyst` to measure first. A changed checkout flow with a Playwright
  suite also gets `test-engineer`.

Want each step visible? Use `/feature <task>`. When a task ends `blocked` you get the
open findings — decide, then ask again. Commit with `/commit` when you're happy.

Before a production deploy, ask for a `security-auditor` pass over everything since the
last deploy.

## 6. Skills

- `/feature` and `/commit` run only when you type them.
- `writing-skills` and `verification-before-completion` load automatically when relevant.
- `writing-tests` and `project-conventions` are placeholders. Fill them in, then delete
  the `disable-model-invocation: true` line so Claude loads them on its own.

## 7. Docs and ADRs

When you make a real architectural decision:

1. Delete `docs/adr/ADR-0001-example.md` and its line in `docs/decisions.md`.
2. Let `architect` (Deep mode) write the ADR, or write it yourself in the same format.
3. When an area doc grows past ~150 lines, give it a `## Index` (see `docs/README.md`).

## 8. Checks and CI

`.github/workflows/checks.yml` runs on every push:

- **`gates`** (Linux, macOS, Windows): `scripts/quality-gates.sh`. That's your
  test/lint/typecheck/build from `.claude/quality-gates.conf`, then the security gate
  (secret scan with gitleaks on Linux, plus `check-deps.sh`, which audits
  npm/pnpm/yarn, pip, Go, Cargo, Bundler, Composer and .NET when the tool is installed).
  Add your toolchain's setup step (setup-node, setup-python, ...) before it.
- **`gitleaks`**: full-history scan with a pinned, checksum-verified gitleaks. To update
  it, change `GITLEAKS_VERSION` and `GITLEAKS_SHA256` together (from the release's
  `checksums.txt`).

Run the same locally — see the Checks section in the README.

## 9. Adding or trimming agents and skills

- **Add** — read `writing-skills`, end agents with the result block from `CLAUDE.md`,
  then run `python scripts/validate_template.py`.
- **Trim** — delete the file, then run the validator: it lists every remaining reference
  (in `CLAUDE.md`, `feature/SKILL.md`, README) to fix.
- Common trims: no deep work → drop `architect` and `reviewer`; no ADRs → drop `docs/`
  and the ADR lines in `CLAUDE.md`; solo project with no review habit → keep
  `reviewer-lite` anyway for Normal work, it's the cheapest independent check you have.
  No E2E tests or perf work → drop `test-engineer`/`performance-analyst`.
