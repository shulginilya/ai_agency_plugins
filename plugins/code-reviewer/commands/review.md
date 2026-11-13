---
description: Review a pull request's code in a fresh context and post a PR review; approve moves the ticket to In approval for the Captain's review (to QA when labelled skip_approval), request changes moves it back to In progress, and a third round with issues left stops, moves it to Ready and hands it to the Captain.
argument_hint: "[PR number; nothing for the current branch's PR]"
model: claude-opus-5-5
effort: high
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash Read Grep Glob Write
---

Review: {{ARGS}}

With no argument, use the current branch's PR (`gh pr view --json number`).

Follow the `pr-review` skill:

1. Run `python {{PLUGIN_ROOT}}/skills/pr-review/scripts/pr_scope.py --pr <N>`. `up-to-date` or
   `closed`: say so and stop. `review` or `re-review`: check out the head (`gh pr checkout <N>`) and
   confirm `git rev-parse HEAD` is the head commit it printed. A re-review covers the whole new head.
   Note the `round R of 3; captain @LOGIN` line.
2. Read every changed file in full and the callers of anything whose contract changed. Run the
   repo's checks (`/developer:verify`): a red check is a blocker.
3. Run the correctness and tests passes always, and security, performance and accessibility when
   the diff touches them. Give each pass to a `reviewer` subagent run. Never fix what you find.
4. Write `findings.json` and run
   `python {{PLUGIN_ROOT}}/skills/pr-review/scripts/review_report.py findings.json --commit <sha> --round <R> --captain <LOGIN> > review.md`.
   Add `--skip-approval` when pr_scope shows every closing ticket's approve as `QA`.
   Round 3 or later with any blocker, major or minor left means stop (exit 3); otherwise any blocker
   or major means request changes, and anything else approve.
5. Post it: `gh pr review <N> --comment --body-file review.md`. Then move each closing ticket's card
   on every board pr_scope listed:
   - stop: `... board.py move --project <B> --issue <I> --status "Ready" --create-column --after "Backlog"`
     (even with `skip_approval`). The review body already @mentions the Captain with the summary. Also
     email the Captain that summary when an email connector (Gmail) is available: to `git config user.email`,
     subject `Review stopped: PR #<N> (#<I>) after <R> rounds`, with the PR link and the open findings.
     Then stop: no further fix or review round on this PR.
   - request changes: `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py move --project <B> --issue <I> --status "In progress"`;
   - approve, to the column pr_scope printed for that ticket: In approval, for the Captain's own code review,
     `... board.py move --project <B> --issue <I> --status "In approval" --create-column --after "In review"`;
     or, when it is labelled `skip_approval`, QA:
     `... board.py move --project <B> --issue <I> --status "QA" --create-column --after "In approval"`.
   Never create, edit or close a ticket, and never push.
6. Report the verdict, the commit reviewed, the round, the passes run, the review's link, where each card
   is now, and the findings, most severe first. On a stop, open with `STOPPED after <R> rounds`, say
   whether the email went out, and list what the Captain has to decide.
