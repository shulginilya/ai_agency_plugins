---
description: Check whether every installed plugin is up to date with this plugins repo, report it as a table that marks the crew members, update the stale ones and install new ones.
argument_hint: "[--no-fetch]"
model: claude-sonnet-5-5
effort: low
allowed_tools: Bash(python:*) Bash(git:*) Bash(claude:*) Read
---

Check and update plugins: {{ARGS}}

Follow the `plugin-freshness` skill:

1. Run `python {{PLUGIN_ROOT}}/skills/plugin-freshness/scripts/check.py --update {{ARGS}}` from the
   plugins repo. Exit 2 means it could not run: say why, in its words, and stop.
2. Give the output as it printed it: the `Source:` line, the table (with its Crew column), the verdict, the crew line,
   the differing files and the notes, then what it updated, installed or failed to update
   and the report it printed after the update. Do not re-derive or round anything.
3. Then one line, only when something is off: `Not updating: <why>` means it
   changed nothing, so say what to fix (pull, switch to the default branch,
   commit or stash) and run the command again; a `Failed:` plugin needs its
   output read. After an update or install, `/reload-plugins` loads them.
   Never build, install or pull by hand: the script does it, from a safe source only.
