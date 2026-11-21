# Splitting stories

Every split must produce slices that each ship something a user could notice.
Splitting by layer — "the API ticket" and "the UI ticket" — produces two items
that are each worthless alone and hides the integration risk in whichever one
lands second.

Try the patterns in this order. The first one that yields two or more
independently shippable slices wins; stop there.

## 1. Workflow steps

A multi-step flow is already a sequence of slices. Ship the first step
end-to-end, then the next.

> Checkout → *Slice 1:* card payment only, single item.
> *Slice 2:* multiple items. *Slice 3:* saved payment methods.

## 2. Business rule variations

One rule now, the exceptions later.

> Refunds → *Slice 1:* full refund inside 30 days.
> *Slice 2:* partial refunds. *Slice 3:* refunds past the window with approval.

## 3. Happy path first

Ship the path that works, then each failure path as its own slice. This is
legitimate only if the failure paths are tracked — an untracked failure path is
not a split, it is a bug you scheduled.

## 4. Data variations

One input type, one locale, one file format now; the others as slices.

> Import → *Slice 1:* CSV. *Slice 2:* XLSX. *Slice 3:* files over 50 MB.

## 5. Interface variations

The simplest usable interface first, the polished one later.

> *Slice 1:* a plain form that posts and reloads.
> *Slice 2:* inline validation and optimistic update.

## 6. Defer the non-functional requirement

Ship correct-and-slow, then make it fast — but only when slow is genuinely
usable, and with the performance slice in the same or next sprint.

## 7. Spike out the unknown

When the item cannot be split because nobody knows enough, the first slice is a
time-boxed spike whose deliverable is a written answer, not code.

## Splits that are not splits

- **By layer** (backend / frontend / database). Neither half ships.
- **By role** (the dev ticket, the QA ticket). That is a task breakdown; it
  belongs inside one item, not beside it.
- **By "part 1 / part 2"** with no independent value. Renaming an epic does not
  split it.
- **Under an hour.** Slices smaller than the ceremony around them cost more to
  track than to do. Merge them back.

## Check the result

For each slice, answer both:

1. Could this ship on its own, to real users, and be worth shipping?
2. Would the team estimate this lower than the original — meaningfully lower,
   not 8 → 5 → 5?

If a slice fails the first, it is a task. If every slice fails the second, the
original estimate was wrong rather than the item being too big.
