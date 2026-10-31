---
name: board-setup
description: Creates a GitHub Projects board for a repository, with the team's Status columns (In Definition, Backlog, Ready, In progress, In review, In approval, QA, Ready for Merge, Done, or your own), linked to the repository and ready for a backlog. Use when asked to create, set up or start a project board, kanban board or GitHub Project, or when a backlog is about to be created for a repository that has no board yet.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.2.0"
---

# Board setup

A board is where the team will look every day, so it is created once,
deliberately, with columns that mean something.

This is a shared skill (`plugins/_shared/skills/board-setup`). A plugin can
create boards only if it lists `board-setup` in its `shared_skills`, together
with `ticket-management`, whose `board.py` it uses. Today only scrum-master
does.

```bash
python scripts/create_board.py --title "<name>" --dry-run      # what would be created
python scripts/create_board.py --title "<name>" [--columns "Backlog,Ready,In progress,In review,Done"] [--no-link]
python ../ticket-management/scripts/board.py boards             # the boards that already exist
```

## 1. Check that one is needed

Run `board.py boards` first. If an open board already holds this repository's
issues, use it. Two boards for one repository split the team's attention. The
script also refuses to create a board whose title matches an open one.

## 2. Agree the plan

Show the user:

- **Title:** the project's name, as people already say it.
- **Columns, in order.** The default flow is In Definition → Backlog → Ready →
  In progress → In review → In approval → QA → Ready for Merge → Done:
  - **In Definition:** ideas not yet understood well enough to refine. The
    notes plugin files `"text"(optional)` items here.
  - **Backlog:** refined, or waiting to be.
  - **Ready:** meets the Definition of Ready (see `backlog-refinement`).
  - **In progress:** being worked on, or sent back by QA.
  - **In review:** a PR is open, waiting for code review.
  - **In approval:** code review approved; the Captain reviews the code
    personally and moves it to QA.
  - **QA:** waiting for QA to verify it. A ticket labelled
    `skip_approval` comes here straight from code review.
  - **Ready for Merge:** passed QA, waiting for the merge.
  - **Done:** merged.

  Add `Blocked` only if the team will actually use it. Every column is a promise that
  someone moves cards into and out of it.
- **Linked to this repository**, unless the user says otherwise.
- **The `skip_approval` label** in this repository. The script creates
  it if it's missing. A ticket carrying it skips In approval.

`--dry-run` prints exactly this. Create the board only after the user agrees.
Under a crew brief, create one only when the brief asks for a board.

## 3. Create it

Run the same command without `--dry-run`. The script:

1. creates the board under the repository's owner (a user or an organization),
2. links it to the repository,
3. replaces the default columns with the agreed ones, colored by meaning
   (Ready blue, In progress yellow, In review purple, Done green). GitHub's
   starting Todo, In Progress and Done columns keep their ids and become
   Backlog, In progress and Done (`kept_from_github`), because GitHub's
   built-in workflows point at them by id: a new id switches the workflow off,
   and then a closed or merged ticket never reaches Done,
4. reads the columns and workflows back, fails if the columns do not match,
   and lists any workflow that is off (`workflows_off`), and
5. creates the `skip_approval` label in the repository if it is missing
   (`labels_created`).

It needs the token's `project` scope. If GitHub refuses with a scope error,
tell the user to run `gh auth refresh -s project`. Do not work around it.

## 4. After creating it

- Moving a ticket to Done when its PR merges or it closes is GitHub's
  built-in workflows ("Item closed" and "Pull request merged"), not ours. If
  the result has `workflows_off`, tell the user exactly which to enable under
  the board's ⋯ → Workflows: GitHub's API can't turn a workflow on.
- To fill the board, use the `ticket-management` skill:
  `tickets.py batch --plan plan.json --project <number> --status Backlog`.

## Reporting

```
Board:   #<number> <title> — <url>
Columns: <in order>
Linked:  <owner/repo, or "not linked">
Labels:  skip_approval (created, or already there)
Workflows: all on, or "off: <names>, enable them under ⋯ → Workflows"
Next:    <the backlog step, or what the user should check>
```
