---
name: safe-refactoring
description: Changes the shape of existing code without changing its behaviour — pin the current behaviour in tests, find every caller, then apply small mechanical moves that keep the tree green at each step. Use when asked to refactor, clean up, restructure, extract, rename, split or simplify existing code, remove duplication, pay down technical debt, or make room for a feature before adding it.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Safe refactoring

A refactor changes structure and nothing else. The moment observable behaviour
changes, it is a feature or a fix, and it belongs in its own commit with its own
tests. Mixing the two produces a diff nobody can review and nobody can revert.

## Before the first edit

**1. Name the reason.** "Make room for the new payment provider", "this
function has nine branches and the bug we just fixed was in branch seven".
A refactor without a reason is churn — it costs review time and rebases and
buys nothing. If you cannot name the reason, stop.

**2. Pin the behaviour.** You cannot preserve what you have not captured.

- Tests exist and cover the code → run them, confirm green, and note the
  coverage gap you are about to work inside.
- Tests do not exist → write **characterization tests** first: assert what the
  code does today, including behaviour that looks wrong. Do not fix it yet;
  a surprising assertion is documentation, and the fix is a separate change.
- Behaviour is genuinely untestable at this seam → introduce the seam first
  (see [references/refactoring-moves.md](references/refactoring-moves.md)),
  then pin, then refactor.

**3. Find every caller.**

```bash
python scripts/callers.py parseConfig
python scripts/callers.py UserRepository --root src --json
```

Then look where the script cannot: dynamic dispatch, string-keyed lookups,
reflection, DI containers, templates, serialized data holding class names,
other repositories, public API consumers you do not control. If the symbol is
exported from a published package, it has callers you cannot grep, and the
rename becomes an expand-contract migration rather than a rename.

## The loop

One move, then green, then commit. Every time.

```
pick the smallest move  ->  apply it mechanically  ->  run the tests
     ^                                                      |
     +--------------  green: commit  ----------------------+
                      red: revert, take a smaller step
```

- **Revert, do not debug.** If the tests go red after a mechanical move, the
  move was wrong or too big. Undo it and take a smaller one — debugging forward
  is how a refactor turns into a rewrite.
- **Never refactor on red.** Failing tests before you start means you are
  changing behaviour, not structure. Fix or quarantine them first.
- **Automate what the tool can do.** The IDE's rename and extract are exact;
  your search-and-replace is not. Where you must do it by hand, change one call
  site at a time.
- **Commit each green step separately** with a conventional-commit `refactor:`
  message. A ten-step refactor in one commit is a ten-step revert.

The mechanical steps for each common move — extract function, inline, rename
across call sites, introduce a seam, replace a conditional with dispatch,
split a module, parallel change — are in
[references/refactoring-moves.md](references/refactoring-moves.md).

## Knowing when to stop

- **The reason is satisfied.** The feature now fits. Stop. The rest of the mess
  is not this change's problem.
- **The diff outgrew the reason.** If a refactor to add one field has touched
  forty files, revert and find a narrower seam.
- **You are rewriting.** If the "refactored" code no longer maps step by step
  to what was there, the tests are no longer proof of anything. Say plainly
  that this is a rewrite and needs its own plan and its own review.
- **Leave the campsite tidy, not renovated.** Fixing the thing you touched is
  good. Fixing everything you saw is a different pull request.

## Reporting

```
Refactor: <what changed shape, one sentence>
Reason:   <what this makes possible or cheaper>
Behaviour: unchanged — <the tests that prove it, and that they passed before and after>
Call sites: <n> updated across <n> files (<any that could not be found by search>)
Follow-up: <anything deliberately left alone>
```

If any behaviour did change — even an error message, a log line, or an
ordering — say so explicitly under its own heading. Silent behaviour changes
inside a refactor are the reason people distrust refactors.
