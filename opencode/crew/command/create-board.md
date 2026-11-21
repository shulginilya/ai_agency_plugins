---
description: Create a GitHub Projects board for this repository with the team's columns, linked and ready for a backlog.
model: claude-sonnet-5-5
---

Create a board: $ARGUMENTS

Follow the `board-setup` skill:

1. Check whether a board already exists with
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/crew/skills/ticket-management/scripts/board.py boards`. If an open one
   already holds this repository's issues, say so and stop unless the user still
   wants a new one.
2. Settle the title and the columns. The default is In Definition, Backlog, Ready,
   In progress, In review, In approval, QA, Ready for Merge, Done. Show the plan with
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/crew/skills/board-setup/scripts/create_board.py --title "<title>" --dry-run`.
3. Wait for the user's yes. Under a crew brief, go ahead only if the brief asks
   for a board.
4. Create it with the same command without `--dry-run`, then report the board's
   number, URL, columns and linked repository in the skill's format.
