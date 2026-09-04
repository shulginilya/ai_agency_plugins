---
name: code-review
description: Reviews a diff, branch or pull request and reports defects ranked by severity, each with a concrete failure scenario. Covers correctness, security, performance, accessibility and test coverage. Use when the user asks to review code, check a diff or branch, look over a PR before merging, or find bugs in changes that were just made.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Code review

Review changed code the way a senior engineer reviews it: find defects that
would actually bite, prove each one, and say nothing about the rest.

## Scope first

Determine what changed before reading anything.

```bash
python scripts/changed_files.py            # working tree vs HEAD
python scripts/changed_files.py --base main
python scripts/changed_files.py --base origin/main --json
```

If the user named a path, a branch or a PR, use that instead. If the diff is
empty, say so and stop — do not review the whole repository because a diff was
requested.

Read every changed file in full, not just the hunks. A diff hides the context
that makes a change wrong: the caller that now passes null, the invariant two
functions up, the migration the new column needs.

## The passes

Run these in order. Each pass has its own reference file; load one only when
the change touches that surface.

| Pass | Load when | Reference |
| --- | --- | --- |
| Correctness | always | this file, below |
| Security | input handling, auth, queries, file or network I/O, secrets, deps | [references/security.md](references/security.md) |
| Performance | loops over data, queries, rendering, bundle size, hot paths | [references/performance.md](references/performance.md) |
| Accessibility | any user-facing markup or interaction | [references/accessibility.md](references/accessibility.md) |
| Tests | always | this file, below |

### Correctness

Ask of each change, in this order:

1. **Boundaries.** What happens at zero, one, empty, null, the maximum, and one
   past it? Off-by-one and empty-collection handling are the two most common
   real defects in reviewed code.
2. **Error paths.** Every `try` without a matching failure behaviour, every
   promise without a rejection path, every non-zero exit that is swallowed.
   Ask what the user sees when this fails.
3. **Concurrency and ordering.** Two requests arriving at once, a retry landing
   after the original, a listener firing before state is ready. Anything that
   reads then writes without a guard is a candidate.
4. **State and lifecycle.** Stale closures, effects that re-run, caches that
   are never invalidated, subscriptions that are never torn down.
5. **Contracts.** Does the change alter a signature, a payload shape, a
   database column, or a public route? If so, who else depends on it, and does
   the change ship with the thing that keeps them working?

### Tests

A change is under-tested when a defect you can describe would pass CI. Say
which test is missing and what it should assert — not "add tests".

Do not ask for tests on pure refactors with no behaviour change, on generated
files, or on config.

## Reporting

Report findings ranked most severe first. Each finding is four lines:

```
<severity> <file>:<line> — <one-sentence claim>
Why: <the invariant or assumption that breaks>
Failure: <concrete inputs or state -> wrong output, crash, or exposure>
Fix: <the smallest change that closes it>
```

Severity:

- **blocker** — data loss, security exposure, or a crash on a normal path
- **major** — wrong behaviour on a plausible path, or a contract break
- **minor** — a real defect on an unlikely path
- **nit** — style or naming; group these into one line at the end, or omit them

## Rules that keep a review useful

- **Prove it or drop it.** If you cannot write the Failure line with concrete
  inputs, you have a hunch, not a finding. Delete it.
- **No taste-as-defect.** Preference dressed as a bug wastes the author's time.
  If the code is fine but you would have written it differently, say nothing.
- **Read the tests before claiming a gap.** Half of "missing test coverage"
  findings are tests the reviewer did not open.
- **Blame the code, not the author.** "This drops the error" beats "you forgot".
- **Empty is a valid result.** "I found nothing that would break" is a complete
  review, and a more trustworthy one than five nits.

## Working with the reviewer subagent

Where the harness supports subagents, delegate each pass to a separate
`reviewer` run so no single context holds the whole diff, then merge the
findings and de-duplicate before reporting. Where it does not, run the passes
sequentially in one context and keep a running findings list.
