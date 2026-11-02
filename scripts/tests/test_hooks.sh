#!/usr/bin/env bash
# Tests for .claude/hooks/{guard-bash,guard-files,scan-secrets}.sh. Needs bash + git only.
# Each case feeds the hook the same JSON Claude Code sends and checks the decision:
#   allow = exit 0 + no output, ask = exit 0 + "permissionDecision":"ask", deny = exit 2.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
guard="$root/.claude/hooks/guard-bash.sh"
files="$root/.claude/hooks/guard-files.sh"
scan="$root/.claude/hooks/scan-secrets.sh"
pass=0; fail=0

check() { # expected description actual
  if [ "$1" = "$3" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL: $2 (expected $1, got $3)"; fi
}
json_str() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\t'/\\t}; printf '%s' "${s//$'\n'/\\n}"; }

decide() { # hook json -> allow|ask|deny|error:<code>
  local out code
  out=$(cd "$work" && printf '%s' "$2" | env -u CLAUDE_GUARD_STRICT -u REQUIRE_GITLEAKS bash "$1" 2>/dev/null); code=$?
  if [ "$code" = 2 ]; then echo deny
  elif [ "$code" != 0 ]; then echo "error:$code"
  elif printf '%s' "$out" | grep -q '"permissionDecision":"ask"'; then echo ask
  elif [ -z "$out" ]; then echo allow
  else echo "unexpected-output"; fi
}
bash_case() { # expected command [permission_mode]
  local json
  json=$(printf '{"session_id":"t","permission_mode":"%s","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"%s","description":"x"}}' \
    "${3:-default}" "$(json_str "$2")")
  check "$1" "guard-bash [${3:-default}]: $2" "$(decide "$guard" "$json")"
}
file_case() { # expected tool field path
  local json
  json=$(printf '{"session_id":"t","hook_event_name":"PreToolUse","tool_name":"%s","tool_input":{"%s":"%s"}}' "$1" "$2" "$(json_str "$3")")
  check "$4" "guard-files: $1 $2=$3" "$(decide "$files" "$json")"
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git -C "$work" init -q
git -C "$work" config user.email t@example.com
git -C "$work" config user.name t
git -C "$work" config core.autocrlf false
git -C "$work" commit -q --allow-empty -m init

# ---------------------------------------------------------------- guard-bash: allowed
for cmd in "ls -la" "git status --porcelain" "git add src/app.ts README.md" "git add ./src/file.ts" \
  'git commit -m "fix a bug"' "git commit --amend -m msg" "git push origin main" "git push -u origin feat" \
  "git push -n origin main" "git log --oneline -5" "git checkout -b feature/x" "git checkout main" \
  "git restore --staged leak.js" "git branch -d merged" "git clean -n" "git reset HEAD~1" "git rebase main" \
  "cp .env.example .env" "cat .env.example" "ls -la .env" "source .venv/bin/activate" "grep -r TODO src" \
  "cat README.md" "npm run build" "echo hello > out.txt"; do
  bash_case allow "$cmd"
done

# ------------------------------------------------------------------ guard-bash: deny
for cmd in "git add -A" "git add ." "git add --all" "git add -u" "git add :/" "git add *" \
  "cd sub && git add . && git commit -m x" "git -C repo add -A" "git -c color.ui=never add ." \
  "git commit -am msg" "git commit -a -m msg" "git commit --all -m msg" \
  "git commit -m msg --no-verify" "git commit -n -m msg" "git push --no-verify" "git merge feat --no-verify" \
  "git -c core.hooksPath=/dev/null commit -m x" "git config core.hooksPath .nohooks" "HUSKY=0 git commit -m x" \
  "git push --force origin main" "git push -f" "git push origin +main" "git push --force-with-lease" \
  "git push --force-with-lease=main:abc origin main" "git push origin main --force" "git push -uf origin main" \
  "git push --mirror origin" "git -c http.extraHeader=x push -f origin main" "git --no-pager push --force" \
  "git --git-dir .git push -f" "/usr/bin/git push -f" "sh -c 'git push --force'" 'g"i"t push --f"orce"' \
  "ls; git push -f" "echo ok && git push -f origin main" "(git push -f)" "\$(git push -f)" \
  "git status
git push -f" "git push -f	origin"; do
  bash_case deny "$cmd"
done

# ------------------------------------------------- guard-bash: secret files via Bash
for cmd in "cat .env" "cat apps/api/.env" "cat .env.local" "head -5 .env.production" "base64 .env" \
  "grep KEY .env" "less config/server.key" "cat ~/.ssh/id_rsa" "python3 -c 'print(open(\".env\").read())'" \
  "sort < .env" "cat ~/.aws/credentials" "tail -f .env && echo x" "cat a.txt .env"; do
  bash_case deny "$cmd"
done

# ------------------------------------------------- guard-bash: ask (destructive, legit)
for cmd in "git reset --hard" "git reset --hard HEAD~1" "git clean -fd" "git clean -fdx" "git checkout -- src/a.ts" \
  "git checkout ." "git restore src/a.ts" "git restore --staged --worktree a.ts" "git branch -D old" \
  "git push origin --delete old" "git push origin :old" "git stash drop" "git stash clear" \
  "git filter-branch --tree-filter x" "git reflog expire --all" "git gc --prune=now"; do
  bash_case ask "$cmd"
done

# --- security-audit regressions: each line was a confirmed bypass or false positive ---
nl=$'\n'
for cmd in 'git -C "/c/x y/repo" add -A' 'git -C "my repo" push --force origin main' \
  'git -C "my repo" commit --no-verify -m x' "git -c 'user.name=a b' push -f" \
  "git push \\${nl}  --force origin main" "git commit \\${nl}  --no-verify -m x" "git add \\${nl}  -A" \
  "git add leak.js && git commit -m 'add client'" "git add a.ts; git commit -m x" \
  "git commit t.js -m update" "git commit -m update -- t.js" "git commit -o t.js -m x" \
  "git.exe push -f" "C:/Program\\ Files/Git/bin/git.exe push --force" \
  "cat .env*" "head .env*" "cat .env>out.txt" 'echo "$(cat .env)"' \
  "python - <<'EOF'${nl}print(open('.env').read())${nl}EOF"; do
  bash_case deny "$cmd"
done
for cmd in 'grep -rn "git push --force" docs' 'grep -rn "\.env" scripts/tests' "rg -n 'git add -A' ." \
  'git -C "my repo" config --get core.hooksPath' 'echo "never run git push -f"' \
  "git commit -F - <<'EOF'${nl}Explain in README why git add . is denied${nl}EOF" \
  "git commit -m \"\$(cat <<'EOF'${nl}Deny git push --force and cat .env${nl}EOF${nl})\"" \
  'git commit -m "fix" -m "longer body"' "git checkout -b feat origin/feat" 'git -C "my repo" status'; do
  bash_case allow "$cmd"
done
for cmd in "git clean -n && git clean -fdx" "git restore --staged . && git restore ." "git switch -f main" \
  "git switch --discard-changes main" "git checkout HEAD~1 src/a.ts"; do
  bash_case ask "$cmd"
done
bash_case deny 'git -C "my repo" reset --hard' auto

# Nobody would see the prompt in auto/bypass mode → ask becomes deny.
bash_case deny "git reset --hard" auto
bash_case deny "git clean -fd" bypassPermissions
bash_case allow "git status" auto
out=$(cd "$work" && printf '{"tool_name":"Bash","tool_input":{"command":"git stash drop"}}' | CLAUDE_GUARD_STRICT=1 bash "$guard" >/dev/null 2>&1; echo $?)
check 2 "guard-bash: CLAUDE_GUARD_STRICT=1 turns ask into deny" "$out"

# Malformed input fails closed when it carries a command, open when it doesn't.
check deny "guard-bash: unparseable command" "$(decide "$guard" '{"tool_name":"Bash","tool_input":{"command": 42}}')"
check allow "guard-bash: no command field" "$(decide "$guard" '{"tool_name":"Bash","tool_input":{}}')"

# ------------------------------------------------------------------ guard-files
file_case Read file_path "/repo/.env" deny
file_case Read file_path "/repo/apps/api/.env.local" deny
file_case Read file_path 'C:\repo\.env' deny
file_case Read file_path "/repo/certs/server.key" deny
file_case Read file_path "/home/u/.ssh/id_ed25519" deny
file_case Read file_path "/home/u/.aws/credentials" deny
file_case Edit file_path "/repo/.env.production" deny
file_case Write file_path "/repo/.env" deny
file_case NotebookEdit notebook_path "/repo/.env" deny
file_case Grep path "/repo/.env" deny
file_case Grep glob ".env*" deny
file_case Read file_path "/repo/.env.example" allow
file_case Read file_path "/repo/src/env.ts" allow
file_case Read file_path "/repo/.envrc.md" allow
file_case Read file_path "/home/u/.ssh/id_ed25519.pub" allow
file_case Grep path "/repo/src" allow
file_case Edit file_path "/repo/keyboard.ts" allow

# ------------------------------------------------- scanner + guard on commit
# Fake secrets are assembled at runtime so this file never contains one.
akia="AKIA$(printf 'X%.0s' $(seq 1 16))"
pem_head="-----BEGIN RSA PRIVATE"" KEY-----"
scan_staged() { (cd "$work" && env -u REQUIRE_GITLEAKS PATH="$scan_path" bash "$scan" --staged >/dev/null 2>&1); echo $?; }
# Run the built-in layer on its own (gitleaks hidden from PATH) so results don't depend on the machine.
scan_path=$(printf '%s' "$PATH" | tr ':' '\n' | while read -r d; do [ -x "$d/gitleaks" ] || [ -x "$d/gitleaks.exe" ] || printf '%s:' "$d"; done)

echo "const region = 'eu-west-1';" > "$work/clean.js"
git -C "$work" add clean.js
check 0 "scan: clean staged file" "$(scan_staged)"
bash_case allow "git commit -m clean"

echo "const key = '$akia';" > "$work/leak.js"
git -C "$work" add leak.js
check 1 "scan: AWS key in staged diff" "$(scan_staged)"
bash_case deny "git commit -m leak"
out=$(cd "$work" && bash "$scan" --staged 2>&1)
case "$out" in *"$akia"*) check 0 "scan: never prints the secret" 1 ;; *) check 0 "scan: never prints the secret" 0 ;; esac
git -C "$work" restore --staged leak.js

echo "const key = '$akia'; // secret-scan:allow" > "$work/allowed.js"
git -C "$work" add allowed.js
check 0 "scan: allow marker" "$(scan_staged)"
git -C "$work" restore --staged allowed.js

printf '%s\nabc\n' "$pem_head" > "$work/k.txt"
git -C "$work" add k.txt
check 1 "scan: private key header" "$(scan_staged)"
git -C "$work" restore --staged k.txt

fakepw="hunter2""pw"
echo "DB_URL=postgres://app:${fakepw}@db:5432/x" > "$work/cfg.txt"
git -C "$work" add cfg.txt
check 1 "scan: password in connection string" "$(scan_staged)"
git -C "$work" restore --staged cfg.txt

echo "DB_URL=postgres://app:\${DB_PASSWORD}@db:5432/x" > "$work/cfg2.txt"
git -C "$work" add cfg2.txt
check 0 "scan: env-var placeholder in connection string" "$(scan_staged)"
git -C "$work" restore --staged cfg2.txt

echo "X=1" > "$work/.env"
git -C "$work" add -f .env
check 1 "scan: .env file" "$(scan_staged)"
git -C "$work" restore --staged .env

echo "X=" > "$work/.env.example"
git -C "$work" add .env.example
check 0 "scan: .env.example is fine" "$(scan_staged)"

out=$(cd "$work" && PATH="$scan_path" REQUIRE_GITLEAKS=1 bash "$scan" --staged >/dev/null 2>&1; echo $?)
check 1 "scan: REQUIRE_GITLEAKS=1 fails when gitleaks is missing" "$out"

# gitleaks layer — only when installed (CI installs it, so it always runs there).
if command -v gitleaks >/dev/null 2>&1; then
  # A generic high-entropy API key: no built-in pattern matches it, gitleaks' entropy rule does.
  generic="q8ZrLk2N""w7VbX4mT9pYc3HsJ6dFg"
  echo "api_key = \"$generic\"" > "$work/generic.py"
  git -C "$work" add generic.py
  check 0 "scan: built-in layer alone misses a generic API key" "$(scan_staged)"
  out=$(cd "$work" && bash "$scan" --staged >/dev/null 2>&1; echo $?)
  check 1 "scan: gitleaks layer finds a generic API key" "$out"
  git -C "$work" restore --staged generic.py
else
  echo "note: gitleaks not installed — gitleaks-layer test skipped (it runs in CI)"
fi

echo "hooks: $pass passed, $fail failed"
[ "$fail" = 0 ]
