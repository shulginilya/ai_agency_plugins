---
name: ticket-management
description: Creates, edits, closes and deletes GitHub issues, creates a whole backlog from a plan in one rerunnable batch with epics linked to their slices, and puts issues on a GitHub Projects board or moves them between its columns. Use when asked to create, file, open or raise a ticket or issue, create a backlog, edit, retitle, relabel, close or delete a ticket, add tickets to a board, or move a card to another column.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Ticket management

Every write here lands on GitHub, where other people see it at once. So
every write is shown before it is made, and each result is reported back with
its link.

```bash
python scripts/tickets.py create --title T --body-file F [--label L] [--project N --status Backlog]
python scripts/tickets.py batch  --plan plan.json --project N --status Backlog [--dry-run]
python scripts/tickets.py edit   --issue I [--title T] [--body-file F] [--add-label L] [--remove-label L]
python scripts/tickets.py close  --issue I [--reason completed|not-planned] [--comment C]
python scripts/tickets.py delete --issue I --confirm I

python scripts/board.py boards                                  # open boards, most used first
python scripts/board.py add  --project N --issue I              # card on a board
python scripts/board.py move --project N --issue I --status S   # change column, confirm it held
```

## Who decides

- **In a conversation:** show what you are about to write (the title and body,
  the edit, or the list for a batch) and write only after the user says yes.
- **Under a delivery contract or a crew brief:** the brief decides what you may
  write. Do that much, record each write in your report, and propose the rest.
- **Which board:** use the board the user or the brief named. Otherwise run
  `board.py boards` and ask, recommending the one recent issues use most.
  Never guess.
- **Which repository:** the one the current folder belongs to. To write to
  another, set `GH_REPO=owner/name` on the command. Both scripts and every
  `gh` call they make honor it.

## Create one ticket

Write it for someone who has not seen this conversation:

```
Title:  <type>(<scope>): <outcome>        match the repo's existing titles
Body:   the problem or the user value, the proposal, and testable
        acceptance criteria as checkboxes
```

Write the body to a file and run `create`.

- A `--label` must already exist in the repository. Add
  `--create-missing-labels` to create any that don't.
- Pass `--skip-existing` when the ticket may already exist: an issue with the
  exact same title is reused instead of duplicated.
- Add `--project N --status <column>` to put it on a board in the same step.

## Create a backlog

1. Draft every story first. When scrum-master is installed, its
   `backlog-refinement` skill owns the story format and its `story-splitter`
   agent owns splitting an epic.
2. Write the plan file:
   ```json
   {"issues": [
     {"key": "timeline", "title": "Session timeline view", "body": "...", "labels": ["epic"]},
     {"key": "turns", "title": "Timeline of conversation turns", "body": "...", "parent": "timeline"}
   ]}
   ```
   Each `key` is unique. A `parent` must be an earlier item. Labels must
   already exist in the repository.
3. Run `batch --dry-run` and show the user its list. It marks each item
   `create`, or `exists` with the number already taken by that title.
4. After approval, run `batch` with `--project` and `--status`. Children are
   linked to their epic as sub-issues, or as task-list lines in the epic's body
   where the repository has no sub-issues.
5. If it stops partway, fix the cause and run the same command again.
   Everything already created is skipped.

## Edit or close

- `edit` changes the title, body or labels. Keep the title unless it
  misdescribes the work, because renaming breaks links people have already
  pasted. To change a body, read the current one first
  (`gh issue view I --json body`) and edit that, so nothing is lost.
- `close --reason completed` for done work. `close --reason not-planned` for
  work that is dropped, a duplicate, or out of scope. Add `--comment` saying
  why, and link the duplicate.

## Delete

Deleting removes the issue, its comments and its history for everyone, and
GitHub cannot undo it. Only the repository's admins can do it.

- Prefer `close --reason not-planned`. Delete only spam, a ticket created by
  mistake (a wrong-repo or duplicate batch run), or one that holds something
  that must not stay public, such as a leaked secret.
- Delete only when the user, or the brief, names that exact ticket for
  deletion. Then run `delete --issue I --confirm I`. The script refuses unless
  the number is repeated.

## Board columns

`board.py move` re-reads the card several times after moving it, because board
automations move cards asynchronously. For example, "Pull request linked to
issue" moves a card to In progress seconds after a PR opens. It exits 1 if the
column will not hold. Report that failure instead of claiming the move.

## Reporting

```
Created:  #N <title> — <url>   (on <board>, <column>)
Skipped:  #N <title> — already existed
Edited / Closed / Deleted:  #N — <what changed>
Not done: <anything proposed but not written, and why>
```
