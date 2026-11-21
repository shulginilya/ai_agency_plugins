# Self-review before handoff

Everything here is something a reviewer will otherwise find for you, more
slowly and more expensively. Work it against your own diff.

## Read your own diff

`git diff` (or `git diff <base>...HEAD`) top to bottom, every hunk, as if
someone else wrote it and you are looking for what is wrong. Most of what a
first-round review catches is visible in the diff alone.

## The checklist

**Requirements**

- [ ] Every acceptance criterion from the plan: name the test or the concrete
      observation that proves it. Not "should work".
- [ ] Anything you decided not to do is stated, with the reason.
- [ ] No scope you added that nobody asked for.

**Correctness**

- [ ] Boundaries exercised: zero, one, empty, null/undefined, max, one past it.
- [ ] Every error path has a defined behaviour — and a caller that can act on
      it. What does the user actually see when this fails?
- [ ] Concurrency: two of these at once, a retry landing after the original, an
      event arriving before state is ready.
- [ ] Read-then-write without a guard is a race until proven otherwise.

**Fit**

- [ ] Matches how this codebase does it — naming, layering, error handling,
      logging.
- [ ] No copy of logic that already exists somewhere else in the repo.
- [ ] New dependency? Justified, pinned, and licence-compatible. Prefer the
      twenty lines you can read over the transitive tree you cannot.

**Tests**

- [ ] The test fails without your change. Verify this by reverting the fix
      locally, not by assuming it.
- [ ] It asserts behaviour, not implementation detail; it does not simply
      restate the code.
- [ ] Test names say what breaks when they fail.
- [ ] No `.only`, no skipped test left behind, no sleep-based timing.

**Debris**

- [ ] No debug logging, commented-out code, or scratch files.
- [ ] No secrets, tokens, real customer data, or absolute local paths.
- [ ] No unrelated formatting churn drowning the real change.
- [ ] TODOs either have an owner and an issue, or are removed.

**Operability**

- [ ] A new failure mode is observable — log, metric, or alert. If it can break
      silently in production, that is unfinished work.
- [ ] Migration and the code needing it are ordered, and the ordering is
      stated.
- [ ] Feature flag default is the safe value, and removing the flag is someone's
      known next step.
- [ ] `git revert` alone undoes this. If it does not, say what else is needed.

## The last question

*If this breaks at 3am, what will the person on call see, and will it tell them
where to look?*

If the answer is "a 500 with no context", finish the change.
