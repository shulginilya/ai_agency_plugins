---
description: Say whether the memory database answers and how many memories the current project has.
model: haiku
allowed_tools: Bash(python:*)
---

Memory status {{ARGS}}

Run `python "{{PLUGIN_ROOT}}/skills/memory-keeping/scripts/memory.py" status` and report its
lines. When it says memory is unavailable, report the reason; `/memory:setup`
repairs a stopped or missing database. Never print the connection string.
