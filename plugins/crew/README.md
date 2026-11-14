# crew

The crew's workflow, owned by no role. The role plugins (developer, scrum-master,
designer, qa, devops, code-reviewer) each do their own step; this plugin holds
what connects them: the order of the steps, the Captain's gates, and the board
the tickets move on. Removing a role plugin removes only that role's commands,
never the workflow.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill (shared) | `crew-workflow` | Runs ticket work through the crew: each step through its crew command, no asking from In Definition to In approval, never a skipped column, stops at In approval, starts QA when the Captain moves a card to QA, stops at Ready for Merge. Only crew lists it. Source: `plugins/_shared/skills/` |
| Skill (shared) | `board-setup` | Create a GitHub Projects board with the crew's columns and the `skip_approval` label, linked to the repo. Only crew lists it. Source: `plugins/_shared/skills/` |
| Skill (shared) | `ticket-management` | The board scripts `board-setup` relies on (`board.py boards`). Source: `plugins/_shared/skills/` |
| Command | `/create-board` | Create the board a new project's tickets go on |
| Hook | `SessionStart`, `UserPromptSubmit` | See below |

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

## Starting QA when the Captain moves a card to QA

GitHub sends no event when a card moves on a user-owned board, so the same
script also runs on every prompt (`UserPromptSubmit`). It reads the crew
board's own cards in QA, by the board's ID (another board with the same title
is never read), filtered to QA and to this repository's open issues.

| When | What the session is told |
| --- | --- |
| Session start (also after compaction, `/clear` or resume) | Cards moved to QA that no earlier check reported: run `/qa:verify` on each, without asking |
| A prompt, at most once a minute | The same, for cards moved to QA since the last check |
| A card moved out of QA and back, even within one turn | Reported again: each card is keyed on when its Status was last set |
| No cached crew board, offline, without `gh`, or checked under a minute ago | Nothing. A prompt never looks the board up (a cached board ID is used whatever its age, so a long session keeps checking), and a check, failed or not, claims the minute before calling `gh`, so a prompt waits on at most one 5 s `gh` call a minute across sessions |

Only issue numbers are printed. QA starts on your next message after the move,
not while the session is idle. A card is reported once per move: if a session
ends before its QA finishes, ask for `/qa:verify #N` yourself. The QA state is
kept in `crew_qa.json`, apart from the board cache, and every cache file is
replaced atomically; a file another session is halfway through writing is left
alone rather than overwritten. After a check, cards are compared with the state
as it is then, so a card another session reported meanwhile is not reported
twice.

## Moving a merged ticket to Done

A merged PR puts its ticket in **Done**, whatever column its card is in. GitHub's
board automation only does that when the board's "Item closed" workflow is on and
the PR targeted the default branch, so the same check-ins also read the crew
board's cards that are not in Done (filtered on GitHub's side) and move to Done:

- an issue of this repository that a merged PR closes, whatever branch the PR targeted;
- a merged PR's own card.

| When | What happens |
| --- | --- |
| Session start, and a prompt at most once a minute | Up to 5 cards are moved (the rest on the next check); the session is told `crew: moved #N to Done` |
| A move fails, or the board has no Done column | The session is told to move the card to Done itself, without asking |
| A card already in Done, or with no merged PR | Nothing |
| Offline, without `gh`, or a failed check | Nothing |

The last check time is kept in `crew_done.json`. Moving is idempotent, so two
sessions checking at once do no harm.

## Harnesses

- **Claude Code** takes everything, including the hook.
- Other harnesses take the skills and the command; there is no hook, so a
  session there starts `crew-workflow` only when asked for ticket work.
