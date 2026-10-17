# The notes format

Plain Markdown that reads fine in any editor and needs no app. One file per
topic, anywhere under the notes folder. Subfolders are fine.

```markdown
---
repo: shulginilya/ai_agency_plugins    # optional: where this topic's tickets go
board: 1                               # optional: the GitHub Projects board number
topic: Firstmate crew                  # optional: defaults to the title, then the file name
---
# Firstmate crew

## In progress
- [/] wire designer into crew_plugins → #39

## TODO
- [ ] add designer to the diagram
  - needs a team.json lane
  - and the RACI column

### Deploy
- [ ] check deploy refuses under a live crew

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
- A filed item ends with `→ #N` when the front matter names the repo, or
  `→ owner/repo#N` when it doesn't. `->` works too. A linked item is never
  filed again.

## Inline markers

Mark a task anywhere in a line, mid-sentence included, by quoting it and
adding its status in brackets:

```markdown
Talked to the team: we should "add an error filter"(todo), and I'm already
"wiring the board"(wip). Yesterday I "shipped the notes plugin"(+).
```

| Marker | Status | Ticket goes to |
| --- | --- | --- |
| `"text"(todo)` or `(TODO)` | TODO | Backlog |
| `"text"(wip)` or `(WIP)` | In progress | In progress |
| `"text"(done)`, `(DONE)` or `(+)` | Done | Done, and the ticket is closed as completed |

- The quoted text becomes the ticket title. Straight `"…"` and curly
  `“…”` quotes both work, and so does any case of the status.
- When filed, the marker gets its ticket right after it:
  `"add an error filter"(todo) → #12`. A marker with a ticket is never filed
  again.
- A checkbox item whose text holds a marker is filed once, as the marker.
- Markers inside a code fence (```` ``` ````) are ignored.
- Unlike inline `(done)` markers, `- [x]` items are never filed. They are
  history, not tasks.

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
