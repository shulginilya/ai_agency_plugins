---
name: sprint-planning
description: Builds a sprint plan from a refined backlog — one sprint goal, a capacity number that accounts for time off and focus factor, the set of GitHub issues that fits inside it, and the risks that would sink it. Use when the user asks to plan a sprint or iteration, decide what to commit to, work out capacity or velocity, set up or fill a milestone, or check whether a plan is realistic.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Sprint planning

A sprint plan is three things: a goal worth achieving, a number that says how
much fits, and a selection that respects both. Produce them in that order —
picking items first and inventing a goal afterwards is how teams end up with a
sprint that is a list.

## 1. Capacity before selection

```bash
python scripts/capacity.py --people 4 --days 10 --focus 0.7
python scripts/capacity.py --people 4 --days 10 --absence "ilya:3,ana:1" --velocity 21,25,19
```

The script reports gross person-days, net of absence, focus-adjusted capacity,
and — when past sprints are supplied — a commitment range from velocity.

Use the velocity range when the team has three or more comparable sprints
behind it. Use the person-day number only for a new team, and treat the first
three sprints' plans as guesses. Details and the arithmetic:
[references/capacity.md](references/capacity.md).

Subtract before you plan, not after: on-call, planned leave, the day of
interviews, the release, the all-hands. Capacity that ignores known
interruptions is a forecast that was wrong when it was written.

## 2. The sprint goal

One sentence. Names an outcome, not a list of tickets. If half the sprint were
cut, the goal is what you would protect.

Write it before selecting items, then use it to decide inclusion:
[references/sprint-goal.md](references/sprint-goal.md) has the tests and the
common failures.

## 3. Selection

Read what is available and what is actually ready:

```bash
python ../backlog-refinement/scripts/backlog.py --not-ready
gh issue list --state open --label ready --json number,title,labels,milestone
```

Then select in this order:

1. **Items that serve the goal**, highest priority first, until capacity is
   80% spent.
2. **Carry-over** from last sprint — placed first in the queue, not appended at
   the end. Work already started is the cheapest work available.
3. **The commitment the team already made** — a security fix, a compliance
   date, a promise to another team.
4. **Leave 20% unallocated.** Not as slack to be filled later: as the space
   interruptions, bug fixes and the estimate that was wrong will take. A sprint
   planned to 100% of capacity finishes below 80% of it.

Never select an item that is not ready. Never select a 13. Never select two
items where the second cannot start until the first finishes unless one person
owns both.

## 4. Write the plan down

```bash
gh api repos/:owner/:repo/milestones -f title="Sprint 12" -f due_on="2026-09-18T17:00:00Z" \
  -f description="Goal: <the sprint goal>"
gh issue edit 42 --milestone "Sprint 12"
```

Then report:

```
Sprint <n> — <start> to <end>
Goal: <one sentence>

Capacity: <N> points (velocity <a>/<b>/<c>, mean <m>) | <D> focused person-days
Committed: <sum> points across <k> issues

  #42  5  <title>
  #47  3  <title>
  ...

Not selected but ready: #51, #52  (nearest fit if something falls out)
Risks:
  - <the dependency, the unknown, the person who is out>
```

## 5. Before you call it planned

- Every selected item is ready by the Definition of Ready.
- The sum of estimates is at or under 80% of capacity.
- The goal survives losing the largest item.
- Every dependency between selected items is either eliminated or owned by one
  person.
- Someone can say what "done" means for the sprint, not just for each ticket.

If any of these fails, the plan is a wish. Say which one failed and what would
fix it — do not quietly plan a sprint you expect to miss.

## Mid-sprint

- **Scope added** displaces scope of equal size. Adding without removing is how
  the goal is lost.
- **An item turns out to be twice its estimate**: split it, ship the slice that
  serves the goal, return the rest to the backlog. Do not extend the sprint.
- **The goal becomes unreachable**: say so the day you know, not at the review.
  A sprint that is cancelled on day 4 costs 4 days; one that is missed on day
  10 costs 10 plus the trust.
