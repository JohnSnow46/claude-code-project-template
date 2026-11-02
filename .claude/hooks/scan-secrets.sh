#!/usr/bin/env bash
# Scan for high-confidence secrets. Stack-agnostic: needs only bash, git, grep, awk.
#   scan-secrets.sh --staged   added lines in the staged diff (used by guard-bash.sh)
#   scan-secrets.sh --all      every tracked file (used by CI)
# Exit 0 = clean, 1 = findings, 2 = usage error.
# Suppress a false positive by adding `secret-scan:allow` to that line.
set -u

mode="${1:---staged}"

# One ERE per line. High-confidence only: a noisy scanner gets bypassed.
patterns='-----BEGIN ([A-Z0-9]+ )?PRIVATE KEY-----
AKIA[0-9A-Z]{16}
gh[pousr]_[A-Za-z0-9]{36,}
github_pat_[A-Za-z0-9_]{50,}
xox[baprs]-[A-Za-z0-9-]{10,}
sk_live_[0-9A-Za-z]{20,}
AIza[0-9A-Za-z_-]{35}
sk-ant-[A-Za-z0-9_-]{20,}
sk-proj-[A-Za-z0-9_-]{20,}
glpat-[A-Za-z0-9_-]{20,}
[a-zA-Z][a-zA-Z0-9+.-]*://[^/[:space:]:@"'"'"']+:[^/[:space:]@$<{"'"'"'[]{3,}@[^[:space:]]'

# File names that should never be committed (templates like .env.example are fine).
bad_names='(^|/)(\.env(\.[A-Za-z0-9_-]+)?|id_rsa|id_ed25519|id_ecdsa|[^/]+\.(pem|key|p12|pfx|jks|keystore))$'
ok_names='(^|/)\.env\.(example|sample|template|dist)$'

case "$mode" in
  --staged)
    files=$(git diff --cached --name-only --diff-filter=ACR)
    content=$(git diff --cached -U0 --no-color --diff-filter=ACMR | awk '
      /^\+\+\+ / { f = substr($0, 7); next }
      /^\+/      { print f ":" substr($0, 2) }')
    ;;
  --all)
    files=$(git ls-files)
    content=$(git grep -I -n -E -f <(printf '%s\n' "$patterns") -- . 2>/dev/null || true)
    ;;
  *)
    echo "usage: $0 [--staged|--all]" >&2; exit 2 ;;
esac

found=0

name_hits=$(printf '%s\n' "$files" | grep -E "$bad_names" | grep -Ev "$ok_names" || true)
if [ -n "$name_hits" ]; then
  echo "Secret-like files:" >&2
  printf '  %s\n' $name_hits >&2
  found=1
fi

hits=$(printf '%s\n' "$content" | grep -E -f <(printf '%s\n' "$patterns") | grep -v 'secret-scan:allow' || true)
if [ -n "$hits" ]; then
  echo "Possible secrets (add 'secret-scan:allow' to the line if this is a false positive):" >&2
  # Show location only, never the matched value.
  printf '%s\n' "$hits" | awk -F: '{ print "  " $1 (NF > 2 && $2 ~ /^[0-9]+$/ ? ":" $2 : "") }' | sort -u >&2
  found=1
fi

exit $found
