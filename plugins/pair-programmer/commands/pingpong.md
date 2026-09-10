---
description: Play the current TDD ping-pong turn — write the failing test, make it pass, or refactor — and hand over when the suite allows.
argument_hint: "[optional: the behaviour the next test should pin down]"
model: sonnet
allowed_tools: Bash Read Edit Write Grep Glob
---

Take the ping-pong turn: {{ARGS}}

Follow the `tdd-ping-pong` skill.

1. Find out whose turn it is and what it owes:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/tdd-ping-pong/scripts/tdd.py" turn
   ```

   If the session is not in ping-pong mode, say so and offer `/pair` rather than
   improvising a cycle.

2. Play the turn, and only that turn:
   - **write-failing-test** — one test, about behaviour, failing for the reason
     you intend. Touch no production code beyond the smallest stub that turns a
     `NameError` into an assertion failure.
   - **make-it-pass** — the smallest code that goes green. No branch that no test
     asked for. Never edit the test to meet the code; if the test is wrong, say
     so and hand back.
   - **refactor** — green the whole way. If it goes red, revert to the last green
     rather than fixing forward.

3. Try to hand over:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/tdd-ping-pong/scripts/tdd.py" advance
   ```

   It runs the suite and refuses if the state is wrong. Read the refusal and act
   on it — an `ERRORED` suite means the run never reached a verdict (an import
   error, or zero tests collected), which is neither red nor progress. Do not
   set the turn by hand to get past a refusal.

4. When the turn is handed over, say in one line what the other side now owes,
   and record anything decided along the way:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" decide "<what>" --because "<why>"
   ```
