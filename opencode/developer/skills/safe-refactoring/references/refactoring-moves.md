# Refactoring moves

Each move is mechanical: a sequence you can follow without judgement, with a
green test run at the end. If a step needs a decision, it belongs in the plan,
not in the middle of the move.

## Extract function

1. Identify the block. It should have one purpose and a small set of inputs.
2. Copy it into a new function beside the original; do not delete anything yet.
3. Turn every variable the block reads into a parameter, and the values it
   produces into the return. If there are more than three parameters or more
   than one return value, the block is not a unit — pick a smaller one.
4. Replace the original block with a call. Run the tests.
5. Name it for what it produces, not how: `taxFor(order)`, not
   `calculateTaxLogic`.

Stop if the block mutates outer state in more than one place. Extract the
mutation first, or leave it alone.

## Inline

The mirror image, used when an indirection has stopped paying for itself:

1. Confirm the callee is called from few places (`callers.py`) and has no
   recursion.
2. Paste the body into each call site, substituting arguments. One site at a
   time, tests between each.
3. Delete the function only after the last call site is gone.

## Rename across call sites

1. `python scripts/callers.py <oldName>` — record the count and the files.
2. Prefer the language tooling's rename. If renaming by hand, go one file at a
   time and re-run the count after each.
3. Check the places search cannot see: string literals, dynamic property
   access, config, serialized data, docs, log-based dashboards and alerts.
4. If the symbol is exported publicly, do not rename in place — **parallel
   change**: add the new name as the implementation, make the old name a thin
   deprecated wrapper, migrate consumers, remove the old name in a later
   release.

## Introduce a seam

A seam is a place you can change behaviour without editing the code around it —
what makes untestable code testable.

1. Find the hard-coded dependency: a `new` in the middle of logic, a global
   clock, a direct HTTP or filesystem call, a singleton.
2. Lift it to a parameter with a default that preserves today's behaviour
   (`function chargeOrder(order, gateway = liveGateway)`).
3. Run the tests: nothing should change, since the default is the old value.
4. Now the test can pass a fake. Write the characterization test.

Constructor or parameter injection beats a mocking framework reaching into the
module — the framework hides the coupling instead of removing it.

## Replace conditional with dispatch

For a `switch`/`if-else` chain on a type or kind that has grown a third or
fourth branch and gets edited every time a case is added:

1. Pin every branch with a test first — one per branch, including the default.
2. Build a lookup keyed by the discriminator, values being the branch bodies as
   functions. Keep the chain in place, delegating to the lookup.
3. Run the tests, then delete the chain.
4. Keep an explicit unknown-key path. A silent `undefined` where the old
   `default:` threw is a behaviour change.

Do not do this for two branches. An `if/else` is clearer than a table.

## Split a module

1. Group the exports by what they actually depend on — not by what they are
   named. `callers.py` on each export tells you who wants what.
2. Move one group to the new module, leaving a re-export behind in the old one.
   Tests stay green because no import path changed yet.
3. Update importers in batches, tests between each batch.
4. Delete the re-exports once nothing points at them.

A cyclic import at step 2 means the split line is wrong: something in both
halves belongs to a third thing. Find it before continuing.

## Remove duplication — carefully

Three similar blocks are not automatically one abstraction. Before unifying:

- Do they change for the same reason? Two things that look alike but change for
  different reasons must stay apart; coupling them means every future change to
  one drags the other.
- Does unifying introduce a flag parameter? A boolean argument that selects
  behaviour usually means you merged two functions that should stay two.

Duplication is cheaper than the wrong abstraction. When unsure, wait for the
third or fourth occurrence to show you which parts really vary.

## Dead code

1. `callers.py` finds zero non-test references.
2. Check dynamic access, exports, entry points, scheduled jobs, and anything
   invoked by name from config.
3. Delete it — do not comment it out. Version control is the archive, and
   commented code rots invisibly.
