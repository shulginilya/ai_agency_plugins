---
name: acceptance-testing
description: Verifies a built change — a branch, a PR, or the review link on its ticket (any <name>.<project>.review.com link in the description or comments), re-testing when a new link appears — against the ticket's acceptance criteria, case by case with evidence, after the repository's own checks pass. Gives accept or reject by fixed rules, comments on the ticket, and moves it to Ready for Merge (adding that column if the board lacks it) or back to In progress. Use when asked to QA, test, verify or sign off a change, check a PR or review link against its ticket, or decide whether work is done.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.4.0"
---

# Acceptance testing

The question is not "does the code look right" but "does it do what the
ticket promised, for the user, including when things go wrong". The verdict
comes from the evidence, by rules, so it can't be talked into a pass.

```bash
python ../test-planning/scripts/criteria.py --issue 42       # what was promised
python scripts/review_link.py --issue 42 --commit SHA        # the review link, and test / retest / up-to-date
python scripts/qa_report.py results.json --link URL --commit SHA > verdict.md   # exit 0 only on accept
gh issue comment 42 --body-file verdict.md
python ../ticket-management/scripts/board.py move --project N --issue 42 \
    --status "Ready for Merge" --create-column               # on accept; on reject: --status "In progress"
```

## 1. Know what you're testing

- **The ticket:** run `criteria.py`. If there's no test plan yet, write one
  first with the `test-planning` skill.
- **The change:** the branch or PR (`gh pr view N`, `gh pr diff N --stat`).
  Read the diff only to find what it touches, so you can add regression
  cases nearby. Don't let the code's intent tell you what the result should
  be. The criteria decide that.
- **The build:** the exact commit you test (`git rev-parse --short HEAD`).
  Record it, because a verdict on the wrong commit is worthless.
- **The review link:** run `review_link.py --issue N --pr PR --wait 600`
  (or `--commit SHA` instead of `--pr`). A review link is any link shaped
  `<name>.<project_slug>.<review domain>` in the ticket's description or
  comments. The name is usually the branch, but can be anything. The review
  domain is the repo variable `REVIEW_DOMAIN`, and `review.com` until one is
  set. **The newest one wins:**
  - **The devops comment** is one comment on the ticket, edited by the
    preview workflow on every deploy. Its hidden marker names the link, the
    commit it serves and whether it's still up. It counts as new as of its
    last edit, and the commit comes from the marker, not from guessing.
  - **A pasted link** (description or comment) counts as of when it was
    posted. Which build it serves is unknown, so confirm the PR's head
    commit with `preview_link.py --pr N` before trusting it.

  Its `action` says what to do:
  - `wait`: the link still serves an older commit than the one under test,
    because the new build hasn't landed. Never test it: you'd pass old code.
    With `--wait` the script polls until the build lands and exits 3 if it
    doesn't. Then report that the preview is stuck.
  - `test`: test against that link. It is the build the user will see, so
    every case runs there, not only locally.
  - `retest`: since your last verdict the link serves a different commit, or
    it's a different link, or one was pasted after it. Run every case again,
    against the new build. A re-test is a full test; a fix can break what
    passed before.
  - `up-to-date`: you already gave a verdict on this link and commit. Say so,
    and stop. Nothing has changed to test.
  - `none`: no review link in the ticket. For a PR, look for its preview
    deployment: `python ../preview-link/scripts/preview_link.py --pr N --wait 600 --check`.
    Test on it only when it's **current**, meaning it was deployed from
    the PR's head commit, and record the URL and its commit. Stale,
    pending or failed means the running build isn't the code under test:
    wait, or test locally. A failed preview deploy is itself a finding.
    With no preview at all, run the app locally.

  If the link doesn't load, that is not a pass: record the cases as
  `unchecked`, with what you saw.

## 2. Gate on the repository's own checks

Run `/developer:verify`, or the checks the repo declares. If they fail, the
verdict is **reject**, with the failing check as the reason. Don't test
features on top of a red build.

## 3. Execute every case

Run the app on the review link, or the way the README says, and work through the plan. For each
case record `status` (pass, fail, unchecked or skipped) and `evidence`: the
command and output, a screenshot path, a response, a log line.

- **unchecked** means you couldn't make the check: the environment is missing,
  the review link is down, the data can't be created. Say why in `note`.
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
Then run `qa_report.py --link <review link> --commit <sha>` (leave out
`--link` when there is none). There are two verdicts, and only two:

| Verdict | When | The ticket moves to |
| --- | --- | --- |
| **accept** | every criterion has a passing case with evidence, on the review link when there is one, and nothing failed | **Ready for Merge** |
| **reject** | anything else: a failure, a criterion with no case, or one that couldn't be checked | **In progress** |

A pass with no evidence is counted as not run. QA never blocks a ticket. When
a criterion couldn't be checked, the verdict is reject and the comment lists
it under "Suggest blocking", with why. Blocking is the Captain's call.

## 5. Comment, then move the ticket

`qa_report.py` prints the ticket comment: the verdict, the link and commit
tested, what fails and how to see it, any blocking suggestion, and a
`<!-- qa:verdict ... -->` marker that `review_link.py` reads next time to know
what was already tested. Post it on the ticket with `gh issue comment N
--body-file`, then move the card on every board `review_link.py` listed:

- **accept**: `board.py move --project N --issue N --status "Ready for Merge"
  --create-column`. If the board has no Ready for Merge column, this adds it
  after In review and proves no other card changed column. Do it without
  asking, and say in the report that you added it.
- **reject**: `board.py move --project N --issue N --status "In progress"`.
  The comment has to say exactly what fails, so the developer can start from
  it without asking.

Never move a ticket to Ready for Merge on anything less than an accept.

## 6. Report

Give the report `qa_report.py` prints, plus:

- the commit tested, and how (review link, local run, test data used),
- the comment's link, and the column each board's card is now in,
- one bug ticket per failure, filed by QA with the `bug-reporting` skill and
  labelled **QA testing**, with each ticket's link,
- anything the criteria never covered but a user will hit, as proposed new
  criteria.

On **accept**, say so plainly. On **reject**, the change isn't done: name
exactly what would turn it into an accept.
