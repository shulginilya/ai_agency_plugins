---
description: What is open across your notes — in progress, TODO and not yet ticketed, per topic. Also sets the notes folder.
model: sonnet
---

Notes status: $ARGUMENTS

If the arguments contain `--set-root <path>`, run
`python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py set-root "<path>"`, and report
the folder now in use. Windows paths like `C:\Users\me\notes` are fine.

Otherwise:

1. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py status`. Add `--topic`
   when one is named, or `--file "<path>"` when a notes file is named. The file
   may be anywhere, outside the notes folder too. If no folder is set, ask for the path and save it with
   `set-root`.
2. Summarize one line per topic:
   - in progress, TODO and done;
   - open items without a ticket, inline markers included;
   - inline `(done)` markers not filed yet;
   - loose `TODO:` lines that `/notes:organize` would tidy.
3. List the in-progress items by name
   (`python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py scan`), then offer
   `/notes:to-tickets` for anything open and unfiled.
