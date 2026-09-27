#!/usr/bin/env bash
#
# marketplace.sh -- regenerate .claude-plugin/marketplace.json after adding a plugin.
#
# The index is generated from every plugins/*/plugin.json by `apkit marketplace`.
# This wrapper adds the parts that went wrong by hand: it validates the whole
# tree first (every plugin lands in the index, not just the new one) and
# reports what changed by name and version. It works on any branch.
#
# Two open branches that each regenerate the index will conflict on it when
# the second one merges. Never hand-merge the file: when a merge, rebase or
# cherry-pick stops on it, run this script again -- it rebuilds the whole index
# from the merged tree and marks the conflict resolved. CI also regenerates it
# on main after every merge (docs/release.md), so main converges either way.
#
#   tools/marketplace.sh recruiter-inbox      # validate, regenerate, confirm it is listed
#   tools/marketplace.sh --commit             # ...and commit only the index
#   tools/marketplace.sh --check              # would CI change the index? writes nothing
#   tools/marketplace.sh --local              # path-form index for `/plugin marketplace add .`
#   tools/marketplace.sh --ref "$(git rev-parse origin/dist)"   # pin to one dist build
#   tools/marketplace.sh -n                   # print the commands, run nothing
#
# Exit status: 0 written or already current, 1 --check found the index stale,
# 2 refused or failed.

set -uo pipefail

SCRIPT_NAME=$(basename "$0")
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# ---------------------------------------------------------------- defaults --

INDEX=.claude-plugin/marketplace.json
COMMIT_MESSAGE="chore(marketplace): regenerate index"

EXPECTED=()
MODE="write"        # write | check | local
DO_COMMIT=0
DO_VALIDATE=1
DRY_RUN=0
REF=""

# shellcheck source=tools/_common.sh
. "$ROOT/tools/_common.sh"

usage() {
  cat <<'USAGE'
Regenerate .claude-plugin/marketplace.json from every plugin under plugins/.

Usage:
  tools/marketplace.sh [options] [plugin[,plugin...]]

Name the plugin you just added and the script fails unless the regenerated
index lists it. The index itself is always generated from the whole tree.

Works on any branch. If a merge or rebase stops on a conflict in the index,
run it again: it rebuilds the file from the merged tree and stages it.

Modes (pick one)
  (default)                validate, then write the committed (git-subdir) form
  -c, --check              regenerate, compare, restore. Writes nothing.
                           Exit 1 when the committed index is stale.
      --local              build claude-code bundles and write the path form,
                           for `/plugin marketplace add .`. Never commit it.

Options
      --commit             after writing, commit only the index
      --ref <ref>          branch, tag or sha the entries fetch from (default: dist)
      --skip-validate      do not run `apkit validate --strict` first
  -n, --dry-run            print every command, execute none
  -h, --help               this

Environment
  PYTHON                   interpreter to use (default: first working
                           Python 3.9+ of python3, python, py)
USAGE
}

# ------------------------------------------------------------------- parse --

set_mode() {
  [ "$MODE" = write ] || [ "$MODE" = "$1" ] || die "--check and --local cannot be combined"
  MODE=$1
}

while [ $# -gt 0 ]; do
  case "$1" in
    -c|--check)        set_mode check ;;
    --local)           set_mode local ;;
    --commit)          DO_COMMIT=1 ;;
    --ref)
      [ $# -ge 2 ] || die "--ref needs a value"
      REF=$2; shift ;;
    --skip-validate)   DO_VALIDATE=0 ;;
    -n|--dry-run)      DRY_RUN=1 ;;
    -h|--help)         usage; exit 0 ;;
    -*)                die "unknown option: $1 (try --help)" ;;
    *)
      while IFS= read -r piece || [ -n "$piece" ]; do EXPECTED+=("$piece"); done < <(split_commas "$1") ;;
  esac
  shift
done

[ "$DO_COMMIT" = 1 ] && [ "$MODE" != write ] \
  && die "--commit only goes with the default mode: a --check writes nothing, and a --local index must never be committed"
[ -n "$REF" ] && [ "$MODE" = local ] \
  && die "--ref does not apply to --local: the path form points at your own dist/"

PY=$(pick_python) || exit $?

ALL_PLUGIN_NAMES=()
while IFS= read -r line; do ALL_PLUGIN_NAMES+=("$line"); done < <(available_plugins)
[ ${#ALL_PLUGIN_NAMES[@]} -gt 0 ] || die "no plugins found under $ROOT/plugins"

for name in ${EXPECTED[@]+"${EXPECTED[@]}"}; do
  contains "$name" "${ALL_PLUGIN_NAMES[@]}" \
    || die "no plugins/$name/plugin.json -- known plugins: ${ALL_PLUGIN_NAMES[*]}"
done

cd "$ROOT" || die "cannot enter $ROOT"

# --------------------------------------------------------------------- git --

# --no-optional-locks: reading the branch or a diff must never leave an
# index.lock behind, which some sandboxed shells cannot delete.
GIT=(git --no-optional-locks -C "$ROOT")
IN_GIT=0
BRANCH=""
if command -v git >/dev/null 2>&1 && "${GIT[@]}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  IN_GIT=1
  BRANCH=$("${GIT[@]}" symbolic-ref --quiet --short HEAD 2>/dev/null || true)   # empty when detached
fi

# Plugins on disk that git does not know about yet. The index would list them,
# but the dist branch CI publishes cannot contain them until they are committed
# and merged to main.
untracked_plugins() {
  [ "$IN_GIT" = 1 ] || return 0
  local name
  for name in "${ALL_PLUGIN_NAMES[@]}"; do
    "${GIT[@]}" ls-files --error-unmatch -- "plugins/$name/plugin.json" >/dev/null 2>&1 \
      || printf '%s\n' "$name"
  done
}

UNTRACKED=()
while IFS= read -r line; do UNTRACKED+=("$line"); done < <(untracked_plugins)

# ------------------------------------------------------------------ guards --

# Which operation stopped on a conflict, for the "continue with" hint.
in_progress() {
  local dir
  dir=$("${GIT[@]}" rev-parse --git-dir 2>/dev/null) || { printf 'git merge'; return; }
  case "$dir" in /*|[A-Za-z]:[\\/]*) ;; *) dir=$ROOT/$dir ;; esac
  if [ -d "$dir/rebase-merge" ] || [ -d "$dir/rebase-apply" ]; then printf 'git rebase'
  elif [ -f "$dir/CHERRY_PICK_HEAD" ]; then printf 'git cherry-pick'
  elif [ -f "$dir/REVERT_HEAD" ]; then printf 'git revert'
  else printf 'git merge'
  fi
}

# A merge, rebase or cherry-pick that stopped on the index. The file holds
# conflict markers then, so it is regenerated whole from the merged tree
# rather than merged by hand -- the tree is the source of truth, not the file.
CONFLICTED=0
if [ "$IN_GIT" = 1 ] && "${GIT[@]}" diff --name-only --diff-filter=U -- "$INDEX" 2>/dev/null | grep -q .; then
  CONFLICTED=1
fi

if [ "$CONFLICTED" = 1 ]; then
  [ "$MODE" = write ] \
    || die "$INDEX is in conflict; run without --check/--local to rebuild it from the merged tree"
  [ "$DO_COMMIT" = 1 ] \
    && die "$INDEX is in conflict: let the script resolve it without --commit, then finish the merge or rebase"
fi

if [ "$DO_COMMIT" = 1 ] && [ ${#UNTRACKED[@]} -gt 0 ]; then
  die "not committing: the index would list plugins git does not track yet: ${UNTRACKED[*]}
Commit the plugin first, so the index never names a bundle CI cannot publish."
fi

# ---------------------------------------------------------------- helpers --

run() {  # run <command...>
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s$%s %s\n' "$C_DIM" "$C_OFF" "$*"
    return 0
  fi
  "$@"
}

apkit() { run "$PY" -m tools.apkit --root "$ROOT" "$@"; }

BACKUP=""
HAD_INDEX=0
# shellcheck disable=SC2329  # invoked by the EXIT trap
cleanup() {
  [ -n "$BACKUP" ] && rm -f "$BACKUP"
  return 0
}
trap cleanup EXIT

# The previous index, so we can say what changed -- and, for --check, put back.
snapshot() {
  BACKUP=$(mktemp "${TMPDIR:-/tmp}/marketplace.XXXXXX") || die "cannot create a temp file"
  if [ -f "$INDEX" ]; then
    HAD_INDEX=1
    cp -p "$INDEX" "$BACKUP" || die "cannot copy $INDEX"
  else
    printf '{}\n' > "$BACKUP"
  fi
}

restore() {
  if [ "$HAD_INDEX" = 1 ]; then
    cp -p "$BACKUP" "$INDEX" || die "could not restore $INDEX from $BACKUP -- restore it with: git restore -- $INDEX"
  else
    rm -f "$INDEX"
  fi
}

# summarise <old> <new> [expected...]: print the changes by plugin.
# Returns 0 unchanged, 3 changed, 4 an expected plugin is missing (also printed).
summarise() {
  "$PY" - "$@" <<'PY'
import json
import sys

old_path, new_path, expected = sys.argv[1], sys.argv[2], sys.argv[3:]


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    entries = {e.get("name"): e for e in data.get("plugins") or [] if isinstance(e, dict)}
    rest = {k: v for k, v in data.items() if k != "plugins"}
    return entries, rest


old, old_rest = load(old_path)
new, new_rest = load(new_path)
lines = []
for name in sorted(set(new) - set(old)):
    lines.append("  + %-22s %s" % (name, new[name].get("version", "?")))
for name in sorted(set(old) - set(new)):
    lines.append("  - %-22s %s" % (name, old[name].get("version", "?")))
for name in sorted(set(old) & set(new)):
    a, b = old[name], new[name]
    if a == b:
        continue
    what = []
    if a.get("version") != b.get("version"):
        what.append("%s -> %s" % (a.get("version"), b.get("version")))
    what += [key for key in sorted((set(a) | set(b)) - {"name", "version"}) if a.get(key) != b.get(key)]
    lines.append("  ~ %-22s %s" % (name, ", ".join(what)))
if old_rest != new_rest and old_rest:
    changed = sorted(k for k in set(old_rest) | set(new_rest) if old_rest.get(k) != new_rest.get(k))
    lines.append("  ~ %-22s %s" % ("(index)", ", ".join(changed)))

missing = [name for name in expected if name not in new]
if lines:
    print("\n".join(lines))
for name in missing:
    print("  ! %-22s not in the regenerated index" % name)
sys.exit(4 if missing else (3 if lines else 0))
PY
}

# ---------------------------------------------------------------- the work --

say "${C_BOLD}${SCRIPT_NAME}${C_OFF} mode $MODE${BRANCH:+, branch $BRANCH}, ${#ALL_PLUGIN_NAMES[@]} plugin(s)"
[ ${#EXPECTED[@]} -gt 0 ] && info "  expecting: ${EXPECTED[*]}"
[ "$DRY_RUN" = 1 ] && info "  dry run: nothing will be executed"
say ""

if [ "$DO_VALIDATE" = 1 ]; then
  say "${C_BOLD}validate${C_OFF}"
  apkit validate --strict \
    || die "validation failed -- every plugin goes into the index, so every plugin has to validate.
A directory named above without a plugin.json is usually a leftover __pycache__ from another branch."
  say ""
fi

market_args=()
case "$MODE" in
  local)
    say "${C_BOLD}build${C_OFF} claude-code bundles for the path-form index"
    build_args=(build --target claude-code)
    [ "$DO_VALIDATE" = 1 ] && build_args+=(--skip-validate)   # already done, strictly
    apkit "${build_args[@]}" || die "build failed"
    say ""
    market_args=(--publish path) ;;
  *)
    [ -n "$REF" ] && market_args=(--ref "$REF") ;;
esac

if [ "$DRY_RUN" = 1 ]; then
  apkit marketplace ${market_args[@]+"${market_args[@]}"}
  [ "$MODE" = check ] && info "(the old index would be compared and restored)"
  [ "$DO_COMMIT" = 1 ] && run "${GIT[@]}" add -- "$INDEX" \
    && run "${GIT[@]}" commit -m "$COMMIT_MESSAGE" --only -- "$INDEX"
  say ""
  info "dry run -- nothing was executed"
  exit 0
fi

snapshot
say "${C_BOLD}regenerate${C_OFF}"
if ! apkit marketplace ${market_args[@]+"${market_args[@]}"}; then
  restore
  die "apkit marketplace failed; $INDEX is unchanged"
fi
say ""

if [ "$CONFLICTED" = 1 ]; then
  # the file on disk is conflict markers; report the change against HEAD's copy
  "${GIT[@]}" show "HEAD:$INDEX" > "$BACKUP" 2>/dev/null || : > "$BACKUP"
fi
summarise "$BACKUP" "$INDEX" ${EXPECTED[@]+"${EXPECTED[@]}"}
status=$?
say ""

if [ "$MODE" = check ]; then
  restore
  case "$status" in
    0) say "${C_GREEN}current${C_OFF} $INDEX matches the tree"; exit 0 ;;
    4) die "the index would not list every plugin you named" ;;
  esac
  say "${C_YELLOW}stale${C_OFF} regenerating would change $INDEX as above (nothing was written)"
  info "rebuild it with: $SCRIPT_NAME"
  exit 1
fi

[ "$status" = 4 ] && die "the regenerated index does not list every plugin you named"

if [ "$CONFLICTED" = 1 ]; then
  "${GIT[@]}" add -- "$INDEX" || die "rebuilt $INDEX but could not stage it: git add -- $INDEX"
  say "${C_GREEN}resolved${C_OFF} $INDEX rebuilt from the merged tree and staged"
  info "then: $(in_progress) --continue"
  exit 0
fi

if [ "$status" = 0 ]; then
  say "${C_GREEN}current${C_OFF} $INDEX already matched the tree; nothing changed"
else
  say "${C_GREEN}written${C_OFF} $INDEX"
fi

if [ "$MODE" = local ]; then
  warn "this is the path form: it points at your own dist/ and must never be committed.
      /plugin marketplace add .            # try it in Claude Code
      git restore -- $INDEX   # put the committed form back when done"
  exit 0
fi

if [ ${#UNTRACKED[@]} -gt 0 ]; then
  warn "the index lists plugins git does not track yet: ${UNTRACKED[*]}
      commit them before (or with) the index, never after it"
fi

if [ "$DO_COMMIT" = 1 ]; then
  if [ "$status" = 0 ]; then
    info "nothing to commit"
  else
    "${GIT[@]}" add -- "$INDEX" || die "git add failed"
    "${GIT[@]}" commit -q -m "$COMMIT_MESSAGE" --only -- "$INDEX" || die "git commit failed"
    say "${C_GREEN}committed${C_OFF} $("${GIT[@]}" log -1 --format='%h %s')"
    info "push when ready: git push   (entries install once CI has published the dist branch from main)"
  fi
elif [ "$status" != 0 ] && [ "$IN_GIT" = 1 ] && [ ${#UNTRACKED[@]} -eq 0 ]; then
  info "commit it with --commit, or: git add $INDEX && git commit -m \"$COMMIT_MESSAGE\""
fi
exit 0
