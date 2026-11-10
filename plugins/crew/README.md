# crew

The crew's workflow, owned by no role. The role plugins (developer, scrum-master,
designer, qa, devops, code-reviewer) each do their own step; this plugin holds
what connects them: the order of the steps, the Captain's gates, and the board
the tickets move on. Removing a role plugin removes only that role's commands,
never the workflow.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill (shared) | `crew-workflow` | Runs ticket work through the crew: each step through its crew command, every ticket or board write shown first, never a skipped column, stops at In approval and Ready for Merge. Only crew lists it. Source: `plugins/_shared/skills/` |
| Skill (shared) | `board-setup` | Create a GitHub Projects board with the crew's columns and the `skip_approval` label, linked to the repo. Only crew lists it. Source: `plugins/_shared/skills/` |
| Skill (shared) | `ticket-management` | The board scripts `board-setup` relies on (`board.py boards`). Source: `plugins/_shared/skills/` |
| Command | `/create-board` | Create the board a new project's tickets go on |
| Hook | `SessionStart` | See below |

## The session-start hook

`scripts/crew_context.py` runs at every session start and is cached per
repository (a found board for 12 hours, "no board" for 10 minutes).

| Where the session starts | What the session is told |
| --- | --- |
| A GitHub repository whose board has the In approval and QA columns, and is linked to it or owned by its owner and holding its recent issues | One line: follow the `crew-workflow` skill for ticket work |
| A GitHub repository with no crew board | Ask the Captain in the first reply whether to create one and what to call it. Yes: `/crew:create-board <name>`, then `crew-workflow`. No: run the `--decline` command the line gives, and that repository is never asked again (`--forget` undoes it) |
| A repository the Captain declined | Nothing, until a crew board appears there |
| An unattended session (`CREW_UNATTENDED=1` set) | Never the question; still the crew-board line |
| Not a GitHub repository, offline, or without `gh` | Nothing |

A board found through the repository's issues counts only when the
repository's owner owns it, and every board title is cleaned before it is
printed, so nobody else's board can put text into a session.

## Harnesses

- **Claude Code** takes everything, including the hook.
- Other harnesses take the skills and the command; there is no hook, so a
  session there starts `crew-workflow` only when asked for ticket work.
