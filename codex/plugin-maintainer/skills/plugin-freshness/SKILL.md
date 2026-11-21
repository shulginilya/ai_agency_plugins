---
name: plugin-freshness
description: Checks whether every installed plugin is up to date with the plugins repo — the installed version equals the source version, the installed files are identical to a fresh build, and the local default branch matches origin — and reports it as a Markdown table with the differing files and notes on source plugins that are not installed and older same-named copies from other sources. Read-only by default; with --update it also builds and installs the stale ones, and the source plugins not installed yet, from a safe source. Use when asked whether the plugins are up to date, which plugins are stale, to update or reinstall them, to install new plugins, whether an install matches the repo, or to check every plugin before a session.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.3.0
---

# Plugin freshness

One script answers "is every installed plugin up to date?" and prints the
report. Run it; do not reconstruct the comparison by hand.

```bash
python scripts/check.py                 # from the plugins repo
python scripts/check.py --no-fetch      # offline: compare with origin as last fetched
python scripts/check.py --skills-dir <path>   # another install location (report only)
python scripts/check.py --update        # report, update the stale plugins, install new ones, report again
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

## Updating

`--update` (the `/plugin-maintainer:check` command always passes it) acts only
when something is stale, a source plugin is not installed yet, or the default
branch is behind origin, and only from a safe source. It stops with `Not updating: <why>` and changes nothing when:

- the checkout is on a branch other than the default branch;
- there are uncommitted changes under `plugins/`;
- the default branch is ahead of origin, or origin cannot be compared with;
- the skills dir is not the default `~/.claude/skills`, where `apkit install`
  writes;
- `git pull --ff-only` fails (a merge is never made).

Otherwise it fast-forwards a default branch that is behind, rebuilds, then for
each stale plugin, and each plugin in the source that is not installed yet, runs `python -m tools.apkit build --plugin <name> --target
claude-code` and `python -m tools.apkit install <name> --target claude-code`.
A plugin that fails is listed with the step's output under `Failed:` and the
rest still update. It prints `Updated: ...` for the stale ones and `Installed: ...` for the new
ones, then the report again under
`After the update:` as the proof, and exits 0 only when that report is clean.
The new versions and plugins load with `/reload-plugins`. Copies from other
sources (`@synced`) are never installed or touched, and a plugin removed from
the source is never uninstalled.

## Rules

- **Read-only unless `--update`.** Without it the script fetches `origin` and
  builds into a temporary directory, and never pulls, installs, uninstalls,
  commits or touches `dist/`. Updating is the command's job: run the script
  with `--update`, never the pull, build or install by hand.
- **Report what it printed.** Do not soften a stale row, a `Not updating:` or
  a `Failed:`, and do not drop a note.
- Outside the plugins repo it stops with exit 2 and no table; say so.
