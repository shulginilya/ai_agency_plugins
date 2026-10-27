---
description: Ship a finished change for review — ticket on a board, branch, commit, push, PR, card moved to In review.
argument_hint: "[optional: board name or number, ticket title, or what to leave out]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(git:*) Bash(gh:*) Bash(python:*) Read Grep Glob Write
---

Ship the current change for review. Notes: {{ARGS}}

Follow the `ship-change` skill:

1. **Check it is shippable.** Its checks pass and the diff is self-reviewed.
   List the files that belong to the change. Make sure there are no secrets.
   If something is missing, say what and stop.
2. **Ask which board** unless the notes, an earlier answer in this conversation
   or a delivery contract name one. Offer
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py boards` and
   recommend the most used.
3. **File the ticket** (Problem, Proposal, Acceptance criteria) and put it on
   the board in one step:
   `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/tickets.py create --title ... --body-file ... --project N`.
4. **Branch** with the name from `board.py branch` and check it out. **Commit**
   only the change's files, ending the message with `Closes #<issue>`.
   **Push** with `-u`. Never force-push and never push to the default branch.
   If the PR conflicts with its base, report it and offer `/resolve-conflicts`;
   don't resolve it unasked.
5. **Open the PR** against the default branch: `Closes #<issue>`, then What
   changed / Why / Checks, with `--assignee @me`. The user is the only
   assignee unless they explicitly asked for someone else on this PR.
6. **Then** run `board.py move` to put the card in In review. It must run after
   the PR exists, because the board's PR-linked automation moves the card to
   In progress.
7. Report in the skill's format, with the PR link on its own line.
