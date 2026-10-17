---
description: Turn TODO, in-progress and done items from your notes — checkboxes and inline "text"(todo|wip|done) markers — into tickets assigned to you, and mark each note with its ticket.
argument_hint: "[topic, board number or repo; nothing for every topic]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(python:*) Bash(gh:*) Read Edit
---

Notes to tickets: {{ARGS}}

Follow the `notes-to-tickets` skill:

1. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py defaults` for the saved repo,
   board and assignee. Front matter and anything the user named here come
   first. Ask for any topic that still has no repo, and never guess. When no
   board is set, offer the ones
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py boards` lists for that repo.
2. Export to a scratch folder:
   `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py export --out <dir> [--topic T] [--repo R] [--board N] [--assignee A]`.
   Show the list per repo, board and column, with the assignee:
   - TODO and `(todo)` go to Backlog;
   - in progress and `(wip)` go to In progress;
   - `(done)` and `(+)` go to Done and are closed.

   Wait for a yes.
3. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py file --plans <dir> --yes`.
4. Report every ticket filed, with its link, column, assignee and the note it
   came from, plus anything closed, skipped or not linked.
