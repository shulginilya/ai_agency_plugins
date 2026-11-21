# The sprint goal

One sentence naming an outcome the team can achieve in one sprint, which
someone outside the team would recognise as progress.

The goal exists to answer a question that comes up on day 6, every sprint:
*this new thing has appeared — does it go in, and what comes out?*

## Tests for a good goal

- **Losing the largest committed item does not kill it.** If it does, the goal
  is that item wearing a disguise.
- **It can be judged true or false at the review**, without reading the board.
- **It is one thing.** A goal joined by "and" is two goals; one of them is the
  real one.
- **It says why, not what.** "Merchants can issue partial refunds without
  contacting support" beats "finish the refunds epic".

## Shapes that work

> Reduce checkout abandonment by removing the forced-account step.

> Make search results return in under 400 ms at p95 for the top 100 queries.

> Give merchants self-service partial refunds, so support stops handling them.

> Prove whether the new provider can handle our peak volume, well enough to
> decide by the review.

That last one is a legitimate goal: a sprint whose outcome is a decision is a
sprint that produced something.

## Common failures

| Failure | Looks like | Why it hurts |
| --- | --- | --- |
| The list | "Finish #42, #47, #51" | Gives no basis for any mid-sprint tradeoff |
| The theme | "Improve the checkout experience" | Never false, so never useful |
| The epic name | "Sprint 12: Refunds" | Names a container, not an outcome |
| Two goals | "Ship refunds and migrate the queue" | The team silently picks one |
| Someone else's goal | "Support the marketing launch" | Nothing the team controls |

## When there is honestly no goal

Some sprints are maintenance, or four unrelated commitments the business needs.
Say that plainly — "this sprint has no single goal; it is four independent
commitments" — rather than inventing a theme.

An invented goal is worse than none: it gets used to justify decisions it was
never strong enough to make. But two sprints in a row without a goal is worth
raising: it usually means priorities are being set item by item rather than by
outcome.
