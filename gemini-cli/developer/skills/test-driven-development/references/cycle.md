# The cycle in practice

## A good failing test

- **One behaviour.** If its name needs "and", it's two tests.
- **Named for the behaviour:** `rejects_an_expired_token`, not `test_validate`.
- **Arrange, act, assert,** with the assertion stating the outcome a user of
  the code cares about. Avoid asserting how the code got there.
- **Fails on its assertion,** with a message that says what was expected and
  what came back. A test that fails with `NameError` or `undefined` hasn't
  specified anything yet: add a stub first.
- **Deterministic:** no real clock, network, randomness or ordering
  assumptions. Inject the clock, fake the boundary.
- **Fast enough to run on every step.** A slow test gets skipped.

## Getting to green

Three ways, from safest to fastest:

| Strategy | Use it when |
| --- | --- |
| **Fake it:** return the constant the test expects | the general shape isn't clear yet. The next test forces the real code. |
| **Triangulate:** add a second example that a constant can't satisfy | you aren't sure what generalisation the behaviour needs |
| **Obvious implementation:** write the real code | it's genuinely obvious. If it goes red, fall back to faking it. |

## Test doubles

- Fake or stub only at the **boundaries you don't own**: the network, the
  database, the clock, the file system, a third-party SDK.
- Don't mock the code under test or its private collaborators. Those tests
  break on every refactor and prove nothing about behaviour.
- Prefer a small hand-written fake over a mock that asserts call order.

## Scoping the test command

Run only the tests in play during the cycle, and the full suite at the end.

| Runner | One file | One test |
| --- | --- | --- |
| pytest | `python -m pytest -q tests/test_cart.py` | `python -m pytest -q tests/test_cart.py::test_rejects_empty` or `-k rejects_empty` |
| unittest | `python -m unittest tests.test_cart` | `python -m unittest tests.test_cart.CartTest.test_rejects_empty` |
| node --test | `node --test test/cart.test.js` | `node --test --test-name-pattern="rejects empty" test/cart.test.js` |
| vitest | `npx vitest run src/cart.test.ts` | `npx vitest run src/cart.test.ts -t "rejects empty"` |
| jest | `npx jest src/cart.test.ts` | `npx jest src/cart.test.ts -t "rejects empty"` |
| go | `go test ./cart` | `go test ./cart -run TestRejectsEmpty` |
| cargo | `cargo test --test cart` | `cargo test rejects_empty` |
| dotnet | `dotnet test --filter FullyQualifiedName~CartTests` | `dotnet test --filter FullyQualifiedName~CartTests.RejectsEmpty` |

`tdd.py check` reports a run that collected nothing as ERRORED. A scoped
command that matches no test (a typo in `-k` or `-t`) is caught there, not
mistaken for green.

## Traps

- **Writing the code first, then a test shaped to fit it.** The test passes
  the first time it runs, and specifies only what the code already does.
- **A test list in your head.** Write it down. It is what keeps a cycle to
  one behaviour.
- **Big steps.** If green takes more than a few minutes, the test asks for
  too much. Revert, and write a smaller test.
- **Refactoring on red.** Two changes at once, and no way to tell which one
  broke it.
- **Skipping the refactor.** The duplication you leave is what makes the next
  test hard.
- **Keeping a test you never saw fail.** Break the code on purpose for a
  moment and watch it go red, or delete the test.
