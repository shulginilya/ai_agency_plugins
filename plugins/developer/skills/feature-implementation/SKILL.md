---
name: feature-implementation
description: Implements a feature or fix end to end — orient in the existing code, agree a change plan, build it in slices that stay green, verify with the repository's own checks, and self-review before handing off. Use when asked to implement or add a feature, build something, work a ticket or issue, wire up an endpoint or component, fix a bug in application code, or finish a change someone else started.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Feature implementation

Writing the code is the short part. What makes a change land cleanly is knowing
where it goes, keeping it small enough to verify, and proving it works the way
the project proves things.

## 1. Orient before you type

Never write the first line until you can answer these:

- **Where does this belong?** Find the module that already owns this concern.
  A new file is a decision — justify it or put the code where its neighbours
  are.
- **How does this codebase already do this?** Find the closest existing
  equivalent — another endpoint, another form, another migration — and read it
  end to end. Match its patterns even where you would have chosen differently.
  Consistency is worth more than your preference.
- **What is the contract?** Signature, payload shape, route, table, event.
  Write down what callers depend on today.
- **What proves it works?** Locate the tests for the neighbouring code. If
  there are none, that is a finding to state now, not after you have finished.

```bash
python scripts/verify.py             # the checks this repo actually runs
```

Ask the user only what the code cannot tell you: an ambiguous requirement, a
product decision, a missing credential. Do not ask what a `grep` answers.

## 2. Write the change plan

Before editing, state the plan in the conversation. Keep it to a handful of
lines — the format and the decomposition rules are in
[references/change-plan.md](references/change-plan.md):

```
Goal:      one sentence, the user-visible outcome
Slices:    2-5 steps, each independently verifiable
Contracts: what changes shape (API, schema, event, config) and who consumes it
Risk:      what could break that the tests would not catch
Verify:    the exact commands that will prove it, and the scoped test
           command each red-green cycle runs
```

Get agreement on the plan when the change is more than a slice or two, when it
alters a contract, or when it touches migrations, auth, money, or data
deletion. Then follow it — and say so if you deviate.

## 3. Implement in slices

One slice at a time, and the tree stays green between slices.

- **Make the change easy, then make the easy change.** If the code resists,
  refactor first as its own slice — see the `safe-refactoring` skill — then
  add behaviour. Never combine the two in one commit.
- **Drive each slice test-first,** with the `test-driven-development` skill:
  a test list from the slice's acceptance test, then red, green and refactor
  for one behaviour at a time. Each red is checked with `tdd.py check
  --expect red`, so it is a real failure and not an import error or an empty
  run. For a bug fix, the first red reproduces the reported defect: it is the
  only proof the fix addresses that defect and not a lookalike.
- **Handle the unhappy path in the same slice.** The empty list, the timeout,
  the rejected promise, the 404. An error path added later is an error path
  that was never run.
- **Do not smuggle.** No drive-by renames, no unrelated formatting, no
  dependency bumps. They make the change unreviewable and unrevertable.
- **Leave nothing dead.** If you replace something, delete the old path in the
  same slice or say explicitly why it must stay.

Extended work benefits from delegation: hand a single slice, with its plan
entry and its acceptance test, to the `implementer` subagent so the main
context holds the plan rather than every hunk. Merge and verify its report
yourself — the plan is still yours.

## 4. Verify with the project's own checks

```bash
python scripts/verify.py --run       # runs them in order, stops at the first failure
```

Run the whole set, not just the test you wrote. A green unit test beside a
broken type-check is not a finished change. If a check fails for a reason that
predates your change, say so explicitly instead of quietly ignoring it.

When a check does not exist — no linter, no test runner — say that too, and
verify by hand: state exactly what you ran or observed.

## 5. Self-review before handoff

Work [references/handoff.md](references/handoff.md) before you call it done.
The short version:

1. Re-read your own diff top to bottom, as if someone else wrote it.
2. Every acceptance criterion from the plan: name the test or the observation
   that proves it.
3. Boundaries: zero, one, empty, null, max, and one past it.
4. Debris: debug logging, commented-out code, `.only`, TODOs, stray files.
5. Contract changes: is the consumer updated, or is there a deploy ordering
   that must be stated?

## Reporting

Report what you did like this, and no longer:

```
Done: <the outcome, one sentence>
Changed: <file> — <why>, ... (group trivia)
Verified: <commands run and their result, or what you observed by hand>
Not done: <anything deferred, out of scope, or still failing — with the reason>
```

State the incomplete parts plainly. A change described as finished when it is
not costs more than the work it saved.
