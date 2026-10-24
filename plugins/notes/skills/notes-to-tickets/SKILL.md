---
name: notes-to-tickets
description: Turns items in running notes — TODO and in-progress items, and inline "text"(todo), "text"(optional), "text"(wip) and "text"(done) markers, from every topic or one, with "text"(outcome) markers as their acceptance criteria — into GitHub issues assigned to the user on the saved default board, TODO into Backlog, optional into In Definition, in-progress into In progress, done into Done and closed, then replaces each filed item in the note with a link to its ticket (keeping a .bak), or with after-filing set to link marks it with its ticket number, so it is never filed twice. Use when asked to turn notes, TODOs or work in progress into tickets or issues, push notes to a board, or file what is open in the notes.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.2.0"
---

# Notes to tickets

Each item becomes a ticket only once, in the right repo, after the user has
seen the list. The scripts guarantee the "only once". The list is your job.

```bash
python ../note-keeping/scripts/notes.py defaults                # where tickets go by default, and to whom
python ../note-keeping/scripts/notes.py defaults --repo owner/name --board "AI common tasks" --assignee @me
python ../note-keeping/scripts/notes.py export [--topic T | --file F] [--status todo,wip,done] \
    [--repo owner/name] [--board N] [--assignee @me|LOGIN|none] --out PLANS_DIR
python ../note-keeping/scripts/notes.py retitle --plans PLANS_DIR --key K --title "Short title"
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
    completed;
  - `"text"(outcome)` is never a ticket. It is an acceptance criterion of the
    marker on its line, else of the item whose scope holds it, else of the
    closest item above it before a blank line.
- The quoted text is the title. Done `- [x]` items are never filed.
- A marker's scope is the bullet or dash lines straight after it, up to a
  blank line or any other line. It becomes the ticket's checklist and is never
  filed as separate tickets. `export` lists such a ticket with its scope count,
  e.g. `build the importer (3 scope items)`. Show it that way.
- Outcomes become the ticket's **Acceptance criteria** checklist and leave
  the scope checklist. `export` counts them, `(2 scope items, 2 outcomes)`.
  Show every line of `outcome_warnings` to the user before filing: those
  outcomes reach no ticket, either because they belong to no item or because
  their item is already filed. Offer to move an orphan under its item.
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

Each ticket's body says where it came from (topic, file and line), then has
the item's full text as its description and a checklist: the scope lines, or
when there are none, the item's full text as the one thing to do. Its
outcomes follow as **Acceptance criteria**, then the item's indented details. No ticket has an empty description or
checklist.

### Short titles for long items

`export` lists every item whose text is longer than a title can be (80
characters) under `needs_short_title`, with its `key`. For each one:

1. Write a short title of 80 characters or fewer that keeps the point, in the
   style of the repo's other tickets. For example, "We need to add another
   team member: a DevOps agent. General DevOps, plus …" becomes "Add a DevOps
   agent: CI/CD per repo and PR review links".
2. Set it: `notes.py retitle --plans PLANS_DIR --key K --title "<short title>"`.
   The full text stays in the description and the checklist, so nothing is
   lost. The link left in the note uses the short title.
3. In the list you show, give the short title with the full text under it,
   so the user approves both.

Never file a title that ends in "…". That cut is only a fallback for when no
short title was set.

If a title reads badly out of context, offer a better one the same way, with
`retitle`. Tell the user that each filed
item will be replaced in the note by a link to its ticket, unless `defaults` shows `after_filing:
link` or they ask to keep them (`export --keep`). Stop here until the user
says yes.

## 3. File, then link the note

Run `file --plans PLANS_DIR --yes`. For each plan it calls the shared
`ticket-management` batch with `GH_REPO` set to that plan's repo, puts every
ticket in its column, and assigns it. Tickets created into Done are then
closed as completed. Then it settles the note:

- **remove** (the default): each filed item is replaced by one line linking
  to its ticket, `→ [#N title](https://github.com/owner/repo/issues/N)`, since it now lives there. A checkbox
  item is replaced together with its indented details. An inline marker is
  replaced with its whole line and its scope; a line with several filed
  markers becomes one link per ticket. The ticket already holds the title,
  the quoted line and the scope. The previous version is saved as
  `<file>.bak`. A line that also holds a marker that wasn't filed stays, and
  its filed marker gets `→ #N`. The line is replaced on the run that files its
  last marker. Link lines are never filed and never join a scope. Outcome
  lines go with their item, and one that prose kept apart from it is removed.
- **link** (`defaults --after-filing link`, or `export --keep` for one run):
  every item stays, marked `→ #N` (or `→ owner/repo#N`), right after the
  marker for an inline one. Its outcomes are marked the same way.

Only items whose ticket exists are replaced or marked. If filing fails
partway, the rest of the note is untouched.

- A rerun is safe. Batch skips titles that already exist, and replaced or
  marked items are not exported again.
- If an item moved or was reworded between export and file, it can't be
  found. The output says which one, and the item stays in the note. Delete it
  or add the `→ #N` by hand.

## Reporting

```
Filed:   #N <title> — <repo>, <board> <column>, assigned <who>[, closed]   (from <file>:<line>)
Skipped: <title> — already existed as #N
Replaced: <file>:<lines> — by a link to #N (previous version in <file>.bak)
Not found: <item> — still in the note; delete it or add "→ #N" by hand
```
