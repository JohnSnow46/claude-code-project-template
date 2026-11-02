#!/usr/bin/env bash
# Optional dependency vulnerability check. Detects manifests (up to 3 levels deep),
# runs the stack's own audit tool if it's installed, skips it otherwise.
# Reports High/Critical where the tool supports a threshold.
# REQUIRE_DEP_AUDIT=1 (high-security profile) turns a missing audit tool into a failure.
# Exit 0 = clean or nothing to check, 1 = an audit reported vulnerabilities (or a required
# audit couldn't run).
set -u
cd "${1:-.}" || exit 2

failed=0
ran=0

has() { command -v "$1" >/dev/null 2>&1; }
skip() { # dir, tool
  if [ "${REQUIRE_DEP_AUDIT:-0}" = 1 ]; then echo "FAIL  $1: $2 not installed (REQUIRE_DEP_AUDIT=1)"; failed=1
  else echo "skip  $1: $2 not installed"; fi
}
run() { # dir, tool, command...
  local dir=$1 tool=$2; shift 2
  if ! has "$tool"; then skip "$dir" "$tool"; return; fi
  echo "audit $dir: $*"
  ran=1
  (cd "$dir" && "$@") || failed=1
}

manifests=$(find . -maxdepth 3 \( -name node_modules -o -name .git -o -name vendor -o -name bin -o -name obj \) -prune -o -type f \( \
  -name package-lock.json -o -name pnpm-lock.yaml -o -name yarn.lock -o -name requirements.txt -o \
  -name pyproject.toml -o -name go.mod -o -name Cargo.lock -o -name Gemfile.lock -o -name composer.lock -o \
  -name '*.csproj' \) -print | sort)

if [ -z "$manifests" ]; then echo "No dependency manifests found."; exit 0; fi

seen=""
for m in $manifests; do
  dir=$(dirname "$m"); name=$(basename "$m")
  key="$dir|$name"; case "$name" in *.csproj) key="$dir|dotnet" ;; esac
  case "$seen" in *"[$key]"*) continue ;; esac
  seen="$seen[$key]"
  case "$name" in
    package-lock.json) run "$dir" npm npm audit --omit=dev --audit-level=high ;;
    pnpm-lock.yaml)    run "$dir" pnpm pnpm audit --prod --audit-level high ;;
    yarn.lock)
      if has yarn && (cd "$dir" && yarn --version 2>/dev/null) | grep -q '^1\.'; then
        run "$dir" yarn yarn audit --groups dependencies --level high
      else
        run "$dir" yarn yarn npm audit --environment production --severity high
      fi ;;
    requirements.txt)  run "$dir" pip-audit pip-audit -r requirements.txt ;;
    pyproject.toml)    run "$dir" pip-audit pip-audit . ;;   # the project, not the active venv
    go.mod)            run "$dir" govulncheck govulncheck ./... ;;
    Cargo.lock)        run "$dir" cargo cargo audit ;;
    Gemfile.lock)      run "$dir" bundle-audit bundle-audit check --update ;;
    composer.lock)     run "$dir" composer composer audit --no-dev ;;
    *.csproj)
      if has dotnet; then
        echo "audit $dir: dotnet list package --vulnerable --include-transitive"
        ran=1
        out=$(cd "$dir" && dotnet list package --vulnerable --include-transitive 2>&1)
        echo "$out"
        if echo "$out" | grep -Eq '(High|Critical)[[:space:]]*$|(High|Critical)[[:space:]]+https?://'; then failed=1; fi
      else skip "$dir" dotnet; fi ;;
  esac
done

[ "$ran" = 0 ] && echo "No audit tool available for the manifests found."
exit $failed
