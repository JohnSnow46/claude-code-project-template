#!/usr/bin/env bash
# Install scripts/git-hooks/* into this clone's git hooks directory.
# An existing hook with different content is kept as <name>.local-backup, never overwritten silently.
set -eu
root=$(git rev-parse --show-toplevel)
hooks=$(git rev-parse --git-path hooks)
case "$hooks" in /*|[A-Za-z]:*) ;; *) hooks="$root/$hooks" ;; esac
mkdir -p "$hooks"
for src in "$root"/scripts/git-hooks/*; do
  name=$(basename "$src"); dst="$hooks/$name"
  if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
    mv "$dst" "$dst.local-backup"
    echo "kept your previous $name as $dst.local-backup"
  fi
  cp "$src" "$dst"; chmod +x "$dst"
  echo "installed $name -> $dst"
done
