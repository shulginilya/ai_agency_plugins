# /plan-sprint

Plan the next sprint — capacity, one goal, the issues that fit, and the risks that would sink it.

Plan the sprint described by: $ARGUMENTS

If that is empty, assume a two-week sprint starting on the next working day for
the team implied by the repository's recent contributors, and say what you
assumed.

Follow the `sprint-planning` skill, in its order:

1. **Capacity first.** Run `capacity.py`. Use velocity if three or more past
   sprints are known; otherwise focused person-days, and say which basis you
   used.
2. **Goal second.** One sentence, an outcome, survives losing the largest item.
3. **Selection third.** Only items that meet the Definition of Ready — run
   `backlog.py --not-ready` and exclude everything it lists. Carry-over first,
   then goal-serving items, to at most 80% of capacity.
4. **Report** in the skill's format: goal, capacity, the committed list with
   numbers and points, the nearest unselected items, and the risks.
5. Run the pre-flight checks at the end of the skill and state plainly if any
   of them fail.

Show the `gh` commands that would create the milestone and assign the issues.
Do not run them until the user says to.
