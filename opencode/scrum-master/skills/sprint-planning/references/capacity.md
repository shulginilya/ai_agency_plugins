# Capacity

Two numbers answer "how much fits". Use whichever the team has evidence for.

## Velocity (preferred, after three sprints)

Sum the points completed — met the Definition of Done, no partial credit — in
each of the last three to five sprints.

```
velocity: 21, 25, 19  →  mean 21.7, range 19-25
commit:   19-22 points
```

Plan at or slightly below the mean, never above the maximum. The maximum was
one sprint where everything went right; planning to it means planning for
everything to go right again.

Adjust the range for known differences in the coming sprint: two people out for
half of it is roughly a 25% cut, not a rounding error.

## Focused person-days (a new team, or a changed one)

```
gross      = people x sprint working days
net        = gross - planned absence - holidays - on-call days
capacity   = net x focus factor
```

**Focus factor** is the fraction of a working day that reaches sprint items.
The rest is standups, reviews, interviews, support, the meeting about the
meeting.

| Situation | Focus factor |
| --- | --- |
| Dedicated team, few meetings, no support duty | 0.75 - 0.80 |
| Typical product team | 0.65 - 0.70 |
| Team carrying support or on-call rotation | 0.50 - 0.60 |
| Team split across two products | 0.40 - 0.50 |

Do not start above 0.7. Every team that starts at 0.8 discovers the true number
by missing two sprints first.

Once three sprints of history exist, switch to velocity and use person-days
only to sanity-check a sprint with unusual absence.

## What to subtract before anything else

- Public holidays and planned leave, per person, in days.
- On-call: an on-call week is roughly half a person.
- Ceremonies: planning, review and retro together are about half a day per
  person per two-week sprint.
- The release, if the team runs it, and the day after it.
- Onboarding: a new joiner contributes near zero for their first sprint and
  costs their mentor about 20%.

## The 80% rule

Commit to at most 80% of the capacity number. The remaining 20% absorbs
interruptions, the estimate that was wrong, and the bug that ships on day 6.

Teams that commit to 100% do not deliver 100%; they deliver about 75% and lose
the ability to predict. The 80% is not caution — it is the only way the number
means anything.

## Reading a miss

A sprint that finishes at 60% is data, not failure. Look, in this order, at:

1. Scope added mid-sprint without anything removed.
2. Items that were not actually ready when selected.
3. An estimate that was wrong by more than 2x — which is a refinement problem.
4. Absence nobody subtracted.

Only after all four come up empty is the answer "the team was slower".
