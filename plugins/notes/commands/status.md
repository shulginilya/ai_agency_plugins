---
description: What is open across your notes — in progress, TODO and not yet ticketed, per topic. Also sets the notes folder.
argument_hint: "[topic, or --set-root <path> to change the notes folder]"
model: sonnet
allowed_tools: Bash(python:*) Read
---

Notes status: {{ARGS}}

If the arguments contain `--set-root <path>`, run
`python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py set-root "<path>"`, and report
the folder now in use. Windows paths like `C:\Users\me\notes` are fine.

Otherwise:

1. Run `python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py status` (add `--topic`
   when one is named). If no folder is set, ask for the path and save it with
   `set-root`.
2. Summarize one line per topic:
   - in progress, TODO and done;
   - open items without a ticket, inline markers included;
   - inline `(done)` markers not filed yet;
   - loose `TODO:` lines that `/notes:organize` would tidy.
3. List the in-progress items by name
   (`python {{PLUGIN_ROOT}}/skills/note-keeping/scripts/notes.py scan`), then offer
   `/notes:to-tickets` for anything open and unfiled.
