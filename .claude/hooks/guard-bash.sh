#!/usr/bin/env bash
# PreToolUse hook for Bash. Blocks (exit 2) git operations the template forbids,
# wherever they appear in a command — permission rules only match prefixes.
# Silent and fast for every other command.
set -u

input=$(cat | tr -d '\n')
# Extract tool_input.command from the hook JSON without needing jq.
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(\([^"\\]\|\\.\)*\)".*/\1/p')
cmd=$(printf '%s' "$cmd" | sed 's/\\"/"/g')

case "$cmd" in *git*) ;; *) exit 0 ;; esac

block() { echo "Blocked by .claude/hooks/guard-bash.sh: $1" >&2; exit 2; }

git_re='git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+'
end='([[:space:];&|)]|$)'

if printf '%s' "$cmd" | grep -Eq "${git_re}add([[:space:]]+[^;&|]*)?[[:space:]](-A|--all|-u|--update|\.|:/|\*)${end}"; then
  block "bulk staging. Stage files by name after reviewing them."
fi
if printf '%s' "$cmd" | grep -Eq "${git_re}commit([[:space:]]+[^;&|]*)?[[:space:]](-a|--all|-[b-zA-Z]*a[a-zA-Z]*)${end}"; then
  block "'git commit -a' stages everything. Stage files by name first."
fi
if printf '%s' "$cmd" | grep -Eq "${git_re}(commit|push|merge|rebase|am)[^;&|]*[[:space:]]--no-verify${end}|${git_re}commit[^;&|]*[[:space:]]-n${end}"; then
  block "--no-verify. Fix what the hook reports instead of bypassing it."
fi
if printf '%s' "$cmd" | grep -Eq "${git_re}push[^;&|]*[[:space:]](-f|--force|--force-with-lease|--force-if-includes|\+[^[:space:]]+)([[:space:]=;&|]|$)"; then
  block "force push. Ask the user to do it themselves if it's really needed."
fi
if printf '%s' "$cmd" | grep -Eq "${git_re}commit${end}|${git_re}commit[[:space:]]"; then
  dir=$(cd "$(dirname "$0")" && pwd)
  if ! out=$(bash "$dir/scan-secrets.sh" --staged 2>&1); then
    block "staged changes look like they contain secrets.
$out
Unstage them (git restore --staged <file>) and move the value to env/secret storage."
  fi
fi
exit 0
