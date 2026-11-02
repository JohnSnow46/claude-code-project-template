#!/usr/bin/env bash
# Run the project's quality gates in a fixed order: test → lint → typecheck → build → security.
# Commands come from .claude/quality-gates.conf (one `gate=command` per line):
#   empty value     not configured yet → SKIP (FAIL when QUALITY_GATES_STRICT=1)
#   `none`          declared not applicable for this stack → SKIP, always allowed
# `security` always runs the built-in checks (scan-secrets.sh --all, check-deps.sh) plus any
# command you configure for it.
#
#   bash scripts/quality-gates.sh             run all gates
#   bash scripts/quality-gates.sh test lint   run only these gates
#   bash scripts/quality-gates.sh --detect    print a suggested config for this repo's stack
#
# Exit 0 = every gate passed or was skipped as allowed, 1 = a gate failed, 2 = usage error.
# Strictness (QUALITY_GATES_STRICT, REQUIRE_GITLEAKS, REQUIRE_DEP_AUDIT) comes from the
# environment, else from the `env` block of .claude/settings.json (set by the profile).
set -u
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root" || exit 2
conf="${QUALITY_GATES_CONF:-.claude/quality-gates.conf}"
GATES="test lint typecheck build security"

# Python launcher that actually works here (python3 may be a Windows Store stub).
if [ -z "${PYTHON:-}" ]; then
  for p in python3 python; do
    if "$p" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then PYTHON=$p; break; fi
  done
fi
export PYTHON="${PYTHON:-python3}"

from_settings() { # KEY -> value from .claude/settings.json env, if any
  sed -n -E "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/p" .claude/settings.json 2>/dev/null | head -1
}
for var in QUALITY_GATES_STRICT REQUIRE_GITLEAKS REQUIRE_DEP_AUDIT; do
  if [ -z "${!var:-}" ]; then export "$var=$(from_settings "$var")"; fi
done
strict=${QUALITY_GATES_STRICT:-0}

detect() {
  echo "# Suggested by scripts/quality-gates.sh --detect — review before use."
  if [ -f package.json ]; then
    pm=npm; [ -f pnpm-lock.yaml ] && pm=pnpm; [ -f yarn.lock ] && pm=yarn
    has_script() { grep -Eq "\"$1\"[[:space:]]*:" package.json; }
    has_script test && echo "test=$pm test" || echo "test="
    has_script lint && echo "lint=$pm run lint" || echo "lint="
    if has_script typecheck; then echo "typecheck=$pm run typecheck"
    elif [ -f tsconfig.json ]; then echo "typecheck=npx tsc --noEmit"; else echo "typecheck=none"; fi
    has_script build && echo "build=$pm run build" || echo "build=none"
  elif [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f setup.py ]; then
    echo "test=\$PYTHON -m pytest -q"
    echo "lint=ruff check ."
    if grep -qs mypy pyproject.toml requirements*.txt; then echo "typecheck=mypy ."; else echo "typecheck="; fi
    echo "build=none"
  elif [ -f go.mod ]; then
    printf '%s\n' "test=go test ./..." "lint=go vet ./..." "typecheck=none" "build=go build ./..."
  elif [ -f Cargo.toml ]; then
    printf '%s\n' "test=cargo test" "lint=cargo clippy -- -D warnings" "typecheck=none" "build=cargo build"
  elif ls ./*.sln ./*.slnx ./*.csproj >/dev/null 2>&1; then
    printf '%s\n' "test=dotnet test" "lint=dotnet format --verify-no-changes" "typecheck=none" "build=dotnet build -warnaserror"
  else
    printf '%s\n' "test=" "lint=" "typecheck=" "build="
  fi
  echo "security="
}

case "${1:-}" in
  --detect) detect; exit 0 ;;
  -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
esac
selected="${*:-$GATES}"
for g in $selected; do
  case " $GATES " in *" $g "*) ;; *) echo "unknown gate '$g' (gates: $GATES)" >&2; exit 2 ;; esac
done

gate_cmd() { # gate -> configured command ("" if unset)
  [ -f "$conf" ] || return 0
  sed -n -E "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*(.*)$/\1/p" "$conf" | tail -1 | sed -E 's/[[:space:]]+$//'
}

summary=""; failed=0
record() { summary="$summary$(printf '  %-10s %-5s %s' "$1" "$2" "$3")
"; [ "$2" = FAIL ] && failed=1; return 0; }

run_gate() { # gate command
  echo "=== $1: $2"
  if bash -c "$2"; then record "$1" PASS "$2"; else record "$1" FAIL "$2"; fi
}

[ -f "$conf" ] || echo "note: $conf not found — run '$0 --detect' to create one."
for g in $selected; do
  cmd=$(gate_cmd "$g")
  if [ "$g" = security ]; then
    run_gate security "bash .claude/hooks/scan-secrets.sh --all"
    run_gate security "bash scripts/check-deps.sh"
    [ -n "$cmd" ] && [ "$cmd" != none ] && run_gate security "$cmd"
    continue
  fi
  if [ "$cmd" = none ]; then
    record "$g" SKIP "not applicable (declared 'none')"
  elif [ -z "$cmd" ]; then
    if [ "$strict" = 1 ]; then record "$g" FAIL "not configured (strict: set a command or 'none')"
    else record "$g" SKIP "not configured in $conf"; fi
  else
    run_gate "$g" "$cmd"
  fi
done

echo
echo "Quality gates (strict=$strict):"
printf '%s' "$summary"
if [ "$failed" = 1 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: PASS"
