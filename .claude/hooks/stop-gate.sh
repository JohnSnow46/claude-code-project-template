#!/usr/bin/env bash
# Stop hook: when Claude tries to end its turn with uncommitted code changes, run the
# quality gates; on FAIL, exit 2 so Claude Code sends Claude back to fix them (the
# gate output goes to stderr, which Claude receives as the reason).
#
# Opt-in: active only when CLAUDE_STOP_GATE=1 (the team and high-security profiles set
# it). Skips: not a git repo, clean tree, prose-only changes (*.md, *.txt), or a tree
# identical to the last one that passed. Claude Code ends the turn anyway after
# CLAUDE_CODE_STOP_HOOK_BLOCK_CAP blocks in a row, so a gate Claude can't fix ends as
# a reported `blocked`, not a loop. Needs bash, git, and sha1sum or shasum.
set -u

[ "${CLAUDE_STOP_GATE:-0}" = "1" ] || exit 0
cat >/dev/null  # hook input isn't needed

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

changed=$(git status --porcelain --untracked-files=all | sed -E 's/^.{3}//; s/.* -> //')
[ -z "$changed" ] && exit 0
printf '%s\n' "$changed" | grep -Eqv '\.(md|txt)$' || exit 0

hash_cmd=sha1sum; command -v sha1sum >/dev/null 2>&1 || hash_cmd="shasum"
fingerprint=$( { git diff HEAD; printf '%s\n' "$changed" | while IFS= read -r f; do
  [ -f "$f" ] && git hash-object -- "$f"; done; } 2>/dev/null | $hash_cmd | cut -c1-40)
stamp="$(git rev-parse --git-dir)/claude-stop-gate.pass"
[ -f "$stamp" ] && [ "$(cat "$stamp")" = "$fingerprint" ] && exit 0

out=$(bash scripts/quality-gates.sh 2>&1); code=$?
if [ "$code" -eq 0 ]; then
  printf '%s\n' "$fingerprint" > "$stamp"
  exit 0
fi
{
  echo "Quality gates failed (stop-gate.sh). Fix the failures, or if they're outside this task, report status: blocked with the RESULT line."
  printf '%s\n' "$out" | tail -n 40
} >&2
exit 2
