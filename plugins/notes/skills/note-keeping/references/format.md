# The notes format

Plain Markdown that reads fine in any editor and needs no app. One file per
topic, anywhere under the notes folder. Subfolders are fine.

```markdown
---
repo: shulginilya/ai_agency_plugins    # optional: where this topic's tickets go
board: 1                               # optional: the GitHub Projects board number
topic: Crew diagrams                  # optional: defaults to the title, then the file name
---
# Crew diagrams

## In progress
- [/] wire designer into the team.json crew → #39

## TODO
- [ ] add designer to the diagram
  - needs a team.json lane
  - and the RACI column

### Install
- [ ] check apkit install keeps a hand-edited config

## Done
- [x] crew-only deploy → #26

## Dropped
- [-] separate crew config dir

## Notes
### 2026-10-14
Talked about the crew today. Deploy must not run under a live crew.
```

## Items

| Marker | Status | Also recognized |
| --- | --- | --- |
| `- [ ]` | TODO | a loose `TODO:` or `FIXME:` line |
| `- [/]` | In progress | `- [~]`, a loose `WIP:` or `DOING:` line |
| `- [x]` | Done | `- [X]` |
| `- [-]` | Dropped | |

- Lines indented under an item belong to it: details, sub-bullets, links.
  They move with it and go into its ticket's body.
- By default, once its ticket exists, a filed item is replaced in the note by
  a link to it, `→ [#N title](https://github.com/owner/repo/issues/N)` (see `notes-to-tickets`). A link line is
  never filed and never counts as a scope line. With `after_filing: link`, or for an item whose
  line still holds an unfiled marker, it stays and ends with `→ #N` when the
  front matter names the repo, or `→ owner/repo#N` when it doesn't. `->`
  works too. A linked item is never filed again.

## Inline markers

Mark a task anywhere in a line, mid-sentence included, by quoting it and
adding its status in brackets:

```markdown
Talked to the team: we should "add an error filter"(todo), "maybe a dark mode"(optional), and I'm already
"wiring the board"(wip). Yesterday I "shipped the notes plugin"(+).
```

| Marker | Status | Ticket goes to |
| --- | --- | --- |
| `"text"(todo)` or `(TODO)` | TODO | Backlog |
| `"text"(optional)` or `(OPTIONAL)` | TODO, marked optional | In Definition, with "Marked optional" in its body |
| `"text"(wip)` or `(WIP)` | In progress | In progress |
| `"text"(done)`, `(DONE)` or `(+)` | Done | Done, and the ticket is closed as completed |

- The quoted text becomes the ticket title. When it is longer than 80
  characters, a short title is written for it before filing, and the full
  text goes in the ticket's description and checklist. Straight `"…"` and curly
  `“…”` quotes both work, and so does any case of the status.
- When filed, the marker's whole line and its scope are replaced by a link to
  the ticket, `→ [#12 add an error filter](https://github.com/owner/repo/issues/12)`,
  because the ticket now holds them. A line with two filed markers becomes
  two links. The exception is a line that still holds an unfiled marker:
  there, and in link mode, the marker gets its ticket right after it,
  `"add an error filter"(todo) → #12`. A marker with a
  ticket is never filed again.
- **Board.** A second bracket straight after the status, with no space, names
  the board for that item: `"add an error filter"(todo)(AI common tasks)` or
  `(5)`. A name matches the board's title exactly, in any case. It wins over
  the front matter's `board:`, `--board` and the saved default, and changes
  only the board, never the repo. `"text"(todo) (an aside)`, with a space, is
  not a board. It works on todo, optional, wip and done markers; on an outcome
  it changes nothing, and `export` warns. When filed in link mode, the ticket
  goes after it: `"add an error filter"(todo)(AI common tasks) → #12`.
- A checkbox item whose text holds a marker is filed once, as the marker.
- Markers inside a code fence (```` ``` ````) are ignored.
- **Scope.** The lines straight after a marked line that start with a bullet
  or a dash belong to it, as the things to do within it. Bullets are `-`,
  `–`, `—`, `•`, `·` and `*`, and a `[ ]` or `[x]` box after the bullet is
  kept. A blank line ends the scope, and so does any line that doesn't start
  with a bullet or a dash. A scope line holding its own marker starts a new
  item instead.

  ```markdown
  We need "build the importer"(todo):
  - parse the CSV
  – map the columns
  • [x] pick a library

  This line is not part of it.
  ```

  The scope becomes the checklist in the ticket body. An item with no scope
  gets a one-line checklist: its own text. Its lines, checkboxes
  included, are never filed as tickets of their own. When a line holds two
  markers, the scope belongs to the last one. `organize` keeps a scope under
  its marker.
- Unlike inline `(done)` markers, `- [x]` items are never filed. They are
  history, not tasks.

## Outcomes

`"text"(outcome)`, in any case, is an acceptance criterion: how you will know
the item is done. It works anywhere a marker does, but it never becomes a
ticket of its own. It belongs to the marker on its own line (the last one
before it), else to the item whose scope or details hold it, else to the
closest item above it before a blank line or a heading (a checkbox or
`TODO:` item too).

```markdown
"build the importer"(todo)
- parse the CSV
- "a 10k-row file imports in under 5 seconds"(outcome)

"add an error filter"(todo) "only errors are shown"(outcome)

- [ ] add dark mode
Done when "contrast passes AA"(outcome)
```

- The ticket gets an **Acceptance criteria** checklist, one box per outcome,
  after its checklist. Outcome lines are left out of the checklist and the
  details, so nothing appears twice. A line holding only outcomes is never an
  item or a task.
- `export` counts them, `build the importer (1 scope item, 1 outcome)`, and
  lists under `outcome_warnings` every outcome no ticket will get: one that
  belongs to no item, and one under an item that is already filed (add that
  one to the ticket by hand). Neither is filed or dropped.
- After filing, outcome lines go with their item: removed with it, or in link
  mode marked `→ #N` like it. Lines holding outcomes straight after an item
  move with it when `organize` regroups the note.

## Sections

- The standard sections, in this order: `## In progress`, `## TODO`,
  `## Done`, `## Dropped`, `## Notes`. These are recognized whatever their
  case. "Doing", "WIP", "Next" and "Completed" are read as their standard
  equivalents.
- A `### Heading` inside a status section groups items, for example
  `### Deploy` under `## TODO`.
- Any other `## Heading` is your own section. On organize, its prose stays
  under it, and its items move into the status sections under a
  `### <your heading>` group, so you can still see where they came from.
- Free text belongs in `## Notes`, under a `### YYYY-MM-DD` heading per day.
  That's where `add --note` writes.

## Guarantees

- `organize` only regroups. It never rewords, drops or duplicates a line,
  and it refuses to write if it would. `check BEFORE AFTER` proves the same
  after any edit, including one made by hand or by Claude.
- `organize --write` keeps the previous version as `<file>.bak`.
