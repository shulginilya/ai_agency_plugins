# code-reviewer

The crew's code reviewer. After the developer ships a PR, it reads the
change in a fresh context, the way a senior engineer reads it before anyone
tests it. It finds the defects that would actually bite, proves each one
with a concrete failure scenario, and posts a PR review with a verdict by
fixed rules.

The developer still reviews its own diff before pushing. QA still judges
the change against the ticket's acceptance criteria. The code reviewer sits
between them and judges the code itself: correctness, security,
performance, accessibility and test gaps.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `pr-review` | Scope the PR (review, re-review or up-to-date), read whole files and callers, run the passes, record findings, verdict approve / request changes, post the PR review, move the card on request changes |
| Skill (shared) | `ticket-management` | Bundled only to move a ticket's card: to In progress, In approval or QA. The code reviewer never creates, edits, closes or deletes a ticket. Source: `plugins/_shared/skills/` |
| Command | `/review` | Review one PR and post the verdict |
| Agent | `reviewer` | One pass (correctness, tests, security, performance or accessibility) in a fresh context, returning only findings that carry a failure scenario |

**Verdicts.** There are three:

- **approve**: no blocker and no major finding. The ticket moves to **In
  approval**, where the Captain reviews the code personally and moves it on
  to **QA**. A ticket labelled `skip_approval` skips that review and
  goes straight to **QA**.
- **request changes**: at least one blocker or major. The ticket moves back
  to **In progress**. The developer fixes it, pushes to the same PR, and the
  new head gets a full re-review.
- **stop**: the fourth review round still finds a blocker, major or minor.
  The fix loop isn't converging, so the ticket moves to **Ready**, the PR
  review opens with an @mention of the Captain (the PR's assignee, else the
  repo owner) and a summary of what's left, the Captain also gets the
  summary by email when the session has a Gmail connector, and the crew stops
  working on it. Rounds are counted from the PR's verdict markers since the
  last approve or stop, so a review after a QA reject, or after the Captain
  picks a stopped ticket up again, starts at round 1.

A finding without a failure scenario is refused, so a review can't be padded
with hunches. Nits never change the verdict.

**Posting.** The review is a PR review posted with `gh pr review --comment`.
The crew's GitHub account usually authored the PR, and GitHub won't let an
author approve or request changes on their own PR, so the verdict goes in
the body. A hidden `<!-- code-review:verdict ... -->` marker names the
verdict and the reviewed commit.

It never pushes a commit. There are no hooks, because a crew plugin's hooks
run in every crew session.

Two scripts, both standard-library Python:

- `skills/pr-review/scripts/pr_scope.py` reads a PR through `gh`: its head
  commit, base, changed files, the tickets it closes and their board
  columns, and every earlier review. From the last verdict marker it says
  `review`, `re-review` (a new head since then), `up-to-date` (this head was
  already reviewed) or `closed`, plus the review round and the Captain to
  @mention on a stop.
- `skills/pr-review/scripts/review_report.py` turns recorded findings into
  the verdict and the PR review body. It refuses a finding that isn't a nit
  and has no failure scenario, and a review whose passes leave out
  correctness or tests. It exits 0 on approve, 1 on request changes and 3
  on stop.

`references/` holds the security, performance and accessibility checklists.
Each pass loads its checklist only when the diff touches that area.

## Try it

```bash
python plugins/code-reviewer/skills/pr-review/scripts/pr_scope.py --pr 87
python plugins/code-reviewer/skills/pr-review/scripts/review_report.py findings.json --commit abc1234
python -m tools.apkit test --plugin code-reviewer
```

## Install it

It's a crew plugin. Install it with the others listed under `crew` in
`integrations/crew/team.json`, or on its own:

```bash
python -m tools.apkit build --plugin code-reviewer
python -m tools.apkit install code-reviewer --target claude-code
```

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes the skills, the command and the `reviewer` agent.
- **Codex CLI, Cursor, Gemini CLI** take the skills and the command.
  `reviewer` becomes a skill, so the passes survive but the fresh context
  doesn't. Run each pass in a new session.
- **Generic `.agents/skills`** takes the skills only. The skill carries its
  own scripts.
