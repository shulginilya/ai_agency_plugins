---
description: Build one behaviour, or a short list of them, test-first — red, green, refactor — with each step checked by running the tests.
argument-hint: "[the behaviour to build, a ticket's acceptance criteria, or a bug to reproduce]"
model: claude-opus-5-5
effort: high
allowed-tools: Bash Read Edit Write Grep Glob
---

Test-drive: $ARGUMENTS

Follow the `test-driven-development` skill.

1. Find the test command: `python "${CLAUDE_PLUGIN_ROOT}/skills/test-driven-development/scripts/tdd.py" detect`,
   or read how the repo runs its tests. Scope it to the tests in play, as in
   the skill's `references/cycle.md`. If the repo has no test runner, stop and
   say so.
2. Write the test list from the arguments: one behaviour per line, unhappy
   paths included. Show it, then start with the simplest item.
3. For each item:
   - **Red:** write one test, then run
     `python "${CLAUDE_PLUGIN_ROOT}/skills/test-driven-development/scripts/tdd.py" check --cmd "<scoped>" --expect red`.
     The new test must be the one failing, on its assertion. If it fails on an
     exception, add a stub and run it again.
   - **Green:** write the smallest code, then run `--expect green`. Never edit
     the test to meet the code.
   - **Refactor:** on green, one move at a time, running `--expect green` after
     each. Revert any move that goes red.
4. Run the repo's full suite and checks at the end, not just the scoped
   command.
5. Report in the skill's format: test list, cycles, refactors, checks, and
   anything not test-driven.
