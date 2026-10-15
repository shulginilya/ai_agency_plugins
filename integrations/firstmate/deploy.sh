#!/usr/bin/env bash
# Deploy the firstmate integration into a firstmate home's gitignored config/.
#
# Usage: integrations/firstmate/deploy.sh [--with-plugins] [FM_HOME]
#   FM_HOME         firstmate home; defaults to $FM_HOME, then ~/firstmate
#   --with-plugins  also install the crew plugins at user scope for Claude Code;
#                   refused while any crewmate of FM_HOME is live
#
# Copies (never symlinks) every deployable file below into <FM_HOME>/config/.
# A file that already exists there with different content is backed up to
# <name>.bak first, so a local hand-edit is never lost silently.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
files=(brief-include.md crew-dispatch.json)   # deployed when present
# Only these go into ~/.claude, which every Claude crewmate runs from. Any other
# plugin would load its hooks into every crew session, so a new plugin stays out
# until it is added here and routed in brief-include.md.
crew_plugins=(developer code-review scrum-master designer)
for p in "${crew_plugins[@]}"; do
  [ -f "$repo/plugins/$p/plugin.json" ] || { echo "crew plugin not found: plugins/$p" >&2; exit 1; }
done

with_plugins=0
fm_home=""
for arg in "$@"; do
  case "$arg" in
    --with-plugins) with_plugins=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) fm_home="$arg" ;;
  esac
done
fm_home="${fm_home:-${FM_HOME:-$HOME/firstmate}}"

if [ ! -f "$fm_home/AGENTS.md" ] || [ ! -d "$fm_home/bin" ]; then
  echo "not a firstmate home: $fm_home (pass the path or set FM_HOME)" >&2
  exit 1
fi

# apkit install deletes ~/.claude/skills/<plugin> and copies the new build in, under
# every running crewmate. firstmate keeps state/<id>.meta for exactly as long as a
# task is live (fm-teardown.sh removes it), so refuse while any exists - before
# anything is written, so a refused run changes nothing.
if [ "$with_plugins" -eq 1 ]; then
  live=()
  for meta in "$fm_home"/state/*.meta; do
    [ -f "$meta" ] && live+=("$(basename "$meta" .meta)")
  done
  if [ "${#live[@]}" -gt 0 ]; then
    echo "refusing --with-plugins: ${#live[@]} crewmate(s) live in $fm_home: ${live[*]}" >&2
    echo "replacing plugins under them would break them. Let them finish or tear them down, then rerun." >&2
    exit 1
  fi
fi

if grep -q 'Delivery contract: mode=' "$here/brief-include.md"; then
  echo "brief-include.md must not contain a 'Delivery contract: mode=' line" >&2
  exit 1
fi
if [ -f "$here/crew-dispatch.json" ] && command -v jq >/dev/null; then
  jq empty "$here/crew-dispatch.json" || { echo "crew-dispatch.json is not valid JSON" >&2; exit 1; }
fi

mkdir -p "$fm_home/config"
for f in "${files[@]}"; do
  src="$here/$f"; dst="$fm_home/config/$f"
  [ -f "$src" ] || continue
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    echo "unchanged  $dst"; continue
  fi
  if [ -f "$dst" ]; then cp -p "$dst" "$dst.bak"; echo "backed up  $dst.bak"; fi
  install -m 644 "$src" "$dst"
  echo "deployed   $dst"
done

# Keep deployed files out of the firstmate clone's git status. Upstream firstmate
# gitignores config/, but some clones and copies do not: hide an untracked file
# through the clone-local .git/info/exclude, and a tracked one with
# skip-worktree. Neither edits a tracked firstmate file, so updates stay clean.
if git -C "$fm_home" rev-parse --git-dir >/dev/null 2>&1; then
  exclude="$(git -C "$fm_home" rev-parse --git-path info/exclude)"
  case "$exclude" in /*) ;; *) exclude="$fm_home/$exclude" ;; esac
  for f in "${files[@]}"; do
    rel="config/$f"
    [ -f "$fm_home/$rel" ] || continue
    if git -C "$fm_home" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
      git -C "$fm_home" update-index --skip-worktree "$rel"
      echo "git: $rel is tracked in this firstmate clone; marked skip-worktree"
    elif ! git -C "$fm_home" check-ignore -q "$rel"; then
      mkdir -p "$(dirname "$exclude")"
      grep -qxF "/$rel" "$exclude" 2>/dev/null || echo "/$rel" >> "$exclude"
      echo "git: $rel was not ignored; added to .git/info/exclude"
    fi
  done
  # Backups this script writes must not show up either.
  if ! git -C "$fm_home" check-ignore -q "config/x.bak"; then
    grep -qxF "/config/*.bak" "$exclude" 2>/dev/null || echo "/config/*.bak" >> "$exclude"
  fi
fi

if [ "$with_plugins" -eq 1 ]; then
  py="$(command -v python3 || command -v python || true)"
  [ -n "$py" ] || { echo "python not found" >&2; exit 1; }
  # install copies from dist/, which is gitignored and goes stale; rebuild first.
  build_args=()
  for p in "${crew_plugins[@]}"; do build_args+=(--plugin "$p"); done
  (cd "$repo" && "$py" -m tools.apkit build --target claude-code "${build_args[@]}")
  for p in "${crew_plugins[@]}"; do
    (cd "$repo" && "$py" -m tools.apkit install "$p" --target claude-code --scope user)
  done
fi

echo "done. New briefs pick this up on the next dispatch; running crewmates keep their brief."
