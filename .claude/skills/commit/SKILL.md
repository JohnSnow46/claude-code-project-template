---
name: commit
description: Stage and commit the current changes safely. Use for `/commit`, once the work is verified and any review returned `completed`.
disable-model-invocation: true
allowed-tools: Bash(git status *), Bash(git diff *), Bash(git add *), Bash(git commit *), Bash(git log *), Bash(git restore --staged *)
---

## Current state (collected when the skill starts)

```!
git status --porcelain || true
git diff HEAD --stat || true
git log --oneline -10 || true
```

## Steps

1. Read the full `git diff HEAD` for the files above, and any untracked files you'd include.
2. Stop and report instead of committing if you see: secrets/credentials (`.env`, keys,
   tokens, connection strings with passwords), build output or dependencies
   (`node_modules`, `bin/`, `dist/`), or debug leftovers. Unrelated changes mixed in →
   ask before grouping them.
3. Stage only the relevant files **by name** — never `-A`, `.`, `-u`.
4. `git diff --cached` — confirm exactly the intended changes are staged.
5. Commit with a message matching the log above (short imperative summary;
   body only when the *why* isn't obvious).
6. If a hook fails or blocks: fix the cause or report it. Never `--no-verify`.
7. Don't push unless the user asked. Report the hash and files.
