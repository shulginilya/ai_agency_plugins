---
name: tdd-ping-pong
description: Runs test-driven pairing where the turns alternate — one side writes a failing test, the other writes the smallest code that passes it, then refactors and hands back — with the test suite, not either partner, deciding when a turn is over. Use when the user wants to pair with TDD, asks for ping-pong pairing, wants tests written first, or wants you to write the test while they implement it.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# TDD ping-pong

One side writes a failing test. The other writes the smallest thing that passes
it, refactors, and writes the next failing test. The keyboard changes hands
every turn.

What makes it worth the ceremony is that neither partner decides when a turn is
over — the suite does. That removes the argument, and it removes the thing TDD
usually degenerates into: writing the code first and the test afterwards, with
the test shaped to fit what was written.

## The cycle

```
write-failing-test  ->  make-it-pass  ->  refactor  ->  write-failing-test
      needs RED            needs GREEN     needs GREEN
```

Each turn hands over only when the suite is in the state that turn owes.

```bash
python scripts/tdd.py turn        # whose turn, and what it needs
python scripts/tdd.py state       # run the suite, name the state
python scripts/tdd.py advance     # hand over, if the state allows it
```

`advance` runs the suite and refuses when the state is wrong, with the reason.
Do not work around a refusal by setting the turn by hand — the refusals are the
skill.

## Four states, not two

A suite that "passes or fails" is the abstraction that lets a ping-pong session
rot, because both of the interesting states hide inside "passes" and "fails".

| State | What it means | Why it is its own answer |
| --- | --- | --- |
| `GREEN` | every test passed | |
| `RED` | a test failed | An assertion failed. This is what a new test owes. |
| `ERRORED` | the suite never reached a verdict | An import error, a collection error, a timeout — **or a run that collected zero tests**. |
| `UNUSABLE` | the command did not run | No test command declared, or it does not exist. |

`ERRORED` is the state that matters most and the one a two-state model gets
wrong in both directions:

- **A green with nothing behind it.** The new test file is not being collected —
  wrong directory, wrong name, a missing `__init__.py` — so the suite passes and
  the turn appears finished. The code written next is driven by nothing at all.
- **An error mistaken for red.** A typo makes the module fail to import. The
  suite is not green, so it looks like a legitimate red, and the "implementation"
  that follows is really just fixing the typo. Nothing was driven by a test.

When the state is `ERRORED`, fix the suite before continuing. Do not treat it as
red and do not treat it as progress.

## Turn discipline

**Writing the failing test:** write one, and watch it fail for the right reason.
Read the failure message — a test that fails because of a `NameError` has not
yet specified anything. See
[references/ping-pong.md](references/ping-pong.md) for what a good failing test
looks like and the specific ways this turn goes wrong.

**Making it pass:** the smallest code that turns it green, and no more. If you
find yourself writing a branch no test asked for, stop — that branch is the next
test, not this turn's code. Never edit the test to meet the code; if the test is
wrong, say so and hand back rather than quietly adjusting it.

**Refactoring:** the suite stays green the whole way. A refactor that goes red is
not a refactor that needs fixing forward — revert to the last green and try a
smaller move.

The `PostToolUse` hook this plugin ships watches for the two edits that break
turn discipline: production code touched while it is the test turn, and test
files touched while it is the implementation turn. It says so; it never blocks.

## Starting

Ping-pong needs a declared test command, because the gate has nothing to check
without one:

```bash
python ../pair-session/scripts/session.py start \
  --goal "retry the webhook safely" --scope src/webhooks --scope tests/webhooks \
  --test-command "pytest -q tests/webhooks" --mode pingpong
```

Scope the test command as tightly as the work: a full-suite run per turn is a
cycle nobody keeps up, and the first thing to be abandoned will be the running
of it. Widen it before handing off, not during.

## Ending a session

Stop on green, with the next failing test named but not written. It is the
cheapest place to resume from and the only one where the code and the tests agree
about what exists. Record it as the next step in the `pair-session` journal.
