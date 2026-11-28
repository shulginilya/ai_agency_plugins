# /backlog-health

Report how much of the backlog is actually ready to plan, and what the top items are missing.

Assess the backlog scoped to: $ARGUMENTS

If that is empty, assess all open issues.

1. Run `python scripts/backlog.py --json` (add `--milestone` or `--label` when
   the argument names one).
2. Report, in this order:
   - how many open items, how many ready, and how many sprints of ready work
     that is at the team's recent velocity if it is known;
   - the top ten items by priority, each with its single most important gap;
   - the failure pattern across the backlog — if eight items all lack
     acceptance criteria, that is one problem, not eight.
3. Name the three items to refine next and why those three.

Do not rewrite anything. This command reports; `/refine` changes things.

If `backlog.py` exits 2, say what it reported (gh missing, not authenticated,
not a repository) and offer to work from `gh issue list` output the user pastes.
