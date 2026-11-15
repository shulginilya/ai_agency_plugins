---
name: plugin-freshness
description: Checks whether every installed plugin is up to date with the plugins repo — the installed version equals the source version, the installed files are identical to a fresh build, and the local default branch matches origin — and reports it as a Markdown table with the differing files and notes on source plugins that are not installed and older same-named copies from other sources. Read-only. Use when asked whether the plugins are up to date, which plugins are stale, whether an install matches the repo, or to check every plugin before a session.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Plugin freshness

One script answers "is every installed plugin up to date?" and prints the
report. Run it; do not reconstruct the comparison by hand.

```bash
python scripts/check.py                 # from the plugins repo
python scripts/check.py --no-fetch      # offline: compare with origin as last fetched
python scripts/check.py --skills-dir <path>   # another install location
```

## What "up to date" means

A plugin is **up to date** when both hold:

1. its installed version (`<skills-dir>/<name>/.claude-plugin/plugin.json`)
   equals the source version (`plugins/<name>/plugin.json`);
2. its installed files are identical to a fresh build of the source for
   Claude Code. `__pycache__` and `*.pyc` are ignored.

The verdict is only as fresh as the checkout, so the report starts with a
`Source:` line: the branch and commit built, and how far the default branch is
behind or ahead of `origin`. A checkout on another branch, behind, ahead, or
with uncommitted changes under `plugins/` is called out there, and the exit
code is 1 even when every row says up to date.

## Reading the report

- **Table:** one row per installed plugin from this repo: plugin, installed
  version, source version, files (`identical` / `differs`), status
  (`up to date` / `stale`). Then `All N up to date.` or `K of N stale: …`.
- **Differing files:** for each stale plugin, up to 8 paths that differ, exist
  only in the build, or exist only in the install.
- **Notes:** source plugins that are not installed, and same-named plugins
  from other sources in `claude plugin list` (for example synced from
  claude.ai) whose version differs from the source. These never become rows.

Exit codes: `0` all up to date and in sync, `1` something stale or out of
sync, `2` the check could not run (not the plugins repo, or the build failed).

## Rules

- **Read-only.** It fetches `origin` and builds into a temporary directory.
  It never pulls, installs, uninstalls, commits or touches `dist/`. Fixing a
  stale plugin is the user's call: name the commands, do not run them.
- **Report what it printed.** Do not soften a stale row or drop a note.
- Outside the plugins repo it stops with exit 2 and no table; say so.
