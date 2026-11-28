# INVEST

A diagnostic, not a gate. Use it when an item passes the Definition of Ready
mechanically but still feels like it will go wrong.

## Independent

Can it ship without waiting on another item in the same sprint?

Dependent pairs are the usual cause of a sprint that finishes at 80%: item B
was blocked for six days by item A, and nobody noticed until the review.

Fixes: merge the pair into one item; stub the dependency behind a flag; or
sequence them explicitly and put both in the same person's queue.

## Negotiable

Does the item describe an outcome, or a solution someone already picked?

"Add a Redis cache to the search endpoint" forecloses the conversation.
"Search results return in under 400 ms at p95" leaves the team free to find out
that the real cost was an N+1 query.

Fixes: move the implementation idea into a Notes line and write the outcome as
the story. Keep the idea — it is often right — but stop it masquerading as the
requirement.

## Valuable

Does someone outside the team notice when this ships?

If the only beneficiary is the team, that is fine, but say so: technical work
is legitimate and should be visible in the sprint as itself, not disguised as a
user story.

Fixes: name the beneficiary explicitly. "So that on-call stops being paged at
3am" is a real value statement.

## Estimable

Can the team put a number on it without a research spike first?

Inability to estimate is information: it means an unknown. The unknown is the
work, not the story.

Fixes: split off a time-boxed spike ("2 days: determine whether the provider
supports partial refunds") and leave the story unestimated until it returns.

## Small

Does it fit comfortably inside one sprint — with the review, the QA and the
deploy?

The practical test: could one person finish it in under half the sprint? If
only the whole team over the whole sprint can, it is an epic wearing a story's
clothes.

Fixes: see [splitting.md](splitting.md).

## Testable

Could someone who did not write it decide whether it passes?

"Improve performance", "make it more intuitive", "handle edge cases" are all
untestable. So is any criterion whose verification is "ask the author".

Fixes: replace the adjective with a number, a user-visible behaviour, or a
named case.
