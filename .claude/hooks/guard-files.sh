#!/usr/bin/env bash
# PreToolUse hook for the file tools (Read, Edit, Write, MultiEdit, NotebookEdit, Grep).
# Denies (exit 2) any path that points at a secret file: .env / .env.* (templates such
# as .env.example are fine), private keys and keystores, SSH keys, .netrc, .pgpass,
# cloud credential files. Second layer behind the Read/Edit deny rules in settings.json,
# so one mistyped rule doesn't open the file. Needs only bash, sed and grep.
set -u

input=$(cat | tr -d '\r\n')

# Collect every path-like field the file tools use.
paths=$(printf '%s' "$input" | grep -Eo '"(file_path|notebook_path|path|glob)"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' |
  sed -E 's/^"[a-z_]+"[[:space:]]*:[[:space:]]*"//; s/"$//; s/\\\\/\//g')

[ -z "$paths" ] && exit 0

secret='(^|/)(\.env(\.[A-Za-z0-9_*-]+)*|[^/]*\.(pem|key|p12|pfx|jks|keystore)|id_(rsa|dsa|ecdsa|ed25519)|\.netrc|\.pgpass|\.aws/credentials|\.docker/config\.json|\.env\*)$'
template='(^|/)\.env\.(example|sample|template|dist)$'

hits=$(printf '%s\n' "$paths" | grep -E "$secret" | grep -Ev "$template" || true)
if [ -n "$hits" ]; then
  echo "Blocked by .claude/hooks/guard-files.sh: '$hits' is a secret file. Ask the user for the specific non-secret value you need, or use the .env.example template." >&2
  exit 2
fi
exit 0
