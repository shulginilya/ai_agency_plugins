---
name: note-keeping
description: Keeps a folder of running notes, one Markdown file per topic, organized — captures a TODO, an in-progress item or a dated note into the right topic, regroups a messy topic into In progress, TODO, Done, Dropped and Notes without losing a line, and reports what is open across every topic. Use when asked to note or jot something down, add a TODO, organize, tidy or restructure notes, see open or in-progress items, or change where the notes folder is.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Note keeping

The notes are the user's own words. Organizing them may move a line. It must
never lose one, reword one, or invent one. The script enforces that, so let
it do the moving.

```bash
python scripts/notes.py where                                 # which folder, and why
python scripts/notes.py set-root "C:\Users\me\notes"          # remember a folder (Windows paths are fine)
python scripts/notes.py add --topic "Firstmate crew" --todo "add designer to the diagram"
python scripts/notes.py add --topic "Observatory" --note "Neon branch per PR looks cheap"
python scripts/notes.py status                                # open items per topic
python scripts/notes.py status --file "C:\Users\me\meeting.md"  # one notes file, anywhere
python scripts/notes.py scan --topic "Observatory"            # every item with file:line
python scripts/notes.py organize --file observatory.md        # preview the regroup
python scripts/notes.py organize --file observatory.md --write
python scripts/notes.py check before.md after.md              # prove an edit lost nothing
```

The format is in [references/format.md](references/format.md): sections, item
markers, front matter, and how a filed item is marked.

## The notes folder

First match wins: `--root`, then `$NOTES_DIR`, then the folder saved with
`set-root`. Run `where` when in doubt. If no folder is set, ask the user for
the path and save it with `set-root`. Never guess one.

## Capture

When the user says "note that…", "TODO…" or "I'm working on…", run `add` with
the topic they name. If they don't name one, pick the closest existing topic
from `status` and say which you picked.

- `--todo` and `--wip` add an item to the topic's TODO or In progress section.
- `--note` appends to today's `### YYYY-MM-DD` entry under Notes.
- A new topic gets its own file.
- Inline markers need no command. A quoted phrase followed by `(todo)`,
  `(optional)`, `(wip)` or `(done)`/`(+)`, anywhere in a note, is a task of that status (see
  the format reference). `status` counts the markers, and `notes-to-tickets`
  files them. `"text"(outcome)` is not a task: it is an acceptance criterion
  of the item it sits with, and goes into that item's ticket. A second bracket,
  `"text"(todo)(Board name)`, sends the item to that board.

Keep the user's wording. Fix only obvious typos, and only if they ask.

## Organize

1. Preview with `organize --file F`. Tell the user what moves: how many items
   go to each section, which loose `TODO:` lines become task items, and which
   of their own sections become groups.
2. Write with `--write` once they agree. Mention the `.bak`.
3. The script only regroups. When the user wants more, such as merging
   duplicates, splitting a topic into two files, or rewording, make that edit
   yourself. Then run `check <file>.bak <file>`. If it reports lost or added
   lines, list them to the user and keep each change only if they confirm it.
   Nothing is dropped silently.

## Report

For `status`, give a topic-per-line summary: in progress, TODO, done, and
"open unfiled", meaning open items without a ticket yet. When open unfiled
items exist, offer the `notes-to-tickets` skill.
