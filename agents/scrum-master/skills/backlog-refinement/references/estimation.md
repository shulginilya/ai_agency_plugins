# Estimation

Estimates exist to decide how much to pull into a sprint and to expose
disagreement about what an item involves. They are not a commitment, a
performance metric, or a unit of time.

## Relative sizing

Estimate against a reference item the team already finished, not against hours.

1. Pick one small, well-understood, recently completed item. That is the 2.
2. For each new item ask only: bigger, smaller, or about the same?
3. Place it on the scale: 1, 2, 3, 5, 8, 13.

The scale is coarse on purpose. The gap between 5 and 8 is wide because the
team's ability to tell 6 from 7 is imaginary.

## What the numbers mean

| Points | Reading |
| --- | --- |
| 1 | Trivial. Known, isolated, no unknowns. Often not worth a ticket of its own. |
| 2 | Small. One clear change, the team has done this shape of work before. |
| 3 | Normal. A day or two of work for one person, some integration. |
| 5 | Substantial. Multiple files or surfaces, real testing, a review that takes thought. |
| 8 | Large. At the limit. Look hard for a split before accepting it. |
| 13 | Too big. Not an estimate — a signal to split or spike. Never commit a 13. |

## Running the estimate

- Estimate the whole item, including review, tests and deployment. Teams that
  estimate "the coding" then miss sprints have found the leak.
- Ask the two extremes to explain first. A 2-vs-8 spread is the most valuable
  thing that happens in refinement: one of them knows something.
- Re-estimate only when the item's scope changed, never because it took longer
  than expected. Adjusting estimates after the fact destroys the historical
  data velocity depends on.
- Do not estimate items nobody intends to start. It is inventory.

## Bugs and spikes

- **Bugs**: estimate the fix once it is diagnosed. Before diagnosis, a bug is a
  spike wearing a bug's clothes.
- **Spikes**: never given points — given a time box, in days, with a written
  deliverable. A spike that produces a decision has succeeded even if it
  produced no code.

## When the team cannot agree

Three rounds, then stop. If a 3 and an 8 survive three rounds of discussion,
the item has an unresolved question in it. Write the question down and take the
item out of the ready pile.

## Velocity

Velocity is the sum of points completed in a sprint, averaged over the last
three to five sprints. It is a planning input, nothing else.

- Never compare velocity between teams. Points are per-team by construction.
- Never set velocity as a target. It is trivially gamed by inflating estimates.
- Count only items that met the Definition of Done. Partial credit makes the
  average lie in exactly the direction that hurts.
