# notes

Running notes on many topics, kept organized in plain Markdown. Capture a
TODO, something you're working on, or a thought as it happens. Regroup a
messy topic into In progress, TODO, Done, Dropped and Notes without losing a
line. See what's open across every topic. Turn TODO and in-progress items
into GitHub tickets on the board you name, with each note marked by its
ticket so nothing is filed twice.

It's a Captain plugin, for your own sessions. It isn't in the firstmate crew
(`crew_plugins`), and the crew brief doesn't route work to it.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `note-keeping` | Capture, organize (lossless, with a `.bak`), status, and the notes folder |
| Skill | `notes-to-tickets` | Export open items, show the list, file them, link each note to its ticket |
| Skill (shared) | `ticket-management` | Creates the issues and places them on the board. Source: `plugins/_shared/skills/` |
| Command | `/add` | Capture a TODO, an in-progress item or a dated note |
| Command | `/organize` | Regroup a topic, or all of them, into the standard sections |
| Command | `/status` | What's open per topic; `--set-root <path>` changes the notes folder |
| Command | `/to-tickets` | Turn open items into tickets on a board |

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

One `.md` file per topic. Front matter can name the topic's `repo` and
`board`, so its tickets go to the right place. Items are `- [ ]` TODO,
`- [/]` in progress, `- [x]` done and `- [-]` dropped. Loose `TODO:` and `WIP:`
lines count too. Lines indented under an item belong to it. A filed item ends
with `→ #N`. The full description, with an example, is in
`skills/note-keeping/references/format.md`.

## Guarantees

- **Nothing lost:** `organize` only regroups and refuses to write if a line
  would be lost or duplicated. `check before.md after.md` proves the same for
  any other edit.
- **Nothing filed twice:** filed items are marked `→ #N` and never exported
  again, and the batch skips titles that already exist.
- **Nothing filed unseen:** `file` refuses without `--yes`, which the skill
  passes only after you've seen the list. A topic with no repo is refused,
  never guessed.

## Try it

```bash
N=plugins/notes/skills/note-keeping/scripts/notes.py
python $N set-root "C:\Users\Ilya Shulgin\source\repos\tech_docs\notes"
python $N add --topic "Observatory" --todo "add a timeline filter for errors"
python $N status
python $N organize --file observatory.md            # preview; add --write to apply
python $N export --topic Observatory --repo me/app --board 3 --out /tmp/plans
python -m tools.apkit test --plugin notes
```

## What degrades where

- **Claude Code** takes everything.
- **Codex CLI, Cursor, Gemini CLI and OpenCode** take the skills and commands.
- **Generic `.agents/skills`** takes the skills only. Both skills carry their
  scripts.
- Filing needs the shared `ticket-management` skill, which comes with #35's
  shared-skills build. It needs an authenticated `gh` with the `project` scope.
