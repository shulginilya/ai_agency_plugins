# notes

Running notes on many topics, kept organized in plain Markdown. Capture a
TODO, something you're working on, or a thought as it happens. Regroup a
messy topic into In progress, TODO, Done, Dropped and Notes without losing a
line. See what's open across every topic.

Turn TODO and in-progress items into GitHub tickets assigned to you on your
default board, and inline markers too: `"text"(todo)`, `"text"(optional)`,
`"text"(wip)`, and `"text"(done)` or `"text"(+)`. The bullet lines under a
marker become the ticket's task list. Each note is marked with its ticket, so
nothing is filed twice.

It's a Captain plugin, for your own sessions. It isn't in the firstmate crew
(`crew_plugins`), and the crew brief doesn't route work to it.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `note-keeping` | Capture, organize (lossless, with a `.bak`), status, and the notes folder |
| Skill | `notes-to-tickets` | Export items and inline markers, show the list, file them assigned to you (done ones closed), link each note to its ticket |
| Skill (shared) | `ticket-management` | Creates and assigns the issues, places them on the board, closes the done ones. Source: `plugins/_shared/skills/` |
| Command | `/add` | Capture a TODO, an in-progress item or a dated note |
| Command | `/organize` | Regroup a topic, or all of them, into the standard sections |
| Command | `/status` | What's open per topic, inline markers included; `--set-root <path>` changes the notes folder |
| Command | `/to-tickets` | Turn open items and inline markers into tickets on a board, assigned to you |

No hooks, no agents, no MCP server. Everything runs when you ask.

## The notes folder

First match wins:

1. `--root <path>` on any command,
2. `$NOTES_DIR`,
3. the folder saved with `notes.py set-root <path>` (or `/notes:status --set-root <path>`),
   kept in `$XDG_CONFIG_HOME/ai-agency/notes.json`, by default `~/.config/ai-agency/notes.json`.

Windows paths such as `C:\Users\Ilya Shulgin\source\repos\tech_docs\notes`
work as given: under WSL they map to `/mnt/c/...`. Change the folder any time
by saving a new one.

## The format

One `.md` file per topic. Front matter can name the topic's `repo`, `board`
and `assignee`, so its tickets go to the right place. Items are `- [ ]` TODO,
`- [/]` in progress, `- [x]` done and `- [-]` dropped. Loose `TODO:` and `WIP:`
lines count too. Lines indented under an item belong to it. A filed item ends
with `→ #N`.

### Inline markers

A quoted phrase followed by a status in brackets is a task, anywhere in a
line, mid-sentence included. The quoted text becomes the ticket title.

| Marker | Ticket goes to |
| --- | --- |
| `"add an error filter"(todo)` | Backlog |
| `"maybe a dark mode"(optional)` | In Definition, with "Marked optional" in its body |
| `"wiring the board"(wip)` | In progress |
| `"shipped it"(done)` or `"shipped it"(+)` | Done, and the ticket is closed as completed |

Any case works, so `(TODO)`, `(OPTIONAL)`, `(WIP)` and `(DONE)` are the same.
Markers inside code fences are ignored. Unlike these markers, `- [x]` items
are never filed.

### Scope

The lines straight after a marked line that start with a bullet or a dash
(`-`, `–`, `—`, `•`, `·`, `*`) are its scope: the things to do within it.
They become the ticket's task list, keeping any `[x]`, and are never filed as
tickets of their own. A blank line, or any line that doesn't start with a
bullet or dash, ends the scope.

```markdown
We need "build the importer"(todo) soon
- parse the CSV
– map the columns
• [x] pick a library

This line is not part of it.
```

### A full sample

A note, `observatory.md`:

```markdown
# Observatory

Planning call today. We agreed to "add an error filter to the timeline"(todo)
- filter by status code
- filter by agent name
– keep the filter in the URL

Nice to have: "dark mode for the dashboard"(optional)
- follow the OS setting

I'm currently "wiring the Neon branch per PR"(WIP), and yesterday I "shipped the session list"(+).
This line has no bullet, so it is not part of anything.

"write the README"(TODO)
```

`/notes:to-tickets` turns it into five tickets, all assigned to you:

| Ticket | Column | Body extras |
| --- | --- | --- |
| add an error filter to the timeline | Backlog | Scope: filter by status code, filter by agent name, keep the filter in the URL |
| write the README | Backlog | none |
| dark mode for the dashboard | In Definition | "Marked optional", scope: follow the OS setting |
| wiring the Neon branch per PR | In progress | none |
| shipped the session list | Done, closed as completed | none |

The bullets aren't tickets of their own: each scope becomes its ticket's task
list. The blank line ends the first scope, so "Nice to have…" starts afresh.
The line without a bullet is ignored. Each ticket's body opens with where it
came from, then quotes the sentence. Here is the first one:

```markdown
From my notes: **Observatory** (`observatory.md`, line 3, TODO).

add an error filter to the timeline

> Planning call today. We agreed to add an error filter to the timeline

**Scope**

- [ ] filter by status code
- [ ] filter by agent name
- [ ] keep the filter in the URL
```

After filing, each marker carries its ticket, e.g.
`"write the README"(TODO) → shulginilya/ai-common-tasks#5`, and is never filed
again.

The full description is in `skills/note-keeping/references/format.md`.

## Where tickets go

For each topic, first match wins: its front matter, then the command line,
then the saved defaults. The defaults are kept in the same `notes.json` as the
notes folder, and `set-root` leaves them alone.

```bash
python skills/note-keeping/scripts/notes.py defaults --repo shulginilya/ai-common-tasks --board "AI common tasks" --assignee @me
python skills/note-keeping/scripts/notes.py defaults     # show them
```

`--board` takes a number or the board's exact name. The assignee defaults to
`@me`, meaning you. `--assignee none` files tickets unassigned.

## Guarantees

- **Nothing lost:** `organize` only regroups and refuses to write if a line
  would be lost or duplicated. `check before.md after.md` proves the same for
  any other edit.
- **Nothing filed twice:** filed items are marked `→ #N`, at the end of the
  line for an item and right after the marker for an inline one. Marked items
  are never exported again, and the batch skips titles that already exist.
  Scope lines are part of their marker's ticket, never tickets of their own.
- **Nothing filed unseen:** `file` refuses without `--yes`, which the skill
  passes only after you've seen the list. A topic with no repo in its front
  matter, on the command line or in the defaults is refused, never guessed.

## Try it

```bash
N=plugins/notes/skills/note-keeping/scripts/notes.py
python $N set-root "C:\Users\Ilya Shulgin\source\repos\tech_docs\notes"
python $N add --topic "Observatory" --todo "add a timeline filter for errors"
python $N status
python $N organize --file observatory.md            # preview; add --write to apply
python $N defaults --repo me/tasks --board "AI common tasks"
python $N export --out /tmp/plans                     # todo, wip and done, assigned to @me
python -m tools.apkit test --plugin notes
```

## What degrades where

- **Claude Code** takes everything.
- **Codex CLI, Cursor, Gemini CLI and OpenCode** take the skills and commands.
- **Generic `.agents/skills`** takes the skills only. Both skills carry their
  scripts.
- Filing uses the shared `ticket-management` skill, which the build copies into
  this plugin. It needs an authenticated `gh` with the `project` scope.
