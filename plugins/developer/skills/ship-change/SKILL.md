---
name: ship-change
description: Ships a finished, verified change for review — files a GitHub issue on the board the user picks, creates and checks out a branch named after it, commits, pushes, opens a pull request that closes the issue, and moves the card to the review column, confirming it stays there. Use when asked to ship, open a PR, raise a ticket and a PR, push this for review, put the work up for review, or move a ticket to In review.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.3.0"
---

# Ship a change

The change is done. This skill is the paperwork that gets it reviewed: a ticket
that says why, a branch and a PR that say what, and a board card that says
where it stands. Every step writes to GitHub, so each one is checked before the
next.

The ticket and board steps use the `ticket-management` skill, which ships in
this plugin too. Its scripts are in `../ticket-management/scripts/`:

```bash
python ../ticket-management/scripts/board.py boards                       # open boards, most used first
python ../ticket-management/scripts/tickets.py create --title T --body-file F --project N
python ../ticket-management/scripts/board.py branch --issue I             # <number>-<type>-<slug>
python ../ticket-management/scripts/board.py move   --project N --issue I # to "In review", and confirm it held
```

Below, `board.py` and `tickets.py` mean those two scripts.

## 0. Before anything is written

- **The change must be finished.** Its checks pass (`/verify`) and the diff was
  self-reviewed. If not, say what is missing and stop. Shipping unverified work
  only moves the failure to the reviewer.
- **Know exactly what is in it.** Read `git status` and `git diff`. List the
  files that belong to this change. Anything unrelated stays out of the commit
  and gets mentioned in the report.
- **No secrets.** No `.env`, keys, tokens or credentials in the diff. If one
  is there, stop and say so.
- **A delivery contract wins.** If a brief or project mode decides how work
  reaches the remote (for example a firstmate crew brief), follow it. Do only
  the steps it allows and report the rest as not done.

## 1. Pick the board — ask

Run `board.py boards` and ask the user which board, recommending the one recent
issues use most. Skip the question only when the user already named the board,
in this request or earlier in the conversation, or a delivery contract names it.
Say which board you are using and why. Never guess: a ticket on the wrong board
is invisible to the people who should see it.

## 2. File the ticket

The issue is written for someone who has not seen this conversation:

```
Title:  <type>(<scope>): <outcome>        conventional-commit style, as the repo uses
Body:   ## Problem   — what is wrong or missing today, concretely
        ## Proposal  — the approach, in a few bullets
        ## Acceptance criteria — checkboxes, each one testable
```

Write the body to a file and run
`tickets.py create --title ... --body-file ... --project N`, which creates the
issue and puts it on the board in one step.

## 3. Branch, commit, push

- **Branch:** `board.py branch --issue I`. If you are on the default branch, run
  `git checkout -b <name>`. Uncommitted work comes along. If you are already on
  a feature branch for this work, keep it and say so.
- **Commit** only the files listed in step 0: `git add <paths>`, never
  `git add -A`. The message follows the repo's convention, explains why in the
  body, and ends with `Closes #I`.
- **Push:** `git push -u origin HEAD`. Never force-push, and never push to the
  default branch. The one exception is the `merge-conflict-resolution` skill's
  leased push after a rebase the user asked for.

## 4. Open the PR

`gh pr create --base <default branch> --title <issue title> --body-file ... --assignee @me`,
with this body:

```
Closes #I

## What changed     — per file or area, the change and its reason
## Why              — anything a reviewer would otherwise ask
## Checks           — what was run and its result; what was NOT run, and why
```

**The assignee is the user, always.** `@me` is the GitHub account `gh` is
logged in as, which is the user's. Assign no one else, not a reviewer, a
crewmate or someone the ticket mentions, unless the user explicitly asks for
that person on this PR. If `--assignee` fails, the PR still exists: add the
user with `gh api -X POST repos/<owner>/<repo>/issues/<PR>/assignees -f 'assignees[]=<login>'`
and report it if that fails too.

Do not merge it and do not approve it. Review is the point. If the PR
conflicts with its base, report that and offer to resolve it, but don't
start: resolving conflicts (the `merge-conflict-resolution` skill) needs the
user's go-ahead.

## 5. Move the card — after the PR exists

`board.py move --project N --issue I` (the default column is `In review`; pass
`--status` for another name).

Order matters. Linking a PR to an issue triggers the board's
"Pull request linked to issue" workflow. It moves the card to In progress
asynchronously, seconds later, and undoes any earlier move to review. So
`move` sets the column only after the PR exists, re-reads it several times, and
sets it again if an automation moved it. It exits 1 if the column will not
hold. Report that failure; do not claim the card is in review.

## Reporting

```
Ticket:  <issue URL> — on <board>, column <column as last read>
Branch:  <name>, checked out locally, pushed
PR:      <PR URL>
Assignee: <login>
Checks:  <what ran before shipping>; Not run: <...>
Left out: <uncommitted files not part of this change, or "nothing">
```

The PR link goes on its own line. It is what the user asked for.
