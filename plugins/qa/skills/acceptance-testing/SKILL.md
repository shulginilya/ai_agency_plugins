---
name: acceptance-testing
description: Verifies a built change — a branch or a PR, checked out at its head commit and run locally (review links are paused), re-testing when a new commit lands — against the ticket's acceptance criteria, case by case with evidence, after the repository's own checks pass. Gives accept or reject by fixed rules, comments on the ticket, and moves it to Ready for Merge (adding that column if the board lacks it) or back to In progress. Use when asked to QA, test, verify or sign off a change, check a PR against its ticket, or decide whether work is done.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.6.0"
---

# Acceptance testing

The question is not "does the code look right" but "does it do what the
ticket promised, for the user, including when things go wrong". The verdict
comes from the evidence, by rules, so it can't be talked into a pass.

```bash
python ../test-planning/scripts/criteria.py --issue 42       # what was promised
python scripts/review_link.py --issue 42 --pr 43 --local     # the card's column, and test / retest / up-to-date
python scripts/qa_report.py results.json --commit SHA > verdict.md   # exit 0 only on accept
gh issue comment 42 --body-file verdict.md
python ../ticket-management/scripts/board.py move --project N --issue 42 \
    --status "Ready for Merge" --create-column --after QA    # on accept; on reject: --status "In progress"
```

**Pick up only tickets in the QA column.** A card reaches QA after the code
review approves it and the Captain approves it in In approval, or straight
from code review when the ticket is labelled `skip_approval`.
`review_link.py` lists the card's column on every board. In In review it is
waiting for code review, and in In approval for the Captain's review. Say
where it is and stop: verifying it early tests code nobody has approved yet.

## 1. Know what you're testing

- **The ticket:** run `criteria.py`. If there's no test plan yet, write one
  first with the `test-planning` skill.
- **The change:** the branch or PR (`gh pr view N`, `gh pr diff N --stat`).
  Read the diff only to find what it touches, so you can add regression
  cases nearby. Don't let the code's intent tell you what the result should
  be. The criteria decide that.
- **The build:** the exact commit you test (`git rev-parse --short HEAD`).
  Record it, because a verdict on the wrong commit is worthless.
- **Review links are paused.** Test the PR's head commit locally. Never
  look for, wait on or test a review link or a preview deployment, even when
  the ticket or the PR has one: it is not part of the workflow for now.
- **What to do:** run `review_link.py --issue N --pr PR --local` (or
  `--commit SHA` instead of `--pr`). It ignores links and decides on the
  commit alone. Its `action` says what to do:
  - `test`: no QA verdict yet. Check out the PR (`gh pr checkout PR`),
    confirm `git rev-parse HEAD` is its head commit, and test it.
  - `retest`: the last verdict tested another commit. Run every case again
    on the new one. A re-test is a full test; a fix can break what passed
    before.
  - `up-to-date`: you already gave a verdict on this commit. Say so, and
    stop. Nothing has changed to test.

## 2. Gate on the repository's own checks

Run `/developer:verify`, or the checks the repo declares. If they fail, the
verdict is **reject**, with the failing check as the reason. Don't test
features on top of a red build.

## 3. Execute every case

Run the app locally from the commit under test, the way the README says, and work through the plan. For each
case record `status` (pass, fail, unchecked or skipped) and `evidence`: the
command and output, a screenshot path, a response, a log line.

- **unchecked** means you couldn't make the check: the environment is missing,
  the app won't start locally, the data can't be created. Say why in `note`.
- Don't fix anything you find, even a one-liner. Record it as a failure and
  write it up with the `bug-reporting` skill. QA that patches what it tests
  is no longer testing.
- Spend about 15 minutes exploring beyond the plan: what a hurried or
  confused user would do. Record anything real as an `exploratory` case
  under the closest criterion.

For the most important flow, hand the criteria and the running build to the
`acceptance-checker` subagent. It judges each criterion without having seen
the implementation, so it catches what the plan's author and the developer
both assumed.

## 4. Record results and get the verdict

Write `results.json` in the shape `qa_report.py` documents: the criteria, and
every case with its `ac`, `kind`, `status`, `evidence`, `steps` and `note`.
Then run `qa_report.py --commit <sha>`. There are two verdicts, and only two:

| Verdict | When | The ticket moves to |
| --- | --- | --- |
| **accept** | every criterion has a passing case with evidence, on the commit under test, and nothing failed | **Ready for Merge** |
| **reject** | anything else: a failure, a criterion with no case, or one that couldn't be checked | **In progress** |

A pass with no evidence is counted as not run. QA never blocks a ticket. When
a criterion couldn't be checked, the verdict is reject and the comment lists
it under "Suggest blocking", with why. Blocking is the Captain's call.

## 5. Comment, then move the ticket

`qa_report.py` prints the ticket comment: the verdict, the commit
tested, what fails and how to see it, any blocking suggestion, and a
`<!-- qa:verdict ... -->` marker that `review_link.py` reads next time to know
what was already tested. Post it on the ticket with `gh issue comment N
--body-file`, then move the card on every board `review_link.py` listed:

- **accept**: `board.py move --project N --issue N --status "Ready for Merge"
  --create-column --after QA`. If the board has no Ready for Merge column, this
  adds it after QA and proves no other card changed column. Do it without
  asking, and say in the report that you added it.
- **reject**: `board.py move --project N --issue N --status "In progress"`.
  The comment has to say exactly what fails, so the developer can start from
  it without asking.

Never move a ticket to Ready for Merge on anything less than an accept.

## 6. Report

Give the report `qa_report.py` prints, plus:

- the commit tested, and how (local run, test data used),
- the comment's link, and the column each board's card is now in,
- one bug ticket per failure, filed by QA with the `bug-reporting` skill and
  labelled **QA testing**, with each ticket's link,
- anything the criteria never covered but a user will hit, as proposed new
  criteria.

On **accept**, say so plainly. On **reject**, the change isn't done: name
exactly what would turn it into an accept.
