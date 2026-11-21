---
name: test-driven-development
description: Builds a feature or fix test-first in red-green-refactor cycles — a test list from the acceptance criteria, then one failing test per behaviour, watched to fail on its assertion, the smallest code that passes it, and a refactor on green — with a script that runs the tests and tells a real red from an errored or empty run. Use when asked to work test-first or with TDD, write the failing test first, do red-green-refactor, drive a change or a bug fix with tests, or prove a test fails before the fix.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Test-driven development

Every line of production code is written to turn one failing test green. The
test comes first, it is seen to fail for the reason it states, and only then
does the code follow. The loop is short on purpose: one behaviour, one test,
one small change, then clean up while everything is green.

```bash
python scripts/tdd.py detect                                  # the test command this repo declares
python scripts/tdd.py check --cmd "<scoped command>" --expect red    # after writing the test
python scripts/tdd.py check --cmd "<scoped command>" --expect green  # after the code, and after each refactor
```

`check` names one of four states: GREEN, RED, ERRORED or UNUSABLE. With
`--expect`, it exits 1 when the step didn't earn its state. The run is a
**red** only when a test ran and failed. A load, import or compile error, a
crash, a timeout, or a run that collected no tests is **ERRORED**, and
`--expect red` refuses it. That is the difference between a red that
specifies behaviour and one that only says the code doesn't load.

## Before the first test

1. **The test command.** Run `detect`, or read how the repo runs its tests.
   Scope the command to the tests in play: a file, a test name, a package.
   A cycle that runs the whole suite every time is a cycle that gets skipped.
   Scoping per runner is in [references/cycle.md](references/cycle.md).
   If the repo has no test runner, stop and say so. Don't invent one silently.
2. **The test list.** Turn the acceptance criteria, the slice or the bug
   report into a short list of behaviours, one line each. Include the
   unhappy paths: empty, missing, invalid, too many, the failure of a
   dependency. Start with the simplest behaviour that is still useful. Add to
   the list as you discover things, and never act on an idea that isn't on it.

## The cycle

### Red: one failing test

- Write **one** test for **one** behaviour, in the project's existing test
  style, next to its neighbours. Name it for the behaviour, not the method.
- Run `check --expect red`. It must be RED, and the failing test must be the
  one you just wrote (`check` lists the failing tests).
- `failed_how: exception` (a `NameError`, `is not defined`, a missing
  attribute) means the code under test doesn't exist yet. Add the smallest
  stub (the function, returning nothing useful) and check again until the test
  fails **on its assertion**. Only an assertion failure says what the code
  must do.
- GREEN means the test passed straight away, or isn't being collected. Either
  the behaviour already exists (cross it off, keep the test if it adds
  coverage) or the test is wrong. Don't write code against a test you never
  saw fail.
- ERRORED means fix the load or collection error first. It is not progress.

### Green: the smallest change that passes

- Write the least code that turns this test green: a constant, a single
  branch, whatever is simplest. Generalise only when the next test forces it.
- Run `check --expect green`. The other tests in scope must stay green too.
- **Never edit the test to meet the code.** If the test is wrong, go back to
  red, fix the test, and watch it fail again.
- No code that no test asked for. A branch you want to add is the next test
  on the list, not part of this step.

### Refactor: on green only

- Remove duplication and improve names, in the code **and** the tests, one
  small move at a time, running `check --expect green` after each move.
- A refactor that goes red is reverted to the last green, not fixed forward.
- Behaviour doesn't change here. A new behaviour needs a new red.

Then cross the item off the list and pick the next one.

## Bug fixes

1. Write a test that reproduces the reported bug and fails for the reported
   reason (`--expect red`, on its assertion).
2. Make the smallest change that removes the cause (`--expect green`).
3. Prove it both ways: undo the fix and the test goes red, restore it and it
   goes green.

## Finishing

- Run the repo's full checks (the whole suite, types, lint), not just the
  scoped command. A green slice beside a broken suite isn't finished.
- Leave nothing behind: no focused or skipped tests (`.only`, `skip`,
  `xfail` added during the work), no debug prints, no commented-out tests.

## When not to drive with a test

Say so explicitly in the report instead of faking a red:

- **A spike** to learn an API: throw it away, then test-drive the real code.
- **Pure configuration, wiring or generated code**, which only an
  integration run proves.
- **Visual details** of a UI: test the behaviour (what renders, what a click
  does), not the pixels.

## Reporting

```
Test list: <behaviours, each marked done or not>
Cycles:    <test name> — red: <how it failed> — green: <the change>   (one line each)
Refactors: <what was cleaned up, all on green>
Checks:    <the full-suite command and its result>
Not test-driven: <anything done without a red first, and why>
```
