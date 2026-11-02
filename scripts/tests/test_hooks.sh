#!/usr/bin/env bash
# Tests for .claude/hooks/guard-bash.sh and scan-secrets.sh. Needs bash + git only.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
guard="$root/.claude/hooks/guard-bash.sh"
scan="$root/.claude/hooks/scan-secrets.sh"
pass=0; fail=0

check() { # expected_exit description actual_exit
  if [ "$1" = "$3" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL: $2 (expected $1, got $3)"; fi
}

hook() { # expected_exit command
  local json
  json=$(printf '{"tool_name":"Bash","tool_input":{"command":"%s","description":"x"}}' "$2")
  (cd "$work" && printf '%s' "$json" | bash "$guard" >/dev/null 2>&1)
  check "$1" "guard: $2" "$?"
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git -C "$work" init -q
git -C "$work" config user.email t@example.com
git -C "$work" config user.name t
git -C "$work" config core.autocrlf false
git -C "$work" commit -q --allow-empty -m init

# --- guard: allowed ---
hook 0 "ls -la"
hook 0 "git status --porcelain"
hook 0 "git add src/app.ts README.md"
hook 0 "git add ./src/file.ts"
hook 0 "git commit -m \\\"fix a bug\\\""
hook 0 "git commit --amend -m msg"
hook 0 "git push origin main"
hook 0 "git push -n origin main"
# --- guard: blocked ---
hook 2 "git add -A"
hook 2 "git add ."
hook 2 "cd sub && git add . && git commit -m x"
hook 2 "git add --all"
hook 2 "git add -u"
hook 2 "git -C repo add -A"
hook 2 "git commit -am msg"
hook 2 "git commit -a -m msg"
hook 2 "git commit -m msg --no-verify"
hook 2 "git commit -n -m msg"
hook 2 "git push --force origin main"
hook 2 "git push -f"
hook 2 "git push origin +main"
hook 2 "git push --force-with-lease"

# --- scanner + guard on commit ---
# Fake secrets are assembled at runtime so this file never contains one.
akia="AKIA$(printf 'X%.0s' $(seq 1 16))"
pem_head="-----BEGIN RSA PRIVATE"" KEY-----"

echo "const region = 'eu-west-1';" > "$work/clean.js"
git -C "$work" add clean.js
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 0 "scan: clean staged file" "$?"
hook 0 "git commit -m clean"

echo "const key = '$akia';" > "$work/leak.js"
git -C "$work" add leak.js
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 1 "scan: AWS key in staged diff" "$?"
hook 2 "git commit -m leak"
out=$(cd "$work" && bash "$scan" --staged 2>&1)
case "$out" in *"$akia"*) check 0 "scan: never prints the secret" 1 ;; *) check 0 "scan: never prints the secret" 0 ;; esac
git -C "$work" restore --staged leak.js

echo "const key = '$akia'; // secret-scan:allow" > "$work/allowed.js"
git -C "$work" add allowed.js
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 0 "scan: allow marker" "$?"
git -C "$work" restore --staged allowed.js

printf '%s\nabc\n' "$pem_head" > "$work/k.txt"
git -C "$work" add k.txt
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 1 "scan: private key header" "$?"
git -C "$work" restore --staged k.txt

fakepw="hunter2""pw"
echo "DB_URL=postgres://app:${fakepw}@db:5432/x" > "$work/cfg.txt"
git -C "$work" add cfg.txt
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 1 "scan: password in connection string" "$?"
git -C "$work" restore --staged cfg.txt

echo "DB_URL=postgres://app:\${DB_PASSWORD}@db:5432/x" > "$work/cfg2.txt"
git -C "$work" add cfg2.txt
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 0 "scan: env-var placeholder in connection string" "$?"
git -C "$work" restore --staged cfg2.txt

echo "X=1" > "$work/.env"
git -C "$work" add -f .env
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 1 "scan: .env file" "$?"
git -C "$work" restore --staged .env

echo "X=" > "$work/.env.example"
git -C "$work" add .env.example
(cd "$work" && bash "$scan" --staged >/dev/null 2>&1); check 0 "scan: .env.example is fine" "$?"

echo "hooks: $pass passed, $fail failed"
[ "$fail" = 0 ]
