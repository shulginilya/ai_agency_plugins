#!/usr/bin/env bash
#
# install.sh -- build and install plugins from this repo into a harness.
#
# A thin, opinionated wrapper around `python -m tools.apkit`. It exists because
# apkit installs one plugin into one harness per invocation, and the thing you
# actually want to type is "all of them, into Claude Code".
#
#   tools/install.sh interview-prep                 # one plugin, claude-code, user scope
#   tools/install.sh --all                          # every plugin
#   tools/install.sh -a -T                          # every plugin, every harness
#   tools/install.sh job-hunter,interview-prep -t claude-code -t cursor
#   tools/install.sh -a -s project --into ~/work/repo
#   tools/install.sh -a -n                          # print the commands, run nothing
#   tools/install.sh -l                             # what is available
#   tools/install.sh -u interview-prep              # uninstall instead
#
# Exit status is the number of failed (plugin, target) pairs, capped at 125;
# 0 when everything installed.

set -uo pipefail

SCRIPT_NAME=$(basename "$0")
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
INVOKED_FROM=$PWD

# ---------------------------------------------------------------- defaults --

PLUGINS=()
TARGETS=()
SCOPE=user
INTO=""
DIST_DIR=""
ALL_PLUGINS=0
ALL_TARGETS=0
DO_BUILD=1
DO_VALIDATE=1
CLEAN=0
LINK=0
DRY_RUN=0
KEEP_GOING=1
UNINSTALL=0
DEFAULT_TARGET=claude-code

# shellcheck source=tools/_common.sh
. "$ROOT/tools/_common.sh"

usage() {
  cat <<'USAGE'
Build and install this repo's plugins into one or more harnesses.

Usage:
  tools/install.sh [options] [plugin ...]

Plugins are positional and may be repeated, comma-separated, or both:
  tools/install.sh code-review debugger
  tools/install.sh code-review,debugger

Selecting plugins
  -a, --all                every plugin under plugins/ (skips _template)
  -l, --list               list available plugins and targets, then exit

Selecting harnesses
  -t, --target NAME        repeatable; comma-separated accepted (default: claude-code)
  -T, --all-targets        every target under targets/

Where it lands
  -s, --scope user|project install scope (default: user)
      --into DIR           project-scope destination (default: the directory you ran this from)
      --link               symlink instead of copying, where the target allows it
      --dist-dir DIR       read and write built bundles here instead of ./dist

Build behaviour
      --no-build           install what is already in dist/, build nothing
      --clean              wipe the output directory before building
      --skip-validate      do not validate sources before building

Other
  -u, --uninstall          remove previous installs instead of installing
  -n, --dry-run            print every command, execute none
  -x, --fail-fast          stop at the first failure (default: keep going)
  -h, --help               this

Environment
  PYTHON                   interpreter to use (default: first working
                           Python 3.9+ of python3, python, py)
USAGE
}

# ------------------------------------------------------------------- parse --

while [ $# -gt 0 ]; do
  case "$1" in
    -a|--all)          ALL_PLUGINS=1 ;;
    -T|--all-targets)  ALL_TARGETS=1 ;;
    -t|--target)
      [ $# -ge 2 ] || die "$1 needs a value"
      while IFS= read -r piece || [ -n "$piece" ]; do TARGETS+=("$piece"); done < <(split_commas "$2")
      shift ;;
    -t=*|--target=*)
      while IFS= read -r piece || [ -n "$piece" ]; do TARGETS+=("$piece"); done < <(split_commas "${1#*=}") ;;
    -s|--scope)        [ $# -ge 2 ] || die "$1 needs a value"; SCOPE=$2; shift ;;
    -s=*|--scope=*)    SCOPE=${1#*=} ;;
    --into)            [ $# -ge 2 ] || die "$1 needs a value"; INTO=$2; shift ;;
    --into=*)          INTO=${1#*=} ;;
    --dist-dir)        [ $# -ge 2 ] || die "$1 needs a value"; DIST_DIR=$2; shift ;;
    --dist-dir=*)      DIST_DIR=${1#*=} ;;
    --link)            LINK=1 ;;
    --no-build)        DO_BUILD=0 ;;
    --clean)           CLEAN=1 ;;
    --skip-validate)   DO_VALIDATE=0 ;;
    -u|--uninstall)    UNINSTALL=1 ;;
    -n|--dry-run)      DRY_RUN=1 ;;
    -x|--fail-fast)    KEEP_GOING=0 ;;
    -l|--list)         LIST_ONLY=1 ;;
    -h|--help)         usage; exit 0 ;;
    --)                shift; while [ $# -gt 0 ]; do PLUGINS+=("$1"); shift; done; break ;;
    -*)                die "unknown option: $1 (try --help)" ;;
    *)
      while IFS= read -r piece || [ -n "$piece" ]; do PLUGINS+=("$piece"); done < <(split_commas "$1") ;;
  esac
  shift
done

PY=$(pick_python) || exit $?

# Portable stand-ins for `mapfile`, which bash 3.2 (still shipped by macOS) lacks.
ALL_PLUGIN_NAMES=()
while IFS= read -r line; do ALL_PLUGIN_NAMES+=("$line"); done < <(available_plugins)
ALL_TARGET_NAMES=()
while IFS= read -r line; do ALL_TARGET_NAMES+=("$line"); done < <(available_targets)

[ ${#ALL_PLUGIN_NAMES[@]} -gt 0 ] || die "no plugins found under $ROOT/plugins"
[ ${#ALL_TARGET_NAMES[@]} -gt 0 ] || die "no targets found under $ROOT/targets"

if [ "${LIST_ONLY:-0}" = 1 ]; then
  say "${C_BOLD}Plugins${C_OFF} ($ROOT/plugins)"
  for name in "${ALL_PLUGIN_NAMES[@]}"; do
    version=$("$PY" - "$ROOT/plugins/$name/plugin.json" <<'PYEOF' 2>/dev/null || true
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("version", "?"))
PYEOF
)
    printf '  %-18s %s\n' "$name" "${version:-?}"
  done
  say ""
  say "${C_BOLD}Targets${C_OFF}"
  ( cd "$ROOT" && "$PY" -m tools.apkit targets ) | sed 's/^/  /'
  exit 0
fi

# ------------------------------------------------------------- resolve sets --

if [ "$ALL_PLUGINS" = 1 ]; then
  PLUGINS=("${ALL_PLUGIN_NAMES[@]}")
elif [ ${#PLUGINS[@]} -eq 0 ]; then
  usage >&2
  say "" >&2
  die "name at least one plugin, or pass --all"
fi

if [ "$ALL_TARGETS" = 1 ]; then
  TARGETS=("${ALL_TARGET_NAMES[@]}")
elif [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=("$DEFAULT_TARGET")
fi

for name in "${PLUGINS[@]}"; do
  contains "$name" "${ALL_PLUGIN_NAMES[@]}" \
    || die "unknown plugin: $name
known plugins: ${ALL_PLUGIN_NAMES[*]}"
done

for name in "${TARGETS[@]}"; do
  contains "$name" "${ALL_TARGET_NAMES[@]}" \
    || die "unknown target: $name
known targets: ${ALL_TARGET_NAMES[*]}"
done

case "$SCOPE" in
  user|project) ;;
  *) die "--scope must be user or project, got: $SCOPE" ;;
esac

# Resolve --into against the directory the user ran this from, not the repo
# root, because everything below runs with cwd set to the repo root.
if [ "$SCOPE" = project ]; then
  if [ -z "$INTO" ]; then
    INTO=$INVOKED_FROM
  else
    case "$INTO" in
      /*|[A-Za-z]:[\\/]*) ;;
      ~*) INTO=${INTO/#\~/$HOME} ;;
      *)  INTO=$INVOKED_FROM/$INTO ;;
    esac
  fi
  [ -d "$INTO" ] || die "--into is not a directory: $INTO"
elif [ -n "$INTO" ]; then
  warn "--into is ignored with --scope user"
fi

# ---------------------------------------------------------------- the work --

FAILURES=0
declare -a REPORT=()

run() {  # run <command...>
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s$%s %s\n' "$C_DIM" "$C_OFF" "$*"
    return 0
  fi
  "$@"
}

record() { REPORT+=("$1"); }

# In a dry run nothing ran, so the summary must not claim success.
verb() { [ "$DRY_RUN" = 1 ] && printf 'planned' || printf '%s' "$1"; }

apkit() { run "$PY" -m tools.apkit --root "$ROOT" "$@"; }

cd "$ROOT" || die "cannot enter $ROOT"

plugin_args=()
for name in "${PLUGINS[@]}"; do plugin_args+=(--plugin "$name"); done
target_args=()
for name in "${TARGETS[@]}"; do target_args+=(--target "$name"); done

say "${C_BOLD}${SCRIPT_NAME}${C_OFF} ${#PLUGINS[@]} plugin(s) -> ${#TARGETS[@]} target(s), ${SCOPE} scope"
info "  plugins: ${PLUGINS[*]}"
info "  targets: ${TARGETS[*]}"
[ "$SCOPE" = project ] && info "  into:    $INTO"
[ "$DRY_RUN" = 1 ] && info "  dry run: nothing will be executed"
say ""

if [ "$UNINSTALL" = 1 ]; then
  for plugin in "${PLUGINS[@]}"; do
    for target in "${TARGETS[@]}"; do
      if apkit uninstall "$plugin" --target "$target"; then
        record "${C_GREEN}$(verb removed)${C_OFF}  $plugin -> $target"
      else
        record "${C_RED}failed${C_OFF}   $plugin -> $target (uninstall)"
        FAILURES=$((FAILURES + 1))
        [ "$KEEP_GOING" = 1 ] || break 2
      fi
    done
  done
else
  if [ "$DO_BUILD" = 1 ]; then
    if [ "$DO_VALIDATE" = 1 ]; then
      say "${C_BOLD}validate${C_OFF}"
      apkit validate "${plugin_args[@]}" --strict \
        || die "validation failed -- fix the source, or pass --skip-validate to build anyway"
      say ""
    fi
    say "${C_BOLD}build${C_OFF}"
    build_args=("${plugin_args[@]}" "${target_args[@]}")
    [ "$CLEAN" = 1 ] && build_args+=(--clean)
    [ "$DO_VALIDATE" = 1 ] && build_args+=(--skip-validate)   # already done, strictly
    [ -n "$DIST_DIR" ] && build_args+=(--dist-dir "$DIST_DIR")
    apkit build "${build_args[@]}" || die "build failed"
    say ""
  else
    info "skipping build (--no-build); installing whatever is in ${DIST_DIR:-dist/}"
    say ""
  fi

  say "${C_BOLD}install${C_OFF}"
  for plugin in "${PLUGINS[@]}"; do
    for target in "${TARGETS[@]}"; do
      install_args=("$plugin" --target "$target" --scope "$SCOPE")
      [ "$SCOPE" = project ] && install_args+=(--into "$INTO")
      [ "$LINK" = 1 ] && install_args+=(--link)
      [ -n "$DIST_DIR" ] && install_args+=(--dist-dir "$DIST_DIR")
      if apkit install "${install_args[@]}"; then
        record "${C_GREEN}$(verb ok)${C_OFF}       $plugin -> $target"
      else
        record "${C_RED}failed${C_OFF}   $plugin -> $target"
        FAILURES=$((FAILURES + 1))
        [ "$KEEP_GOING" = 1 ] || break 2
      fi
    done
  done
fi

say ""
say "${C_BOLD}summary${C_OFF}"
for line in "${REPORT[@]}"; do printf '  %s\n' "$line"; done

if [ "$DRY_RUN" = 1 ]; then
  say ""
  info "dry run -- nothing was executed"
  exit 0
fi

if [ "$FAILURES" -gt 0 ]; then
  say ""
  warn "$FAILURES of $(( ${#PLUGINS[@]} * ${#TARGETS[@]} )) pair(s) failed"
  [ "$FAILURES" -gt 125 ] && exit 125
  exit "$FAILURES"
fi

say ""
say "${C_GREEN}done${C_OFF} -- run 'python -m tools.apkit doctor' to see where things landed"
