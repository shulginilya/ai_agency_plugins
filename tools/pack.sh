#!/usr/bin/env bash
#
# pack.sh -- get plugins ready to hand to a harness.
#
# Builds what you name and zips each bundle into one archive the harness can
# ingest directly: a .plugin file for the Claude desktop app, a .zip elsewhere.
# The archive's contents sit at its root, because a wrapper directory is the
# difference between a plugin that installs and one that is silently ignored.
#
#   tools/pack.sh developer                   # one plugin, claude-code
#   tools/pack.sh --all                       # every plugin, claude-code
#   tools/pack.sh -a -t cursor -t codex       # every plugin, two harnesses
#   tools/pack.sh -a -T                       # every plugin, every harness
#   tools/pack.sh developer,qa -o ~/Desktop
#   tools/pack.sh -a -n                       # print the commands, run nothing
#   tools/pack.sh -l                          # what is available
#
# Exit status is 0 when every archive was written, 2 otherwise.

set -uo pipefail

SCRIPT_NAME=$(basename "$0")
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
INVOKED_FROM=$PWD

# ---------------------------------------------------------------- defaults --

PLUGINS=()
TARGETS=()
OUT=""
DIST_DIR=""
ALL_PLUGINS=0
ALL_TARGETS=0
DO_BUILD=1
DO_VALIDATE=1
CLEAN=0
DRY_RUN=0
LIST_ONLY=0
OPEN_DIR=0
DEFAULT_TARGET=claude-code

# shellcheck source=tools/_common.sh
. "$ROOT/tools/_common.sh"

usage() {
  cat <<'USAGE'
Build plugins and pack each one into a single archive a harness can ingest.

Usage:
  tools/pack.sh [options] [plugin[,plugin...]]

Selection
  -a, --all                every plugin under plugins/ (skips _template)
  -t, --target <id>        harness to pack for, repeatable or comma-separated
                           (default: claude-code)
  -T, --all-targets        every target under targets/

Output
  -o, --out <dir>          where to write archives (default: dist/pack/<target>/)
      --dist-dir <dir>     where bundles are built (default: dist/)
      --clean              rebuild from scratch

Other
      --no-build           pack whatever is already built
      --skip-validate      do not validate sources before building
  -l, --list               show plugins and targets, then exit
  -n, --dry-run            print every command, execute none
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
      [ $# -ge 2 ] || die "--target needs a value"
      while IFS= read -r piece || [ -n "$piece" ]; do TARGETS+=("$piece"); done < <(split_commas "$2")
      shift ;;
    -o|--out)
      [ $# -ge 2 ] || die "--out needs a value"
      OUT=$2; shift ;;
    --dist-dir)
      [ $# -ge 2 ] || die "--dist-dir needs a value"
      DIST_DIR=$2; shift ;;
    --clean)           CLEAN=1 ;;
    --no-build)        DO_BUILD=0 ;;
    --skip-validate)   DO_VALIDATE=0 ;;
    -l|--list)         LIST_ONLY=1 ;;
    -n|--dry-run)      DRY_RUN=1 ;;
    -h|--help)         usage; exit 0 ;;
    -*)                die "unknown option: $1 (try --help)" ;;
    *)
      while IFS= read -r piece || [ -n "$piece" ]; do PLUGINS+=("$piece"); done < <(split_commas "$1") ;;
  esac
  shift
done

PY=$(pick_python) || exit $?

ALL_PLUGIN_NAMES=()
while IFS= read -r line; do ALL_PLUGIN_NAMES+=("$line"); done < <(available_plugins)
ALL_TARGET_NAMES=()
while IFS= read -r line; do ALL_TARGET_NAMES+=("$line"); done < <(available_targets)

[ ${#ALL_PLUGIN_NAMES[@]} -gt 0 ] || die "no plugins found under $ROOT/plugins"
[ ${#ALL_TARGET_NAMES[@]} -gt 0 ] || die "no targets found under $ROOT/targets"

if [ "$LIST_ONLY" = 1 ]; then
  say "${C_BOLD}Plugins${C_OFF} ($ROOT/plugins)"
  for name in "${ALL_PLUGIN_NAMES[@]}"; do say "  $name"; done
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

# Resolve --out against the directory the user ran this from, not the repo root,
# because everything below runs with cwd set to the repo root.
if [ -n "$OUT" ]; then
  case "$OUT" in
    /*|[A-Za-z]:[\\/]*) ;;
    ~*) OUT=${OUT/#\~/$HOME} ;;
    *)  OUT=$INVOKED_FROM/$OUT ;;
  esac
fi

# ---------------------------------------------------------------- the work --

FAILURES=0

run() {  # run <command...>
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s$%s %s\n' "$C_DIM" "$C_OFF" "$*"
    return 0
  fi
  "$@"
}

apkit() { run "$PY" -m tools.apkit --root "$ROOT" "$@"; }

cd "$ROOT" || die "cannot enter $ROOT"

plugin_args=()
for name in "${PLUGINS[@]}"; do plugin_args+=(--plugin "$name"); done
target_args=()
for name in "${TARGETS[@]}"; do target_args+=(--target "$name"); done

say "${C_BOLD}${SCRIPT_NAME}${C_OFF} ${#PLUGINS[@]} plugin(s) -> ${#TARGETS[@]} target(s)"
info "  plugins: ${PLUGINS[*]}"
info "  targets: ${TARGETS[*]}"
[ -n "$OUT" ] && info "  out:     $OUT"
[ "$DRY_RUN" = 1 ] && info "  dry run: nothing will be executed"
say ""

if [ "$DO_BUILD" = 1 ]; then
  if [ "$DO_VALIDATE" = 1 ]; then
    say "${C_BOLD}validate${C_OFF}"
    apkit validate "${plugin_args[@]}" --strict \
      || die "validation failed -- fix the source, or pass --skip-validate to pack anyway"
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
  info "skipping build (--no-build); packing whatever is in ${DIST_DIR:-dist/}"
  say ""
fi

say "${C_BOLD}pack${C_OFF}"
pack_args=("${plugin_args[@]}" "${target_args[@]}" --verbose)
[ -n "$DIST_DIR" ] && pack_args+=(--dist-dir "$DIST_DIR")
[ -n "$OUT" ] && pack_args+=(--out "$OUT")
apkit pack "${pack_args[@]}" || FAILURES=$((FAILURES + 1))
say ""

if [ "$DRY_RUN" = 1 ]; then
  info "dry run -- nothing was executed"
  exit 0
fi

if [ "$FAILURES" -gt 0 ]; then
  die "some archives were not written (see above)"
fi

destination=${OUT:-${DIST_DIR:-dist}/pack}
say "${C_GREEN}ready${C_OFF} archives are in ${destination}"
exit 0
