---
name: pr-review
description: Reviews a pull request's code in a fresh context — correctness and tests always, security, performance and accessibility when the diff touches them — and posts a PR review whose findings each carry a concrete failure scenario. Gives approve or request changes by fixed rules; approve moves the ticket to In approval for the Captain's review (to QA when labelled skip_approval), request changes moves it back to In progress. On the fourth round with issues left it stops, moves the ticket to Ready and hands it to the Captain. Re-reviews the new head after a fix push. Use when asked to review a PR or its code, check a diff before QA, find bugs in a shipped change, or re-review a PR after a fix.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.4.0"
---

# PR review

Read the change the way a senior engineer reads it before anyone tests it:
find the defects that would actually bite, prove each one with a failure
scenario, and say nothing about the rest. The verdict comes from the
findings, by rules, so it can't be argued into an approve.

```bash
python scripts/pr_scope.py --pr 43                        # head, files, tickets, and review / re-review / up-to-date
python scripts/review_report.py findings.json --commit SHA --round R --captain LOGIN > review.md   # 0 approve, 1 changes, 3 stop
gh pr review 43 --comment --body-file review.md
python ../ticket-management/scripts/board.py move --project N --issue 42 --status "In progress"   # request changes
python ../ticket-management/scripts/board.py move --project N --issue 42 --status "In approval" \
    --create-column --after "In review"                                                  # approve (QA if skip_approval)
python ../ticket-management/scripts/board.py move --project N --issue 42 --status "Ready" \
    --create-column --after "Backlog"                                                    # stop
```

## 1. Scope the PR

Run `pr_scope.py --pr N`. It prints the head commit, the base, every
changed file with its line counts, the tickets the PR closes, the board
column each one is in and where an approve moves it (`In approval`, or `QA`
when the ticket is labelled `skip_approval`), and an `action`:

- `review`: no earlier verdict. Review it.
- `re-review`: the last verdict covered an older commit. Review the new head
  **in full**. A fix can break what passed before, so don't only check the
  findings you raised.
- `up-to-date`: you already gave a verdict on this head. Say so and stop.
- `closed`: the PR is closed or merged. Say so and stop.

On `review` and `re-review` it also prints `round R of 4; captain @LOGIN`.
The round is 1 plus the request-changes verdicts since the last **approve**
or **stop**. Either one ends the fix loop: a review after a QA reject, or
after the Captain picks a stopped ticket up again, starts at round 1. The Captain
is the PR's first assignee, else the repository owner. Pass both to
`review_report.py`.

Check out the head (`gh pr checkout N`, then confirm `git rev-parse HEAD`
matches the head commit) so you can read whole files and run the tests.

## 2. Read for context, then read the diff

Read every changed file in full, not just the hunks. A diff hides the
context that makes a change wrong: the caller that now passes null, the
invariant two functions up, the migration the new column needs. For every
changed signature, payload, column or route, find its callers (`grep`) and
check they still work.

Read the ticket and its acceptance criteria to learn what the change is
for. Whether it *does* what the ticket promised is QA's call, not yours.
Yours is whether the code is correct, safe and tested.

## 3. The passes

| Pass | Run when | Reference |
| --- | --- | --- |
| Correctness | always | below |
| Tests | always | below |
| Security | input handling, auth, queries, file or network I/O, secrets, dependencies | [references/security.md](references/security.md) |
| Performance | loops over data, queries, rendering, bundle size, hot paths | [references/performance.md](references/performance.md) |
| Accessibility | any user-facing markup or interaction | [references/accessibility.md](references/accessibility.md) |

Give each pass that runs to a separate `reviewer` subagent run, with the
pass name and the changed files, so each one reads in a fresh context. On a
small diff (a few files, under about 200 lines) you can run the passes
yourself, one after another. Merge the results and remove duplicates.

**Correctness.** Ask of each change, in this order:
1. **Boundaries:** zero, one, empty, null, the maximum and one past it.
2. **Error paths:** every failure that is swallowed, every promise with no
   rejection path. What does the user see when this fails?
3. **Concurrency and ordering:** two requests at once, a retry landing after
   the original, a read-then-write with no guard.
4. **State and lifecycle:** stale closures, caches never invalidated,
   subscriptions never torn down.
5. **Contracts:** a changed signature, payload, column or route. Does every
   caller still work, and does the change ship whatever keeps them working?

**Tests.** A change is under-tested when a defect you can describe would
pass CI. Name the missing test and what it should assert, never just "add
tests". Read the existing tests before you claim a gap. Run the repo's checks
(`/developer:verify`): a red check is a blocker finding in its own right,
with the failing command as its failure. Don't ask for tests on pure
refactors, generated files or config.

## 4. Record findings and get the verdict

Write `findings.json` in the shape `review_report.py` documents: the PR,
the ticket, the commit, the passes that ran, and every finding with its
`severity`, `file`, `line`, `claim`, `why`, `failure` and `fix`.

- **blocker**: data loss, a security exposure, a crash on a normal path, or
  a red check.
- **major**: wrong behaviour on a plausible path, or a broken contract.
- **minor**: a real defect on an unlikely path.
- **nit**: style or naming. It never changes the verdict. Usually leave it out.

`review_report.py` refuses any finding that isn't a nit and has no `failure`,
meaning concrete inputs or state and the wrong result they produce. If you
can't write one, you have a hunch, not a finding. Drop it.

| Verdict | When | The ticket |
| --- | --- | --- |
| **approve** | no blocker and no major finding | moves to **In approval**, for the Captain's own code review; to **QA** when labelled `skip_approval` |
| **request changes** | at least one blocker or major | moves to **In progress** |
| **stop** | round 4 or later, and any blocker, major **or minor** left | moves to **Ready**; the review loop ends |

In rounds 1 to 3, minor findings go in the review either way and the
developer decides whether to fix them in this PR. From round 4 a minor left
unfixed stops the loop too: four rounds that still leave defects mean the
fix loop isn't converging, and the Captain decides what happens next. A
fourth round with only nits, or nothing, approves as usual.

## 5. Post the review, then move the ticket

Post the body as a PR review: `gh pr review N --comment --body-file
review.md`. Always use `--comment`. The crew's GitHub account is usually the
PR's author, and GitHub won't let an author approve or request changes on
their own PR. The verdict is in the body, and its
`<!-- code-review:verdict ... -->` marker is what `pr_scope.py` reads next
time.

Then move the card of every ticket the PR closes, on every board
`pr_scope.py` listed:

- **stop**: `board.py move --project N --issue I --status "Ready"
  --create-column --after "Backlog"`, even when the ticket is labelled
  `skip_approval`. The review body already opens with `@<captain>` and a
  summary of the rounds and what is still open. GitHub doesn't notify you
  of your own mention, and the crew usually posts as the Captain's own
  account, so also send the Captain that summary by email when the session
  has an email connector (Gmail): to the Captain's address (`git config
  user.email`), subject `Review stopped: PR #N (#ticket) after R rounds`, the
  PR link and the open findings in the body. Without a connector, say in the
  report that no email went out. Then stop: no further fix or review round
  on this PR until the Captain picks the ticket up again.

- **request changes**: `board.py move --project N --issue I --status "In progress"`.
- **approve**: to the column `pr_scope.py` printed for that ticket.
  `In approval` (`--create-column --after "In review"`) is where the Captain
  reviews the code personally and, on approval, moves the card to QA. A
  ticket labelled `skip_approval` goes straight to `QA`
  (`--create-column --after "In approval"`), and QA picks it up from there.
  `--create-column` adds the column without asking if the board lacks it;
  say so in the report. Pass `--skip-approval` to `review_report.py`
  when every closing ticket carries the label, so the review names QA.

The `ticket-management` skill is bundled only for these moves. Never create,
edit, close or delete a ticket, and never push a commit, not even a one-line
fix. A reviewer who patches what they review is no longer reviewing. If a
finding needs its own ticket, propose it in the report.

## 6. Report

Give the verdict, the commit reviewed, the round, the passes that ran, the
review's link, where each card is now, and the findings ranked most severe
first. On **request changes**, name exactly what would turn the review into
an approve. On **stop**, open the report with `STOPPED after R rounds`, say
whether the email went out, and list what the Captain has to decide. An empty review is a valid result: "nothing I can prove would
break" is worth more than five nits.

## Rules that keep a review useful

- **Prove it or drop it.** No failure scenario, no finding.
- **Taste is not a defect.** If the code is fine but you'd have written it
  differently, say nothing.
- **Blame the code, not the author.** Write "this drops the error", not "you forgot".
- **Review the head you were given.** A verdict on the wrong commit is
  worthless, so the marker always names the commit.
