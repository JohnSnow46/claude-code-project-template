# Security controls, profiles and models

Reference for what is enforced, by what, and where it stops. Read the index, then the
section you need.

## Index
- What is enforced, layer by layer → §1
- Git operations: deny vs. ask → §2
- Secret files and secret scanning → §3
- Profiles: solo / team / high-security → §4
- Models and fallback → §5
- Verifying the controls → §6
- Known limits → §7

## 1. Layers

| Layer | Enforced by | Deterministic? |
|---|---|---|
| Permission rules (`deny`/`ask`) | Claude Code, from `.claude/settings.json` | Yes: prefix/path match |
| `guard-bash.sh` (PreToolUse, Bash) | Hook; sees the full command text | Yes: text match (see §7) |
| `guard-files.sh` (PreToolUse, Read/Edit/Write/MultiEdit/NotebookEdit/Grep) | Hook; second layer behind `Read`/`Edit` denies | Yes |
| `scan-secrets.sh` | Guard (Claude's commits), git pre-commit hook (everyone's commits), CI | Yes |
| gitleaks | Inside `scan-secrets.sh` when installed; CI (pinned, checksum-verified, full history) | Yes |
| Quality gates | `scripts/quality-gates.sh`, locally and in CI | Yes |
| Security baseline, mode escalation, reviewers | `CLAUDE.md` + agents | No: instructions to the model |

Both hooks use `"onFailure": "block"` (Claude Code ≥ 2.1.295): if a hook can't run (no
bash, script missing), the tool call is blocked instead of silently allowed. On Windows
the hooks need Git Bash on `PATH`.

## 2. Git operations

**Denied** (exit 2, Claude gets the reason):
- bulk staging: `git add -A/--all/-u/./:/ *`
- `git commit -a`
- hook bypass: `--no-verify`, `commit -n`, `core.hooksPath` changes, `HUSKY=0`
- force push: `-f`, `--force*`, `+refspec`, `--mirror`
- any commit whose staged changes fail the secret scan
- `git add … && git commit` in one command, and `git commit <paths>` / `-i` / `-o` /
  `--`. The scan runs *before* the command, so it only sees what was already staged.
  Stage in one command, commit in the next.

Detection is the same however git is invoked: global options (`-C "path with
spaces"`, `-c k=v`, `--git-dir`), absolute path or `git.exe`, `sh -c`, `sudo`/`env`/
`VAR=x` prefixes, `&&`/`;`/`|`/newline chains, `\` line continuations. `git` only counts
as the command of a shell segment. `grep "git push --force" docs`, `echo`, and heredoc
bodies such as commit messages are data, not commands, so they aren't blocked.

**Ask** (the user confirms): `reset --hard/--merge/--keep`, `clean -f`,
`checkout -- / . / -f`, `restore` of the worktree, `branch -D`, remote branch/tag delete,
`stash drop/clear`, `filter-branch`/`filter-repo`, `reflog expire`, `update-ref -d`,
`gc --prune`.

An "ask" turns into a **deny** when nobody would see the prompt: `permission_mode` is
`auto`, `bypassPermissions` or `dontAsk`. It also turns into a deny under
`CLAUDE_GUARD_STRICT=1` (high-security). We found this the hard way: in auto mode, an
ask rule for `git reset --hard` let the command run without stopping.

## 3. Secrets

- **Reading.** `Read`/`Edit` deny rules for `**/.env`, `**/.env.*`, keys, keystores and
  `~/.ssh`, `~/.aws`, `~/.gnupg`, at any depth. `.env.example/.sample/.template` are
  carved out. Claude Code applies these to its file tools and to the Bash file commands
  it recognizes (`cat`, `head`, `<` redirects). `guard-files.sh` repeats the check for the
  file tools. `guard-bash.sh` blocks reading those files through anything else it can see:
  `base64`, `python -c`, `grep`, `sort <`, ...
- **Committing.** `scan-secrets.sh` has two layers. The built-in high-confidence patterns
  plus secret file names are the floor. **gitleaks** (about 150 rules plus entropy) is
  the real scanner, run whenever it's installed. `REQUIRE_GITLEAKS=1` (team,
  high-security, CI on Linux) makes a missing gitleaks a failure, not a skip.
- **Before commit.** Run `bash scripts/install-git-hooks.sh` once per clone, or use
  `pre-commit install` with `.pre-commit-config.yaml`. This covers human commits too,
  not just Claude's.
- **In CI.** The `gates` job scans tracked files. The `gitleaks` job scans the full
  history (`fetch-depth: 0`), so a secret that was committed and later deleted is still
  found.
- **Old findings in history.** `scan-secrets.sh --all` with gitleaks also scans local
  history, so a secret committed long ago keeps failing the security gate. Rotate the
  secret first: once it's in history, it's leaked. Then add the finding's fingerprint
  (gitleaks prints it) to a `.gitleaksignore` file at the repo root. Don't rewrite shared
  history to hide it.

## 4. Profiles

`python scripts/configure.py profile <name>` applies an overlay from
`.claude/profiles/`. `.claude/profile-state.json` records exactly what the active profile
changed: rules it added and values it replaced, with the old value. Switching undoes only
those changes. A rule you had before the profile, even one identical to a profile rule,
is never recorded, so it's never removed. Tested: round trips are byte-identical, and an
overlapping `Bash(curl *)` deny or `sandbox` block survives. Commit `profile-state.json`
together with `settings.json`. The validator fails if they drift apart.

| | solo (default) | team | high-security |
|---|---|---|---|
| Guards, deny rules, ask on destructive git | ✓ | ✓ | ✓ (ask → deny) |
| gitleaks required (`REQUIRE_GITLEAKS`) | — | ✓ | ✓ |
| Strict gates: unconfigured gate = FAIL | — | ✓ | ✓ |
| No direct push to main/master | — | ✓ | ✓ |
| Edits to `.github/`, `.claude/` ask first | — | ✓ | ✓ |
| Dependency audit required (`REQUIRE_DEP_AUDIT`) | — | — | ✓ |
| No WebFetch/curl/wget; IaC state and cloud creds unreadable | — | — | ✓ |
| `bypassPermissions` mode disabled | — | — | ✓ |
| Bash sandbox (`sandbox.enabled`, macOS/Linux/WSL2) | — | — | ✓ |

Branch protection belongs on the server (GitHub rulesets). The push denies only stop
Claude.

## 5. Models

Agents come in two tiers: **strong** (`architect`, `reviewer`, `security-auditor`) and
**standard** (everything else). Defaults are `opus` / `sonnet` aliases, never pinned
IDs, so they resolve to whatever version your account has.

```bash
python scripts/configure.py show                                 # current models + profile
python scripts/configure.py models --strong sonnet               # no Opus on your plan
python scripts/configure.py models --all inherit                 # every agent uses the session's model
python scripts/configure.py models --fallback sonnet,haiku       # settings.json fallbackModel chain (max 3)
```

`inherit` is the safe choice when you don't know which models an account can use. To
remap aliases without touching files, use `ANTHROPIC_DEFAULT_OPUS_MODEL` /
`ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL` (for example on
Bedrock/Vertex).

## 6. Verifying

```bash
bash scripts/quality-gates.sh                 # everything below, in order
bash scripts/tests/test_hooks.sh              # ~160 allow/ask/deny cases incl. audited bypasses
python -m unittest discover -s scripts/tests  # validator, settings wiring, profiles, gates
```

`test_settings.py` runs each hook through the exact `command` string from
`settings.json`. A renamed script or broken matcher fails the test, not just the
validator. The permission rules themselves are evaluated by Claude Code and can't be
unit-tested here. They were checked live in a session: nested `.env` read and write
denied, `.env.example` readable.

## 7. Limits

- The hooks match **text**. A command assembled at runtime (`$VAR`, `eval`, a script
  file, an alias) can evade them. Real isolation is the sandbox (high-security) or a
  container/VM. Never keep production secrets in the working tree.
- A Bash `cp .env x` followed by reading `x` isn't caught (`cp` stays allowed for
  `cp .env.example .env`). `source .env` is allowed, so its values are in that shell.
- A recursive search that doesn't name the file, like `grep -r DATABASE_URL .`, prints
  `.env` lines too: grep ignores `.gitignore`. The Grep tool (ripgrep) respects it; prefer
  that, or add `--exclude='.env*'`.
- `.ENV` (case variants on case-insensitive filesystems) and `.envrc` aren't treated as
  secret files.
- `sandbox.enabled` has no effect on native Windows.
- Profile env vars apply after the folder is trusted, like most project `env`.
- Whether Claude follows `CLAUDE.md` (modes, baseline, gates before "done") is not
  deterministic. The reviewers and CI are the backstop.
