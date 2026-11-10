---
name: crew-workflow
description: Runs ticket work through the crew in a repository whose GitHub Projects board has the crew columns (In approval, QA). Each step uses its crew command, every ticket or board write is shown first, and work stops at In approval and Ready for Merge. Use when asked to do, work, build or ship a ticket or issue, or pick up the next one.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.2.0"
---

# Crew workflow

The user is the Captain. You lead the crew: you pick the crew command for each
step, run it, and report back. The crew commands do the work. You never
improvise a step, its order, or the format of a ticket or PR.

Apply this skill in a repository whose board has the crew columns. The
session-start line `crew board "<name>" ...` says so.

When the session-start line says the repository has **no crew board**, ask the
Captain in your first reply, before anything else, whether to create one and
what to call it. On a yes, run `/crew:create-board <name>` (the yes
covers the plan it shows), then apply this skill for the rest of the session.
On a no, run the `--decline` command that line gives, so the repository is not
asked about again, and carry on without this skill.

Without either line, this skill does not apply.

## Rules for every session

1. **Every step runs through its crew command** (the routing below). Code for
   a ticket is written by `/developer:implement`, `/developer:fix`,
   `/developer:tdd` or `/developer:refactor`. Never by hand outside them.
2. **Show every ticket or board write before making it.** That means creating,
   editing or closing a ticket, a comment, a label, or moving a card. Say what
   will change and where, then wait for a yes. One yes may cover a list you
   showed in full. A crew command's own card move (`/developer:ship` to In
   review, `/code-reviewer:review`, `/qa:verify`) counts as shown when you
   name it before running the command.
3. **Never skip a column.** A ticket moves one column at a time, by the role
   that owns that move (the table below).
4. **Stop at In approval.** The Captain reviews the code and moves the card to
   QA. Never move a card out of In approval.
5. **Stop at Ready for Merge.** Never merge a PR. The Captain merges.
6. **No PR without a ticket, and never a second ticket for the same work.**
   For a ticket that exists, run `/developer:ship #N` so it reuses #N. Only
   work with no ticket gets a new one from `/developer:ship`. Tickets are
   written with the `ticket-management` skill.
7. **When a step cannot be settled, ask the Captain.** Do not guess on
   anything irreversible.

When you stop, report the ticket link, the PR link, the column the card is in,
and what the Captain decides next.

## "Do ticket #N"

1. Read the ticket and its column.
   - In Definition or Backlog: `/scrum-master:refine #N` first. A ticket
     without testable acceptance criteria is not ready to build. Refine
     edits the ticket but moves no card: once it meets the Definition of
     Ready, move it one column at a time (rule 2 for each), from In
     Definition to Backlog, then Ready, then In progress.
   - Ready: move it to In progress (rule 2).
   - Already further along: continue from that column, not from the start.
2. `/qa:plan #N`: a test case for every acceptance criterion. A criterion that
   can't be tested as written goes back to the Captain before building.
3. New or changed UI: `/designer:spec #N` before building.
4. `/developer:implement #N`: test-first, in slices. The Captain approves the
   change plan.
5. New or changed UI: `/designer:review` on the built UI, and fix every
   blocker.
6. `/developer:verify` must pass.
7. `/developer:ship #N board <crew board>`: reuses #N (no new ticket) on the
   board it is already on, branch, commit, a PR with `Closes #N`, and #N's
   card to In review.
8. `/code-reviewer:review <PR>`:
   - request changes: the card goes to In progress. Fix with the developer
     commands and push to the same PR. Move the card back to In review
     (rule 2), then run the review again on the new head. Never re-run the
     review while the card is in In progress: its approve would skip In
     review.
   - approve: the card goes to In approval, or to QA when the ticket is
     labelled `skip_approval`.
9. **Stop at In approval** and report.

After the Captain moves the card to QA and asks for it:

10. `/qa:verify #N` on the ticket's review link when it has one:
    - reject: QA comments what fails and moves the card to In progress. Fix
      and push to the same PR, then go round again from step 8: move the card
      to In review, `/code-reviewer:review` the new head, and stop at In
      approval. QA verifies again only after the Captain moves the card to
      QA; `/qa:verify` refuses a card in any other column.
    - accept: QA moves the card to Ready for Merge.
11. **Stop at Ready for Merge** and report.

## Routing

- Feature, ticket or change: `/developer:implement`. Build it test-first: each
  slice in red-green-refactor cycles with the `test-driven-development` skill.
- Restructure without behaviour change: `/developer:refactor`.
- New or changed UI: `/designer:spec` before building, so every state, the
  copy and the accessibility are decided up front. Then `/designer:review` on
  the built UI before pushing, and fix every blocker.
- Bug, failing or flaky test, wrong output: `/developer:diagnose` to a proved
  mechanism, then `/developer:fix` with the failing test first. Known-good
  regression: `/developer:bisect`.
- Merge conflicts on a PR: `/developer:resolve-conflicts`, only when the
  Captain asks for it. It rebases onto the base branch, never merges it in, and
  pushes with `--force-with-lease`, the only force-push allowed. A conflict
  that is a decision goes to the Captain.
- Before pushing: self-review the diff against the developer's handoff
  checklist (`feature-implementation` skill), fix what it finds, and
  `/developer:verify` must pass.
- Code review: after `/developer:ship`, `/code-reviewer:review <PR>` reads the
  PR in a fresh context and posts a PR review, every finding backed by a
  failure scenario. The code reviewer never pushes code and never creates,
  edits or closes a ticket.
- Ticket with acceptance criteria: `/qa:plan` before building. Once the card
  is in QA (never from In review or In approval): `/qa:verify` against the
  ticket and its PR, on the ticket's review link when it has one (any
  `<name>.<project>.<review domain>` link in its description or comments). The
  newest link wins. While it serves an older commit than the PR's head, QA
  waits. A new commit or link after QA's verdict means verify again. QA never
  blocks a ticket; it may suggest blocking in its comment.
- Bug found while testing: `/qa:bug` writes the report and files it as a
  ticket labelled "QA testing". Never patch it from the QA step.
- CI/CD: `/devops:ci` sets up or fixes CI. `/devops:preview` gives every PR a
  review link. `/devops:triage` says why a run is red and whose fix it is. A
  PR's review link: `preview_link.py` from the `preview-link` skill. Never ask
  for, print or write a secret value: name the secrets with a
  `gh secret set NAME -R <owner>/<repo>` line for the Captain to run.
- Backlog grooming: `/scrum-master:refine`, `/scrum-master:backlog-health`,
  then file the stories with the `ticket-management` skill
  (`tickets.py batch`).
- Sprint planning: `/scrum-master:plan-sprint`.
- New project board: `/crew:create-board`, only when the Captain asks
  for one.

## Who moves which card

| Move | By |
| --- | --- |
| In Definition → Backlog | scrum-master, once refine has turned the idea into a story |
| Backlog → Ready | scrum-master, once refine meets the Definition of Ready |
| Ready → In progress | developer, when starting the ticket |
| In progress → In review, after a fix | developer, before the review runs again |
| In progress → In review | `/developer:ship`, after the PR exists |
| In review → In approval, or QA with `skip_approval` | `/code-reviewer:review` approve |
| In review → In progress | `/code-reviewer:review` request changes |
| In approval → QA | the Captain only |
| QA → Ready for Merge | `/qa:verify` accept (adds the column if the board lacks it) |
| QA → In progress | `/qa:verify` reject |
| Ready for Merge → Done | the Captain merges; GitHub closes the ticket |

Tickets: the developer and scrum-master commands create, edit and close
tickets and move cards with their `ticket-management` skill. QA creates and
edits tickets, never closes or deletes one, and labels every ticket it creates
"QA testing". A designer, devops or code-reviewer finding that needs a ticket
is filed by a developer or scrum-master step, after the Captain agrees. Delete
a ticket only when the Captain names it for deletion; otherwise close it as
not planned.
