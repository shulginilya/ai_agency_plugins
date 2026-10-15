---
name: root-cause-analysis
description: Diagnoses a failure down to its mechanism before changing any code — reproduce it deterministically, narrow it to the smallest failing case, prove causation, fix the cause rather than the symptom, and leave a test that fails without the fix. Use when the user reports a bug, a crash, a stack trace, wrong output, a failing or flaky test, or asks why something is broken and what the root cause is.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Root cause analysis

A bug report is a symptom. The job is to find the mechanism that produces it,
prove that mechanism is the one at work, and remove it. Anything else is
guessing with a commit attached.

## Do not fix first

The strongest pull in debugging is to spot something that looks wrong and
change it. Resist it until step 4. A plausible fix applied to an unproven cause
does three things: it hides the real fault, it adds a change nobody can
justify later, and it destroys the reproduction you needed.

You may read anything. Change nothing until causation is proved.

## 1. State the symptom precisely

Write it down before touching the code, in four parts:

- **Observed** — exactly what happens, quoted: the error text, the wrong value,
  the blank screen.
- **Expected** — what should happen instead, and where that expectation comes
  from (a spec, a test, prior behaviour, a user).
- **Scope** — which environment, which users, which inputs, which routes. "It
  fails" and "it fails for orders with no shipping address" are different bugs.
- **Onset** — always, since a deploy, since an upgrade, intermittently.

If onset is "it used to work", stop and use the `regression-triage` skill
first: finding the commit that introduced it is faster than reasoning about the
current code, and it hands you the mechanism for free.

Ask the user for whichever of the four you cannot establish. A vague symptom
statement is the single largest cause of wasted debugging.

## 2. Reproduce

You cannot diagnose what you cannot trigger.

```bash
python scripts/repro.py --discover              # what this repo declares as test/build/lint
python scripts/repro.py --test "order total"    # run one matching test, isolated
python scripts/repro.py --cmd "npm test -- cart" --times 10   # is it deterministic?
```

The `--times` run is not optional when the report says "sometimes". A fault
that fails 3 times in 10 is a different class of bug from one that fails every
time, and the two need different tools — see
[references/reproduction.md](references/reproduction.md), which also covers
reducing to a minimal case and what to do when you genuinely cannot reproduce.

Record the reproduction as a command anyone can run. If it takes prose to
explain how to trigger the bug, you do not have a reproduction yet.

## 3. Narrow

Halve the search space repeatedly. Never read the whole codebase looking for
something wrong.

| Axis | The cut | When to use it |
| --- | --- | --- |
| Time | `git bisect` between a good and a bad ref | onset is "used to work" — see `regression-triage` |
| Input | remove half the input, does it still fail | data-dependent faults |
| Layer | assert the value at the boundary between layers | wrong data arriving somewhere |
| Config | run with the other environment's config | "works on my machine" |
| Dependency | pin the previous version | onset is "since the upgrade" |

At each cut, state the prediction before you run it: "if the cause is below
this boundary, the value here is already wrong." A cut whose outcome you cannot
predict teaches you nothing either way.

Match the symptom's signature against
[references/bug-classes.md](references/bug-classes.md) to pick the first probe.
Load it as soon as you have a reproduction — it is a symptom-to-mechanism
table, not background reading.

## 4. Prove causation

Correlation is where most debugging stops. Two tests separate a cause from a
coincidence:

1. **Make it fail on demand.** With the mechanism you claim, you can produce
   the failure at will from a clean state — a test, a crafted input, a forced
   ordering.
2. **Make it stop.** Suppress only that mechanism and the failure goes away;
   restore it and the failure comes back.

If you cannot do both, you have a hypothesis. Say so, in those words, and keep
narrowing. Never report a hypothesis as a root cause.

Where the harness supports subagents, give each surviving hypothesis to its own
`investigator` run so one context does not carry the bias of the first idea,
then compare the verdicts.

## 5. Fix the cause

The fix removes the mechanism. These remove the evidence instead, and are
rejected unless the user explicitly asks for a stopgap and you label it one:

- a `try`/`catch` or `except` around the failure with nothing in it
- a null guard, `?.`, or `|| {}` added at the crash site rather than where the
  value went missing
- `@ts-ignore`, `eslint-disable`, `# noqa`, a widened type, a cast
- a retry, a `setTimeout`, an `await` added until the race stops firing
- deleting, skipping or loosening the assertion that caught it

Ask of your own fix: *what would still be wrong if this shipped?* If the answer
is "the value is still wrong upstream, we just stopped crashing on it", you are
at step 5 with a step-3 diagnosis.

Keep the fix minimal and separate. Do not carry a refactor, a rename or a
cleanup in the same change — reverting a bug fix must not revert anything else.

## 6. Verify and prevent

Follow [references/verification.md](references/verification.md). The short
version: write the failing test first, confirm it fails without the fix and
passes with it, then sweep the codebase for the same mechanism elsewhere. A
bug that appeared once in a pattern used in forty places is forty bugs.

## Report

```
Root cause: <file>:<line> — <the mechanism, in one sentence>
Trigger: <the exact inputs, state or timing that produce it>
Evidence: <what proved it — the assertion, the log line, the bisected commit>
Blast radius: <every other caller or path that reaches this mechanism>
Fix: <the smallest change that removes the cause>
Guard: <the test that fails without the fix>
```

When causation is not proved, report under `Leading hypothesis:` instead, and
add a `Next probe:` line saying exactly what would confirm or kill it. That is
an honest and useful result; a confident wrong cause is not.

## Rules that keep a diagnosis honest

- **The first plausible explanation is usually wrong.** Generate a second one
  before testing the first, or you will only look for confirmation.
- **Read the error text.** In full, including the frames you skimmed. Most
  stack traces name the file and the line; a surprising number of debugging
  sessions never open them.
- **Trust the reproduction over the reasoning.** When the code "cannot" do what
  the repro shows, the model of the code is wrong, not the machine.
- **Change one thing at a time.** Two simultaneous changes and a passing test
  tell you nothing about which one mattered.
- **Undo your instrumentation.** Logging, prints and temporary asserts come out
  before the fix is proposed, or the change is unreviewable.
- **"Cannot reproduce" is a result.** Report what you tried, what it would take
  to catch it, and what instrumentation to add — do not fix something plausible
  to have shipped a fix.
