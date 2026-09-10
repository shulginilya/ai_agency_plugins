# The turns, and how each one goes wrong

## Writing the failing test

A good failing test on this turn is:

- **one test**, not a suite. The partner owes the smallest code that passes it,
  and three tests at once is a specification handed over as a wall.
- **about behaviour**, not implementation. `assert retry_delay(3) == 8` says
  what the system does; `assert isinstance(policy, ExponentialBackoff)` says how
  it is built, and locks the partner out of every other way to build it.
- **failing for the reason you intend.** Run it and read the message. A
  `NameError: retry_delay is not defined` is a test that has not specified
  anything yet — the function does not exist, which you already knew. Write the
  smallest stub that makes the failure an assertion failure, then hand over.

### How this turn goes wrong

**Writing the test after peeking at the implementation you already have in
mind.** The test then describes the solution rather than the requirement, and
the partner has no room. If you know exactly what code should be written, you
are on the wrong turn.

**Testing three things in one.** The partner cannot make it pass in small steps,
so they write everything at once, and the cycle collapses into two people taking
long turns.

**Asserting on a message string.** `assert str(exc) == "invalid webhook id"`
fails on every rewording forever, and constrains nothing worth constraining.

**A test that passes when written.** Not a mistake to correct silently — say it
out loud. Either the behaviour already exists, in which case the interesting
test is a different one, or the test is not being collected, and that is a
problem with the session, not the test.

## Making it pass

The smallest code that turns the suite green. "Smallest" is meant literally:
returning a constant is a legitimate first pass, and the way to object to it is
to write the test that rules it out on your next turn.

### How this turn goes wrong

**Writing the branch no test asked for.** You can see the edge case coming and
you handle it. Now there is untested code in the tree, and the next test cannot
fail. If you can see it, name it as the next test and leave it.

**Editing the test to make it pass.** Sometimes the test really is wrong — the
expected value is a typo, the API it assumes was never agreed. Say so and hand
back. Fixing it yourself, mid-turn, is how a pair ends up with a suite that
asserts whatever the code happens to do.

**Refactoring on the way past.** Tempting, and it belongs to the next turn. Mixed
into this one, a green suite no longer tells you which change was responsible.

## Refactoring

Green the whole way through. Run the suite after each move, not at the end of
five.

### How this turn goes wrong

**Fixing forward when it goes red.** A refactor that broke something was a
rewrite. Revert to the last green and take a smaller step — the instinct to
debug your way back is the expensive one.

**Refactoring the tests and the code in the same move.** Then neither one is
holding the other still, and a green suite proves nothing.

**Skipping the turn.** The most commonly dropped turn, and dropping it is what
leaves ping-pong sessions with a tree full of the smallest thing that passed.

## Where the cycle actually breaks

Not on any of the above, usually. It breaks when the suite gets slow enough that
nobody runs it every turn, and then the turns stop being gated by anything.

Scope the test command to the work — one directory, one file — and widen it
before you hand off rather than during. A ten-second suite is a cycle people
keep; a four-minute suite is a cycle people abandon by lunchtime and then claim
to be following.
