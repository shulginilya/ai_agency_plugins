---
name: notes-to-tickets
description: Turns open items in running notes — TODO and in-progress, from every topic or one — into GitHub issues on the board the user names, TODO into Backlog and in-progress into In progress, then marks each item with its ticket number so it is never filed twice. Use when asked to turn notes, TODOs or work in progress into tickets or issues, push notes to a board, or file what is open in the notes.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Notes to tickets

Each item becomes a ticket only once, in the right repo, after the user has
seen the list. The scripts guarantee the "only once". The list is your job.

```bash
python ../note-keeping/scripts/notes.py export [--topic T] [--status todo,wip] \
    [--repo owner/name] [--board N] [--todo-column Backlog] [--wip-column "In progress"] --out PLANS_DIR
python ../note-keeping/scripts/notes.py file --plans PLANS_DIR --yes
python ../ticket-management/scripts/board.py boards     # pick a board when none is named
```

## 1. Decide where the tickets go

- Each topic file's front matter can name its `repo` and `board`. The
  command-line `--repo` and `--board` fill in for topics that name neither.
- If a topic has no repo, ask the user which repository it belongs to. Offer
  to add `repo:` and `board:` to its front matter so the question doesn't
  come back. Never guess a repo.
- To find the board number, run `board.py boards` from inside that repo, or
  with `GH_REPO=owner/name` set. When none is named, offer the boards it
  lists, most used first. Without a board, tickets are created but not
  placed on any board.

## 2. Export and show the list

Run `export` into a scratch folder. It writes one plan per repo, board and
status, and prints every title. Only open items without a ticket are
included; done, dropped and already-linked items are skipped. Show the user:

```
shulginilya/ai_agency_plugins · board 1
  In progress:  wire designer into crew_plugins
  Backlog:      add designer to the diagram
                ship the notes plugin
```

Each ticket's body says where it came from (topic, file and line) and
carries the item's indented details. If a title reads badly out of context,
offer a better one. To use it, change the note itself, then export again, so
the note and the ticket keep the same wording. Stop here until the user says
yes.

## 3. File and link back

Run `file --plans PLANS_DIR --yes`. For each plan it calls the shared
`ticket-management` batch with `GH_REPO` set to that plan's repo, puts every
ticket in its column, and appends `→ #N` (or `→ owner/repo#N`) to the item in
the note.

- A rerun is safe. Batch skips titles that already exist, and linked items
  are not exported again.
- If an item moved or was reworded between export and file, its link can't
  be written. The output says which one. Add the `→ #N` by hand.

## Reporting

```
Filed:   #N <title> — <repo>, <board> <column>   (from <file>:<line>)
Skipped: <title> — already existed as #N
Not linked: <item> — add "→ #N" by hand
```
