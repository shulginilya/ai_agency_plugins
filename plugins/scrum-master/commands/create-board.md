---
description: Create a GitHub Projects board for this repository with the team's columns, linked and ready for a backlog.
argument_hint: "[board title, and optionally the columns in order]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(python:*) Read Grep Glob
---

Create a board: {{ARGS}}

Follow the `board-setup` skill:

1. Check whether a board already exists with
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py boards`. If an open one
   already holds this repository's issues, say so and stop unless the user still
   wants a new one.
2. Settle the title and the columns. The default is In Definition, Backlog, Ready,
   In progress, In review, In approval, QA, Ready for Merge, Done. Show the plan with
   `python {{PLUGIN_ROOT}}/skills/board-setup/scripts/create_board.py --title "<title>" --dry-run`.
3. Wait for the user's yes. Under a crew brief, go ahead only if the brief asks
   for a board.
4. Create it with the same command without `--dry-run`, then report the board's
   number, URL, columns and linked repository in the skill's format.
