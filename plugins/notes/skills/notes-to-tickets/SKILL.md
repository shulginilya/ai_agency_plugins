---
name: notes-to-tickets
description: Turns items in running notes — TODO and in-progress items, and inline "text"(todo), "text"(optional), "text"(wip) and "text"(done) markers, from every topic or one — into GitHub issues assigned to the user on the saved default board, TODO into Backlog, optional into In Definition, in-progress into In progress, done into Done and closed, then marks each item with its ticket number so it is never filed twice. Use when asked to turn notes, TODOs or work in progress into tickets or issues, push notes to a board, or file what is open in the notes.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Notes to tickets

Each item becomes a ticket only once, in the right repo, after the user has
seen the list. The scripts guarantee the "only once". The list is your job.

```bash
python ../note-keeping/scripts/notes.py defaults                # where tickets go by default, and to whom
python ../note-keeping/scripts/notes.py defaults --repo owner/name --board "AI common tasks" --assignee @me
python ../note-keeping/scripts/notes.py export [--topic T | --file F] [--status todo,wip,done] \
    [--repo owner/name] [--board N] [--assignee @me|LOGIN|none] --out PLANS_DIR
python ../note-keeping/scripts/notes.py file --plans PLANS_DIR --yes
python ../ticket-management/scripts/board.py boards     # pick a board when none is named
```

## What gets filed

- Open checkbox items: `- [ ]` and loose `TODO:` lines go to Backlog;
  `- [/]` and `WIP:` lines go to In progress.
- Inline markers anywhere in the text (see the format reference):
  - `"text"(todo)` goes to Backlog;
  - `"text"(optional)` goes to In Definition, and its body says it was marked
    optional;
  - `"text"(wip)` goes to In progress;
  - `"text"(done)` or `"text"(+)` goes to Done, and `file` closes the ticket as
    completed.
- The quoted text is the title. Done `- [x]` items are never filed.
- A marker's scope is the bullet or dash lines straight after it, up to a
  blank line or any other line. It becomes the ticket's task list and is never
  filed as separate tickets. `export` lists such a ticket with its scope count,
  e.g. `build the importer (3 scope items)`. Show it that way.
- Every ticket is assigned to the saved assignee, `@me` unless changed.
  `--assignee none` files them unassigned.

## 0. Which notes

By default, every topic in the notes folder is read. `--topic T` narrows that
to one topic. `--file F` reads just one notes file instead, anywhere on disk,
inside the notes folder or not. Use it when the user names a file. A bare
name like `meeting.md` is looked up in the notes folder, and Windows paths
are fine. The export records which folder it read, so `file` links the
tickets back into that same file.

## 1. Decide where the tickets go

- First match wins:
  1. the topic's front matter (`repo:`, `board:`, `assignee:`);
  2. the command-line `--repo`, `--board` and `--assignee`;
  3. the saved defaults.

  Run `defaults` to see the saved ones. To change them, pass `--repo`,
  `--board` (a number, or the board's exact name) and `--assignee`.
- If a topic still has no repo, ask the user which repository it belongs to. Offer
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
shulginilya/ai-common-tasks · AI common tasks (#5) · assigned to @me
  In progress:    wiring the board
  In Definition:  maybe a dark mode
  Backlog:        add an error filter
                  build the importer (3 scope items)
  Done:           shipped the notes plugin        (closed after filing)
```

Each ticket's body says where it came from (topic, file and line) and
carries the item's indented details. If a title reads badly out of context,
offer a better one. To use it, change the note itself, then export again, so
the note and the ticket keep the same wording. Stop here until the user says
yes.

## 3. File and link back

Run `file --plans PLANS_DIR --yes`. For each plan it calls the shared
`ticket-management` batch with `GH_REPO` set to that plan's repo, puts every
ticket in its column, assigns it, and appends `→ #N` (or `→ owner/repo#N`) to
the item in the note, right after the marker for an inline one. Tickets
created into Done are then closed as completed.

- A rerun is safe. Batch skips titles that already exist, and linked items
  are not exported again.
- If an item moved or was reworded between export and file, its link can't
  be written. The output says which one. Add the `→ #N` by hand.

## Reporting

```
Filed:   #N <title> — <repo>, <board> <column>, assigned <who>[, closed]   (from <file>:<line>)
Skipped: <title> — already existed as #N
Not linked: <item> — add "→ #N" by hand
```
