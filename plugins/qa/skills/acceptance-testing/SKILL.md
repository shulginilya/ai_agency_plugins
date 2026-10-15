---
name: acceptance-testing
description: Verifies a built change — a branch, a PR or a deployed build — against its ticket's acceptance criteria, case by case with evidence, after the repository's own checks pass, and gives a verdict by fixed rules - accept, reject with the failing criteria, or blocked when a criterion could not be checked. Use when asked to QA, test, verify or sign off a change, check a PR against its ticket, or decide whether work is done.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Acceptance testing

The question is not "does the code look right" but "does it do what the
ticket promised, for the user, including when things go wrong". The verdict
comes from the evidence, by rules, so it can't be talked into a pass.

```bash
python ../test-planning/scripts/criteria.py --issue 42       # what was promised
python scripts/qa_report.py results.json                     # the verdict; exit 0 only on accept
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

## 2. Gate on the repository's own checks

Run `/developer:verify`, or the checks the repo declares. If they fail, the
verdict is **reject**, with the failing check as the reason. Don't test
features on top of a red build.

## 3. Execute every case

Run the app the way the README says, and work through the plan. For each
case record `status` (pass, fail, blocked or skipped) and `evidence`: the
command and output, a screenshot path, a response, a log line.

- **blocked** means you couldn't make the check: the environment is missing,
  a dependency is down, the data can't be created. Say why in `note`.
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
every case with its `ac`, `kind`, `status`, `evidence` and `note`. Then run
`qa_report.py`:

| Verdict | When |
| --- | --- |
| **reject** | any case failed, or a criterion has no case |
| **blocked** | nothing failed, but some criterion has no passing case (blocked or skipped) |
| **accept** | every criterion has a passing case with evidence, and nothing failed |

A pass with no evidence is counted as not run.

## 5. Report

Give the report `qa_report.py` prints, plus:

- the commit tested, and how (local run, preview URL, test data used),
- one bug ticket per failure, filed by QA with the `bug-reporting` skill and
  labelled **QA testing**, with each ticket's link,
- anything the criteria never covered but a user will hit, as proposed new
  criteria.

On **accept**, say so plainly. On **reject** or **blocked**, the change isn't
done: name exactly what would turn it into an accept.
