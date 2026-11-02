#!/usr/bin/env bash
# PreToolUse hook for Bash. Inspects the full command text — permission rules only
# match prefixes — and decides:
#   deny (exit 2)  bulk staging, `commit -a`, commit with paths or in the same command as
#                  `git add` (the secret scan can't see those), hook bypass (--no-verify,
#                  core.hooksPath), force/mirror push, reading secret files, committing
#                  staged secrets
#   ask  (JSON)    destructive-but-legitimate ops: reset --hard, clean -f, discarding
#                  worktree changes, branch -D, remote branch delete, stash drop/clear,
#                  history rewrites. Becomes deny when nobody would see the prompt
#                  (auto / bypassPermissions / dontAsk mode) or CLAUDE_GUARD_STRICT=1.
# Silent (exit 0, no output) for everything else. Needs only bash, sed, awk and grep.
#
# How it reads a command: JSON-unescape → join `\`-newline continuations → drop heredoc
# bodies → split into shell segments (; && || | & newline $( ` ( )) → tokens, with quoted
# strings kept as one token. `git` counts only as a segment's command (optionally after
# sudo/env/VAR=/sh -c), so `grep "git push --force" docs` is not a push.
# Best effort against an agent, not a sandbox: a command built at runtime (variables,
# eval, scripts) can evade it. See docs/security.md §7.
set -u

input=$(cat | tr -d '\r\n')

# --- extract fields from the hook JSON (no jq dependency) ---------------------------
field() { printf '%s' "$input" | sed -E -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\".*/\\1/p"; }
raw=$(field command)
mode=$(field permission_mode)
if [ -z "$raw" ]; then
  case "$input" in
    *'"command"'*) echo "Blocked by guard-bash.sh: could not parse the command; refusing to guess." >&2; exit 2 ;;
    *) exit 0 ;;
  esac
fi

# JSON-unescape the parts that matter (bash expansion: portable to macOS bash 3.2).
c=$raw
c=${c//\\\\/$'\001'}
c=${c//\\n/$'\n'}
c=${c//\\r/$'\n'}
c=${c//\\t/ }
c=${c//\\\"/\"}
c=${c//\\\//\/}
c=${c//$'\001'/\\}
c=${c//\\$'\n'/ }                 # line continuations: `git push \⏎ --force`

# Heredoc bodies are data (commit messages, file contents), not commands.
noheredoc=$(printf '%s\n' "$c" | awk '
  skip != "" { t = $0; sub(/^[ \t]+/, "", t); if (t == skip) skip = ""; next }
  { print
    if (match($0, /<<-?[ \t]*["'"'"'\\]?[A-Za-z_][A-Za-z0-9_]*/)) {
      w = substr($0, RSTART, RLENGTH); sub(/^<<-?[ \t]*["'"'"'\\]?/, "", w); skip = w } }')

# Segment a command, one segment per line. Mode "keep": quoted strings stay one token
# (spaces → \001, separators → \002). Mode "strip": quotes are just removed, so
# `sh -c 'git push -f'` exposes the inner command.
segments() { # mode
  printf '%s\n' "$noheredoc" | awk -v mode="$1" '
    { text = text (NR > 1 ? "\n" : "") $0 }
    END {
      q = ""; out = ""
      for (i = 1; i <= length(text); i++) {
        ch = substr(text, i, 1)
        if (q != "") {
          if (ch == q) { q = ""; continue }
          if (mode == "keep") {
            if (ch ~ /[ \t\n]/) ch = "\001"
            else if (ch ~ /[;&|()`<>$]/) ch = "\002"
          } else if (ch ~ /[()]/ && !(ch == "(" && substr(text, i - 1, 1) == "$")) {
            ch = " "   # a quoted "(" is text; only "$(" runs a command
          }
          out = out ch; continue
        }
        if (ch == "\"" || ch == "\047") { q = ch; continue }
        if (ch == "\\") {   # `\ ` keeps a path with spaces one token
          if (mode == "keep" && substr(text, i + 1, 1) == " ") { out = out "\001"; i++ }
          continue
        }
        out = out ch
      }
      gsub(/<<-?[ \t]*[A-Za-z_][A-Za-z0-9_]*/, " ", out)   # heredoc operator + delimiter
      gsub(/&&|\|\||\$\(|[;&|`()]/, "\n", out)
      gsub(/</, " < ", out); gsub(/>/, " > ", out)
      print out
    }'
}
kept=$(segments keep)
stripped=$(segments strip)

deny()  { echo "Blocked by .claude/hooks/guard-bash.sh: $1" >&2; exit 2; }
ask() {
  case "${CLAUDE_GUARD_STRICT:-0}:$mode" in
    1:*|*:auto|*:bypassPermissions|*:dontAsk)
      deny "$1 — needs a human decision and none would be asked in this mode. Ask the user to run it." ;;
  esac
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"guard-bash.sh: %s"}}\n' "$1"
  exit 0
}

# --- token analysis: secret reads + per-command git argument checks -----------------
# Prints one verdict per line: DENY_SECRET, ADD_AND_COMMIT, COMMIT_PATHS, ASK_<what>.
analyze() { # segments
  printf '%s\n' "$1" | awk '
    function base(t) { sub(/^.*\//, "", t); sub(/\.exe$/, "", t); return t }
    function secret(t,   s) {
      s = " " t " "; gsub(/[\001\002"\047`]/, " ", s)
      gsub(/\.env\.(example|sample|template|dist)/, "ENV_TEMPLATE", s)
      return s ~ /[ \/=<(,]\.env(\.[A-Za-z0-9_-]+)*[ ),*?>;|&[]/ ||
             s ~ /[^ \/]*\.(pem|key|p12|pfx|jks|keystore)[ ),*?>;|&[]/ ||
             s ~ /[ \/=<(,]id_(rsa|dsa|ecdsa|ed25519)[ ),*?>;|&[]/ ||
             s ~ /[ \/]\.(netrc|pgpass)[ ),*?>;|&[]/ ||
             s ~ /\.aws\/credentials|\.docker\/config\.json/
    }
    function is_prefix(t) {
      return t ~ /^(sudo|command|builtin|env|exec|time|nice|nohup|stdbuf|timeout|xargs|then|do|else|!|\{)$/ ||
             t ~ /^[A-Za-z_][A-Za-z0-9_]*=/ || t ~ /^-/ || t ~ /^[0-9]+[smhd]?$/
    }
    BEGIN {
      readers = " cat tac less more head tail nl bat batcat view vi vim nvim nano emacs strings xxd hexdump od base64 base32 grep egrep fgrep rg ag ack awk gawk sed cut sort uniq paste column diff cmp comm jq yq type Get-Content gc Select-String tee dd openssl gpg zip tar 7z scp rsync curl wget nc "
      interp = "^(python[0-9.]*|py|node|deno|bun|perl|ruby|php|pwsh|powershell)$"
      patfirst = " grep egrep fgrep rg ag ack awk gawk sed "
    }
    {
      n = split($0, tk, /[ \t]+/); i = 1
      while (i <= n && (tk[i] == "" || is_prefix(tk[i]))) i++
      if (i <= n && (tk[i] ~ /^(ba|z|da|k)?sh$/) && tk[i+1] == "-c") i += 2   # sh -c <script>: script is one kept token
      if (i > n) next
      cmd = base(tk[i])
      # Input redirect anywhere in the segment reads the file.
      for (j = i; j < n; j++) if (tk[j] == "<" && secret(tk[j+1])) print "DENY_SECRET"
      if (cmd ~ interp) { for (j = i + 1; j <= n; j++) if (secret(tk[j])) print "DENY_SECRET" }
      else if (index(readers, " " cmd " ")) {
        need_pat = index(patfirst, " " cmd " ") > 0
        for (j = i + 1; j <= n; j++) {
          t = tk[j]
          if (t == ">" ) { j++; continue }
          if (need_pat && (t == "-e" || t == "-f" || t == "--regexp" || t == "--file")) { need_pat = 0; j++; continue }
          if (t ~ /^-/ || t == "<" || t == "") continue
          if (need_pat) { need_pat = 0; continue }
          if (secret(t)) print "DENY_SECRET"
        }
      }
      if (cmd != "git") next
      # skip git global options
      i++
      while (i <= n && tk[i] ~ /^-/) {
        if (tk[i] ~ /^(-C|-c|--git-dir|--work-tree|--namespace|--exec-path|--config-env)$/) i++
        i++
      }
      sub_ = tk[i]; i++
      if (sub_ == "add") has_add = 1
      if (sub_ == "commit") {
        has_commit = 1
        for (j = i; j <= n; j++) {
          t = tk[j]
          if (t == ">" || t == "<") { j++; continue }
          if (t ~ /^(-m|-F|-C|-c|-t|--author|--date|--template|--cleanup|--fixup|--squash|--reuse-message|--reedit-message|--file|--message|--trailer)$/) { j++; continue }
          if (t == "--" || t ~ /^(-i|--include|-o|--only)$/ || t ~ /^--pathspec-from-file/) { print "COMMIT_PATHS"; break }
          if (t ~ /^-/ || t == "") continue
          print "COMMIT_PATHS"; break
        }
      }
      if (sub_ == "checkout") {
        args = 0; dot = 0; force = 0; dd = 0
        for (j = i; j <= n; j++) {
          t = tk[j]
          if (t == ">" || t == "<") { j++; continue }
          if (t ~ /^(-b|-B|--orphan)$/) { j++; continue }
          if (t == "--") { dd = 1; continue }
          if (t ~ /^(-f|--force)$/) force = 1
          if (t ~ /^-/ || t == "") continue
          args++; if (t == ".") dot = 1
        }
        if (dd || dot || force || args >= 2) print "ASK_CHECKOUT"
      }
      if (sub_ == "switch") for (j = i; j <= n; j++) if (tk[j] ~ /^(-f|--force|--discard-changes)$/) print "ASK_CHECKOUT"
      if (sub_ == "clean") {
        f = 0; dry = 0
        for (j = i; j <= n; j++) {
          if (tk[j] ~ /^--force$/ || tk[j] ~ /^-[a-zA-Z]*f/) f = 1
          if (tk[j] ~ /^--dry-run$/ || tk[j] ~ /^-[a-zA-Z]*n/) dry = 1
        }
        if (f && !dry) print "ASK_CLEAN"
      }
      if (sub_ == "restore") {
        staged = 0; wt = 0
        for (j = i; j <= n; j++) {
          if (tk[j] ~ /^(--staged|-S)$/) staged = 1
          if (tk[j] ~ /^(--worktree|-W)$/) wt = 1
        }
        if (!staged || wt) print "ASK_RESTORE"
      }
    }
    END { if (has_add && has_commit) print "ADD_AND_COMMIT" }'
}
# Quotes kept: exact tokens. Quotes stripped: also sees `echo "$(cat .env)"`; only its
# secret verdicts are used (stripped messages would look like commit paths).
verdicts="$(analyze "$kept")
$(analyze "$stripped" | grep -x DENY_SECRET)"
has_verdict() { printf '%s\n' "$verdicts" | grep -qx "$1"; }

# Interpreter fed a heredoc (python - <<EOF ... open(".env")): check the body too.
if printf '%s\n' "$c" | grep -Eq '(^|[[:space:]/])(python[0-9.]*|py|node|deno|bun|perl|ruby|php)([[:space:]].*)?<<' &&
   printf '%s\n' "$c" | sed -E 's/\.env\.(example|sample|template|dist)/ENV_TEMPLATE/g' |
     grep -Eq '(^|[^A-Za-z0-9_])\.env(\.[A-Za-z0-9_-]+)*([^A-Za-z0-9_.-]|$)|\.(pem|key)([^A-Za-z0-9_]|$)|id_(rsa|ed25519)'; then
  verdicts="$verdicts
DENY_SECRET"
fi
has_verdict DENY_SECRET &&
  deny "reading a secret file (.env, private keys, credentials). Ask the user for the specific non-secret value you need."

# --- regex rules on whole segments (both views: quotes kept, quotes stripped) --------
S='[[:space:]]'
E="($S|$)"
# Segment start, allowed prefixes (sudo, env, VAR=x, timeout 30, then/do, sh -c), git.
P="^$S*(((sudo|command|builtin|env|exec|time|nice|nohup|stdbuf|timeout|xargs|then|do|else|!|\\{)|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*|-[^[:space:]]+|[0-9]+[smhd]?|(ba|z|da|k)?sh$S+-c)$S+)*([^[:space:]]*/)?git(\\.exe)?"
G="$P($S+(-[cC]$S*[^[:space:]]+|--(git-dir|work-tree|namespace|exec-path|config-env)($S+|=)[^[:space:]]+|--[a-z-]+(=[^[:space:]]*)?|-[a-zA-Z]))*$S+"
has() { printf '%s\n%s\n' "$kept" "$stripped" | grep -Eq -- "$1"; }

case "$kept$stripped" in *git*) ;; *) exit 0 ;; esac

has "${G}add($S.*)?$S(-A|--all|-u|--update|-[a-zA-Z]*[Au][a-zA-Z]*|\.|\./|:/|:/\*|\*)$E" &&
  deny "bulk staging. Stage files by name after reviewing them."
has "${G}commit($S.*)?$S(--all|-[a-zA-Z]*a[a-zA-Z]*)$E" &&
  deny "'git commit -a' stages everything. Stage files by name first."
has "${G}(commit|push|merge|rebase|am|cherry-pick|revert|pull|switch|checkout)$S.*--no-verify$E|${G}commit($S.*)?$S-[a-zA-Z]*n[a-zA-Z]*$E" &&
  deny "--no-verify. Fix what the hook reports instead of bypassing it."
{ printf '%s\n%s\n' "$kept" "$stripped" | grep -Eiq -- "${G}.*-c$S*core\.hookspath=|${G}config($S+--[a-z]+(=[^[:space:]]+)?)*$S+core\.hookspath$S+[^-[:space:]]"; } &&
  deny "changing git's hooks path. Fix what the hook reports instead of bypassing it."
{ printf '%s\n%s\n' "$kept" "$stripped" | grep -E -- "$G" | grep -Eq -- "(^|$S)(HUSKY=0|SKIP=[^[:space:]]*gitleaks)$S"; } &&
  deny "disabling git hooks. Fix what the hook reports instead of bypassing it."
has "${G}push($S.*)?$S(-[a-zA-Z]*f[a-zA-Z]*|--force[a-z-]*(=[^[:space:]]*)?|--mirror|\+[^[:space:]]+)$E" &&
  deny "force push / mirror push. Ask the user to do it themselves if it's really needed."
has_verdict ADD_AND_COMMIT &&
  deny "'git add' and 'git commit' in one command: the secret scan runs before the command, so it can't see what this add stages. Stage first, then commit in a separate command."
has_verdict COMMIT_PATHS &&
  deny "'git commit <paths>' (or -i/-o/--) commits files the staged-diff secret scan never sees. Stage the files with 'git add <file>', then run 'git commit -m ...'."

# --- ask (destructive but sometimes intended) -------------------------------------
has "${G}reset($S.*)?$S--(hard|merge|keep)$E" && ask "git reset --hard discards uncommitted work"
has_verdict ASK_CLEAN && ask "git clean -f deletes untracked files"
has_verdict ASK_CHECKOUT && ask "git checkout/switch that overwrites working-tree changes"
has_verdict ASK_RESTORE && ask "git restore discards working-tree changes"
has "${G}branch($S.*)?$S(-[a-zA-Z]*D[a-zA-Z]*|--delete$S.*--force|--force$S.*--delete)$E" && ask "git branch -D deletes an unmerged branch"
has "${G}push($S.*)?$S(--delete|-d|:[^[:space:]]+)$E" && ask "deleting a remote branch or tag"
has "${G}stash$S+(drop|clear)$E" && ask "git stash drop/clear loses stashed work"
has "${G}(filter-branch|filter-repo|replace)$E|${G}reflog$S+(expire|delete)|${G}update-ref($S.*)?$S-d$E|${G}gc($S.*)?$S--prune" &&
  ask "rewriting history or deleting refs"

# --- secret scan before every commit ------------------------------------------------
if has "${G}commit$E"; then
  dir=$(cd "$(dirname "$0")" && pwd)
  if ! out=$(bash "$dir/scan-secrets.sh" --staged 2>&1); then
    deny "staged changes look like they contain secrets.
$out
Unstage them (git restore --staged <file>) and move the value to env/secret storage."
  fi
fi
exit 0
