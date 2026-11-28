# The change plan

A plan exists to make disagreement cheap. Five lines in the conversation cost a
turn; the same disagreement discovered in a finished diff costs the diff.

## Format

```
Goal:      one sentence, the user-visible outcome
Slices:    2-5 steps, each independently verifiable
Contracts: what changes shape (API, schema, event, config) and who consumes it
Risk:      what could break that the tests would not catch
Verify:    the exact commands that will prove it
```

Worked example:

```
Goal:      users can export their invoice history as CSV from the billing page.
Slices:    1. `buildInvoiceCsv(invoices)` + unit tests for empty, one, many, unicode
           2. GET /api/invoices/export route, auth-scoped to the caller's org
           3. Export button + loading and error states on BillingPage
Contracts: new public route; no schema change; response is text/csv, not JSON
Risk:      an org with 50k invoices streams into memory — cap at 10k rows, page after
Verify:    pnpm run test, pnpm run typecheck, manual: export as a user with 0 invoices
```

## Slicing rules

A slice is right-sized when it is **independently verifiable**: after it, the
tests pass and you can name what is now true that was not true before.

- **Cut along seams, not along file types.** "Model, then service, then
  controller" leaves every slice unverifiable until the last one. "One field
  end to end, then the next" is verifiable at every step.
- **The first slice should be the riskiest unknown.** If the third-party API
  does not return what you assumed, learn it in slice one, not after you have
  built the UI on top of it.
- **Pure logic first, wiring second.** A function that transforms data is
  testable without a server; the plumbing around it usually needs no test of
  its own once the logic is proven.
- **Migrations are their own slice, always**, and they ship before the code
  that requires them — see expand-contract below.
- **If a slice cannot be described in one line, it is two slices.**

## Contract changes

Anything another program depends on: a route, a payload field, a database
column, a queue message, a config key, an exported function, a CSS class other
teams select on.

For each one, the plan must answer:

1. Who consumes it today? (`callers.py` from the `safe-refactoring` skill, or
   grep the consuming repos.)
2. Does the change break them, or only add?
3. If it breaks them: is the consumer updated in this change, or does this need
   to be split across deploys?

**Expand-contract** is the split that keeps a system deployable at every step:

1. *Expand* — add the new column, field, or route. Nothing reads it yet.
2. *Migrate* — write both, read the old one. Backfill.
3. *Switch* — read the new one. Old one still written.
4. *Contract* — stop writing the old one, then drop it. A separate deploy,
   after the switch has been live long enough to trust.

A plan that puts a migration and the code requiring it in one deploy has a
window where the running pods hit a schema they do not know. Say so in Risk.

## When to skip the plan

A one-slice change with no contract change and an obvious test does not need a
written plan. Say what you are about to do in a sentence and do it. The plan is
for changes where being wrong is expensive, not for ceremony.
