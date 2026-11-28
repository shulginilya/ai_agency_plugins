---
description: Turn TODO, in-progress and done items from your notes — checkboxes and inline "text"(todo|optional|wip|done) markers, with "text"(outcome) as acceptance criteria — into tickets assigned to you, then replace each filed item in the note with a link to its ticket.
model: claude-opus-5-5
---

Notes to tickets: $ARGUMENTS

Follow the `notes-to-tickets` skill:

0. If the arguments name a notes file (a path, or a file name such as
   `meeting.md`; Windows paths are fine), work on that one file: pass
   `--file "<path>"` to `export` below. It may be outside the notes folder.

1. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py defaults` for the saved repo,
   board and assignee. Front matter and anything the user named here come
   first. Ask for any topic that still has no repo, and never guess. When no
   board is set, offer the ones
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/ticket-management/scripts/board.py boards` lists for that repo.
2. Export to a scratch folder:
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py export --out <dir> [--file F | --topic T] [--repo R] [--board N|"Board name"] [--assignee A]`.
   An item's own board marker, `"text"(todo)(Board)`, wins over front matter,
   `--board` and the default. If `export` names an unknown board, show the
   boards it lists and ask; never guess.
   Show the list per repo, board and column, with the assignee:
   - TODO and `(todo)` go to Backlog;
   - `(optional)` goes to In Definition;
   - in progress and `(wip)` go to In progress;
   - `(done)` and `(+)` go to Done and are closed;
   - `(outcome)` is no ticket: it is an acceptance criterion of its item,
     counted next to it, e.g. `(2 scope items, 1 outcome)`.

   Show every line of `outcome_warnings`: those outcomes reach no ticket.

   For every item under `needs_short_title`, write a short title (80
   characters or fewer) that keeps the point, and set it with
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py retitle --plans <dir> --key <key> --title "<short>"`.
   Show the short title with the full text under it. The full text stays in
   the ticket's description and checklist. Never file a title ending in "…".

   Say that each filed item will then be replaced in the note by a link to its
   ticket, with a `.bak` kept, unless `defaults` shows `after_filing: link`. If the user wants
   to keep them this time, add `--keep`, so they stay marked `→ #N`.
   Wait for a yes.
3. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/notes/skills/note-keeping/scripts/notes.py file --plans <dir> --yes`.
4. Report every ticket filed, with its link, column, assignee and the note it
   came from, what was replaced by a link in the note, and anything closed, skipped
   or not found.
