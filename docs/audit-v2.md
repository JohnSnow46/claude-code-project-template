# Audit v2 — findings

Audit of the template as of commit `48dd245` (plus the uncommitted README edits), against
three goals: speed first, security by default, right-sized engineering. Ordered by
priority. "Fix" says what v2 does about it.

## P0 — directly contradicts a goal

1. **Fast mode always spawns two agents.** `builder` → `reviewer-lite` for every task,
   including a one-line CSS fix. That's two cold-start subagents that re-derive context
   the main thread already has — the slowest possible path for the most common task.
   *Fix:* Fast = main thread implements, verifies, self-reviews against the security
   baseline. No subagents.
2. **No security baseline for ordinary changes.** Security rules live only inside
   `reviewer`/`reviewer-lite`/`security-auditor`, i.e. they're checked after the fact, by
   an agent that may not run. Nothing tells the implementer (main thread or `builder`)
   what secure code looks like. *Fix:* a short mandatory baseline in `CLAUDE.md` (loaded
   every session), applied by whoever writes the code.
3. **Security-sensitive small changes can stay in Fast.** The mode table scores
   security as one signal among four, and `Security touched: indirectly` is Normal. A
   3-line change to a role check scores "1 area, no rule, no schema" → Fast. *Fix:* a
   hard override — directly touching authn/authz, permissions, payments, crypto,
   secrets or sensitive personal data is Deep regardless of size.
4. **Unbounded review loops.** `/feature` says "changes requested → builder → same
   reviewer again" with no cap and no terminal state. *Fix:* max 2 correction cycles,
   then `blocked` with the open findings reported to the user.
5. **No result contract / no blocked state.** Agents end with free-form prose
   ("ready to merge?"). Failed verification or an unresolved critical finding has no
   defined outcome, so it can be silently glossed over. *Fix:* every agent ends with a
   6-field result block (`status: completed | blocked | needs_escalation`, …); the main
   thread never reports success on `blocked`.

## P1 — slow, redundant or inconsistent

6. **Contradiction: who commits.** `commit` skill says "builder doesn't run git
   commands"; `builder.md` says it commits when the brief asks; `/feature` says it tells
   builder whether to commit, then says "doesn't commit". *Fix:* one rule — nothing
   commits unless the user asks; `/commit` is the path.
7. **Duplicate security review in Deep.** `reviewer` has a security section and
   `security-auditor` runs in parallel on the same diff. *Fix:* when `security-auditor`
   runs, `reviewer` skips security.
8. **`prompt-engineer` duplicates `writing-skills`.** Its description (~110 words) loads
   into every session to serve a task (editing agent/skill files) that the
   `writing-skills` skill already covers on demand. *Fix:* removed.
9. **Progress-reporting boilerplate in 3 agents.** Status-line instructions cost tokens
   in every invocation and produce output nobody reads mid-run. *Fix:* removed.
10. **ADR Notes logging after every Normal/Deep task.** Writes a docs entry even when no
    ADR mattered — documentation as a goal in itself. *Fix:* log only when an ADR was
    actually used.
11. **`CLAUDE.md` is 150 lines, ~40% process prose** (docs-reading rules, stage audit
    rationale, `/compact` reminders). Loaded every session. *Fix:* cut to the rules that
    change behavior; rationale moves to README/USAGE.
12. **README/USAGE drifted from the agents** (placeholders that no longer exist,
    model-invoked list contradicting the table, no mention of `security-auditor` in
    USAGE, trim instructions referencing a 3-step `/feature`). *Fix:* rewritten.

## P2 — missing safeguards and validation

13. **Git guardrails only by prefix match.** `permissions.deny` on `git add -A` doesn't
    catch `cd x && git add .`, `git commit -m x --no-verify`, or `git push --force`.
    Nothing scans for secrets before a commit. *Fix:* a `PreToolUse` hook that blocks
    bulk-add, `--no-verify` and force-push anywhere in a command, and scans the staged
    diff for secrets on `git commit`. `git push` moved to `ask`.
14. **Secrets readable into context.** Nothing stops `Read(.env)`. *Fix:* deny rules
    for `.env`/`.env.*`/key files (Read only — documented that Bash can still reach
    them).
15. **No automated validation of the template itself.** Broken links, an agent renamed
    but still referenced by `/feature`, malformed frontmatter — all silent. *Fix:*
    `scripts/validate_template.py` (stdlib only) + CI workflow.
16. **No dependency-scan hook-in point.** *Fix:* `scripts/check-deps.sh` — detects
    manifests, runs the stack's audit tool if installed, skips otherwise. Optional.

## Kept as-is (already good)

- Three modes and the "pick the lowest mode, escalate only on a real signal" rule.
- `architect-lite`'s verified-contracts step — the highest-value part of a Normal plan.
- ADR index/content split and index-first reading.
- `verification-before-completion`, `writing-skills`, `debugger`.
- Stage-end audit and pre-deploy `security-auditor` (shortened, not removed).

## Rejected ideas

- **A classifier agent** — costs a round-trip to decide something the main thread can
  read off a table.
- **Gitleaks/Semgrep as mandatory CI** — heavy, stack-sensitive; the built-in scanner
  covers high-confidence patterns, real scanners are listed as optional.
- **Merging `reviewer` and `reviewer-lite`** — one prompt with "if deep, also check X"
  is longer for every Normal review; two short prompts are cheaper.
