# shellcheck shell=bash
#
# Shared helpers for the wrapper scripts in this directory. Sourced, never run.
#
# A caller must set ROOT (the repo root) before sourcing, and gets: colour
# variables, say/info/warn/die, pick_python, the plugin and target listings,
# contains and split_commas.

# ------------------------------------------------------------------ output --

if [ -t 1 ]; then
  C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'; C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_OFF=$'\033[0m'
else
  C_BOLD=""; C_DIM=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_OFF=""
fi

say()  { printf '%s\n' "$*"; }
info() { printf '%s%s%s\n' "$C_DIM" "$*" "$C_OFF"; }
warn() { printf '%swarn%s  %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die()  { printf '%serror%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 2; }

# ------------------------------------------------------------ interpreter --

# A name on PATH is not proof of an interpreter. On Windows, `python3` and
# `python` are usually App Execution Alias stubs that `command -v` finds but
# that print "Python was not found" and exit nonzero; elsewhere `python` may
# still be Python 2. So probe by running the candidate, and require the 3.9+
# that tools/apkit targets -- otherwise the failure surfaces much later as an
# unexplained "validation failed".
python_ok() {  # python_ok <command>
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
    >/dev/null 2>&1
}

# Callers use `PY=$(pick_python) || exit $?`: die inside $(...) only exits the
# subshell, so without that the script would continue with PY empty.
pick_python() {
  local candidate
  if [ -n "${PYTHON:-}" ]; then
    python_ok "$PYTHON" || die "PYTHON=$PYTHON is not a working Python 3.9+ interpreter"
    printf '%s' "$PYTHON"
    return
  fi
  for candidate in python3 python py; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if python_ok "$candidate"; then printf '%s' "$candidate"; return; fi
    # stdout is captured by PY=$(pick_python), so this note goes to stderr.
    info "skipping $candidate: not a working Python 3.9+ interpreter" >&2
  done
  die "no working Python 3.9+ on PATH (tried python3, python, py); set PYTHON=/path/to/python"
}

# --------------------------------------------------------------- discovery --

# Only directories that actually carry a plugin.json. This is deliberate: a
# stray __pycache__ or a half-deleted directory under plugins/ is invisible to
# git but makes an unscoped apkit run fail with "missing plugin.json".
available_plugins() {
  local dir name
  for dir in "$ROOT"/plugins/*/; do
    [ -f "$dir/plugin.json" ] || continue
    name=$(basename "$dir")
    [ "$name" = "_template" ] && continue
    printf '%s\n' "$name"
  done
}

available_targets() {
  local file
  for file in "$ROOT"/targets/*.json; do
    [ -f "$file" ] || continue
    basename "$file" .json
  done
}

contains() {  # contains <needle> <haystack...>
  local needle=$1; shift
  local item
  for item in "$@"; do [ "$item" = "$needle" ] && return 0; done
  return 1
}

# split_commas a,b,c -> one per line. The trailing newline matters: `read`
# returns non-zero on a final line without one, and the last item is dropped.
split_commas() {
  printf '%s\n' "$1" | tr ',' '\n' | while IFS= read -r piece || [ -n "$piece" ]; do
    piece=$(printf '%s' "$piece" | tr -d '[:space:]')
    [ -n "$piece" ] && printf '%s\n' "$piece"
  done
  return 0
}

# Portable stand-in for `mapfile`, which bash 3.2 (still shipped by macOS) lacks.
# read_lines <array-name> < <(producer)
read_lines() {
  local name=$1 line
  eval "$name=()"
  while IFS= read -r line; do eval "$name+=(\"\$line\")"; done
}
