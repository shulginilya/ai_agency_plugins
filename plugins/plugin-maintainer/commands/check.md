---
description: Check whether every installed plugin is up to date with this plugins repo, and report it as a table.
argument_hint: "[--no-fetch] [--skills-dir <path>]"
model: claude-sonnet-5-5
effort: low
allowed_tools: Bash(python:*) Bash(git:*) Bash(claude:*) Read
---

Check plugins: {{ARGS}}

Follow the `plugin-freshness` skill:

1. Run `python {{PLUGIN_ROOT}}/skills/plugin-freshness/scripts/check.py {{ARGS}}` from the
   plugins repo. Exit 2 means it could not run: say why, in its words, and stop.
2. Give the report as it printed it: the `Source:` line, the table, the verdict,
   the differing files and the notes. Do not re-derive or round anything.
3. Then one line on what to do, only when something is off: pull when the source
   is behind origin; reinstall the stale plugins with
   `python -m tools.apkit build --plugin <name> --target claude-code` and
   `python -m tools.apkit install <name> --target claude-code`. Never run them
   yourself: this check is read-only.
