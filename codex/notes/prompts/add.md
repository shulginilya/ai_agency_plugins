# /add

Capture a TODO, an in-progress item or a dated note into one of your topic notes.

Capture: $ARGUMENTS

Follow the `note-keeping` skill:

1. Work out the topic and the kind: `--todo`, `--wip` ("working on…", "started…")
   or `--note` (anything else). If the topic isn't named, run
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py status` and pick the closest
   existing topic. Say which you picked.
2. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py add --topic "<topic>" --<kind> "<text>"`
   with the user's own wording.
3. Reply in one line: what was added, and to which file and section.
