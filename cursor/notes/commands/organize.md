---
description: Regroup a topic's notes into In progress, TODO, Done, Dropped and Notes, without losing a line.
---

Organize notes: $ARGUMENTS

Follow the `note-keeping` skill:

1. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py where`. If no folder is
   set, ask for the path and save it with `set-root`.
2. For each file (`status` lists them), preview
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py organize --file <file>` and tell
   the user what moves where.
3. After a yes, run the same command with `--write`. A `.bak` is kept.
4. For anything beyond a regroup (merging duplicates, splitting a topic,
   rewording), edit the file yourself, then run
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py check <file>.bak <file>` and
   confirm every lost or added line with the user.
