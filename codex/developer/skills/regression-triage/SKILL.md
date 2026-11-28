---
name: regression-triage
description: Finds the change that broke something that used to work — establishes a last known good state, scripts a pass/fail verdict, drives git bisect to the first bad commit, and reads that commit and the file's history to name the mechanism. Use when behaviour regressed after a deploy or upgrade, a previously passing test now fails, or the user asks which commit, release or change broke something.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Regression triage

When something used to work, the history holds the answer. Bisection finds it
in a dozen runs regardless of how large the codebase is, and it does not
require understanding the code first. Reason about the culprit commit, not
about the whole system.

Use this skill when onset is "it worked before". For a bug that never worked,
or one with no good ref to go back to, use the `root-cause-analysis` skill
instead — and come back to it once this skill has named the commit, because a
culprit commit is a lead, not yet a proven cause.

## 1. Get a verdict command

Bisection is only as good as the question you ask at each step. You need one
command that exits 0 when the code is good and non-zero when it is bad, runs in
under a minute or two, and depends on nothing outside the checkout.

```bash
npm test -- cart.total        # whatever the reproduction reduces to
pytest tests/test_cart.py::test_total -x -q
```

The `root-cause-analysis` skill's `repro.py` will tell you what this repo
declares as its test command and whether the verdict is deterministic; reach
for it by skill name, never by a path into a sibling skill.

Requirements the verdict command must meet:

- **Deterministic.** Check it first: run it five times on the known-bad ref and
  five times on the known-good one. A flaky verdict makes bisect confidently
  wrong. If it is flaky, see the repetition recipe in
  [references/bisect-recipes.md](references/bisect-recipes.md).
- **Specific.** It should fail for *this* bug, not for any failure. A whole
  suite fails for unrelated reasons at old commits and misleads the search.
- **Independent of build state.** Include the install or build step if old
  commits need a different lockfile — see the recipes.

## 2. Bracket the range

Find a ref where the verdict passes. Do not guess further back than necessary:
every extra commit in the range costs at most one more step, but a bad "good"
ref invalidates the whole run.

```bash
git log --oneline --first-parent -30
git tag --sort=-creatordate | head
python scripts/git_bisect.py --good v1.4.0 --cmd "npm test -- cart.total"
```

Run it without `--run` first. It prints the range, the commit count and the
number of steps, and verifies the verdict on both ends — a "good" ref that
already fails is the most common wasted bisect.

## 3. Bisect

```bash
python scripts/git_bisect.py --good v1.4.0 --cmd "npm test -- cart.total" --run
```

The script refuses to start on a dirty tree, always resets the bisect state
when it finishes or is interrupted, and reports the first bad commit with its
diff summary. Exit code 125 from the verdict command marks a commit
unbuildable and skips it rather than lying about it.

If bisection is not available — no repro, shallow clone, squashed history,
non-deterministic verdict — fall back to step 4 alone and say in the report
that the culprit is inferred, not bisected.

## 4. Read the culprit

A commit is not a cause. Open it and answer, in this order:

1. **Which hunk touches the failing path?** Ignore the rest of the commit.
2. **What did it change about behaviour** — not what the message says it
   changed. Renames and moves inside a "refactor" hide semantic edits.
3. **What assumption did it break?** Almost every regression is a change that
   was locally correct and violated an assumption held somewhere else.
4. **Why did no test catch it?** That gap is part of the finding.

Then widen with the file's history:

```bash
python scripts/history.py src/cart/total.ts --lines 40-90
python scripts/history.py src/cart/total.ts --since 2026-06-01 --json
```

It groups blame by commit with line counts and lists the recent commits
touching the path, which surfaces the case bisect cannot see: the culprit
commit only exposed a latent fault that an older commit introduced.

## 5. Hand off

A culprit commit narrows the search to a few lines. Now prove the mechanism
with the `root-cause-analysis` skill — steps 4 through 6, causation, fix and
regression test — and report:

```
Culprit: <sha> <subject> (<author>, <date>)
Verdict command: <the exact command bisect ran>
Range: <good ref>..<bad ref>, <n> commits, <k> steps
Broke: <the hunk, and the assumption it violated>
Why CI missed it: <the gap>
Fix direction: revert | forward-fix | <the specific change>
```

Prefer a revert when the culprit is self-contained and the fix is not urgent —
it restores a known-good state and buys time to fix properly. Prefer a
forward-fix when the culprit also carries wanted behaviour, or when reverting
would undo a migration or a contract change that already shipped.

## Rules

- **Verify both ends before bisecting.** A bad bracket produces a confident,
  wrong sha and hours of misplaced trust.
- **Bisect commits, not deploys, when both exist** — but if the deploy pipeline
  changed and the code did not, the regression is in the pipeline, and no
  commit bisect will find it. Check the deploy diff too: config, base image,
  dependency resolution, environment.
- **`git bisect skip` is honest; a guess is not.** Never mark a commit good or
  bad because building it is inconvenient.
- **Always reset.** Leaving a repo in a bisect state costs the next person an
  hour of confusion. The script does it in a `finally`; do the same by hand.
- **An upgrade is a bisect target too.** When the code range comes back empty,
  bisect the lockfile: pin dependencies to the previous resolution and retest.
