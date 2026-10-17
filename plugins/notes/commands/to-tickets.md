---
description: Turn TODO, in-progress and done items from your notes — checkboxes and inline "text"(todo|optional|wip|done) markers — into tickets assigned to you, then remove the filed items from the note.
argument_hint: "[a notes file path, a topic, a board number or a repo; nothing for every topic]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(python:*) Bash(gh:*) Read Edit
---

Notes to tickets: {{ARGS}}

Follow the `notes-to-tickets` skill:

0. If the arguments name a notes file (a path, or a file name such as
   `meeting.md`; Windows paths are fine), work on that one file: pass
   `--file "<path>"` to `export` below. It may be outside the notes folder.

1. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py defaults` for the saved repo,
   board and assignee. Front matter and anything the user named here come
   first. Ask for any topic that still has no repo, and never guess. When no
   board is set, offer the ones
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py boards` lists for that repo.
2. Export to a scratch folder:
   `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py export --out <dir> [--file F | --topic T] [--repo R] [--board N] [--assignee A]`.
   Show the list per repo, board and column, with the assignee:
   - TODO and `(todo)` go to Backlog;
   - `(optional)` goes to In Definition;
   - in progress and `(wip)` go to In progress;
   - `(done)` and `(+)` go to Done and are closed.

   Say that the filed items will then be removed from the note, with a
   `.bak` kept, unless `defaults` shows `after_filing: link`. If the user wants
   to keep them this time, add `--keep`, so they stay marked `→ #N`.
   Wait for a yes.
3. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py file --plans <dir> --yes`.
4. Report every ticket filed, with its link, column, assignee and the note it
   came from, what was removed from the note, and anything closed, skipped
   or not found.
