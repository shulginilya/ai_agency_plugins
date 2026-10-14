---
description: Turn open TODO and in-progress items from your notes into GitHub tickets on a board, and mark each note with its ticket.
argument_hint: "[topic, board number or repo; nothing for every topic]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(python:*) Bash(gh:*) Read Edit
---

Notes to tickets: {{ARGS}}

Follow the `notes-to-tickets` skill:

1. Work out each topic's repo and board from its front matter, or from what
   the user named here. Ask for any topic that has no repo, and never guess.
   For a board, offer the ones
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py boards` lists for that repo.
2. Export to a scratch folder:
   `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py export --out <dir> [--topic T] [--repo R] [--board N]`.
   Show the list per repo, board and column (TODO → Backlog, in progress →
   In progress), and wait for a yes.
3. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py file --plans <dir> --yes`.
4. Report every ticket filed, with its link and the note it came from, plus
   anything skipped or not linked.
