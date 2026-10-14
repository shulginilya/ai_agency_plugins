# scrum-master

Backlog refinement and sprint planning, against GitHub Issues. It covers the
two ceremonies where an agent is actually useful — turning vague requests into
startable work, and deciding how much of it fits — and deliberately leaves
standups and retros alone.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `backlog-refinement` | Definition of Ready, the refinement loop, the issue template |
| Skill | `sprint-planning` | Capacity first, goal second, selection third, then the pre-flight checks |
| Skill (shared) | `ticket-management` | Create, batch, edit, close and delete GitHub issues; board cards. Source: `plugins/_shared/skills/` |
| Command | `/refine` | Refine one item into a ready story |
| Command | `/plan-sprint` | Build a sprint plan from the ready backlog |
| Command | `/backlog-health` | How much of the backlog is plannable, and what is missing |
| Agent | `story-splitter` | Splits one oversized item into vertical slices, in a fresh context |
| Hook | `SessionStart` | Prints the active milestone and its open issues, once |
| MCP | `scrum-master` | `backlog`, `readiness_check`, `scrum_checklist` |

The readiness rules live in exactly one place —
`skills/backlog-refinement/scripts/ready.py` — and the MCP server imports them
from there rather than restating them, so the CLI and the tool cannot drift.

## GitHub is the backlog

Every read goes through `gh`. Nothing writes to GitHub without the user saying
so: the commands propose `gh issue edit` / `gh api` calls and stop. When `gh`
is missing, unauthenticated, or not pointed at a repository, the scripts exit 2
with a sentence explaining which, and `--from-json` accepts a pasted
`gh issue list --json ...` payload instead.

## Try it

```bash
# what is not ready to plan
python plugins/scrum-master/skills/backlog-refinement/scripts/backlog.py --not-ready

# check one story
gh issue view 42 --json body --jq .body \
  | python plugins/scrum-master/skills/backlog-refinement/scripts/ready.py --title "Partial refunds"

# how much fits
python plugins/scrum-master/skills/sprint-planning/scripts/capacity.py \
  --people 4 --days 10 --absence "ilya:3" --velocity 21,25,19

# talk to the MCP server directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/scrum-master/mcp/server.py

# run its tests
python -m tools.apkit test --plugin scrum-master
```

## Install it

```bash
python -m tools.apkit build --plugin scrum-master
python -m tools.apkit install scrum-master --target claude-code --scope user
python -m tools.apkit install scrum-master --target agents --scope project --into ~/work/my-repo
```

`dist/<target>/scrum-master/INSTALL.md` says what each target got, what it did
not get, and why.

## What degrades where

- **Claude Code** takes everything, including the `SessionStart` hook.
- **OpenCode** takes skills, commands and the agent; no hooks.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; `story-splitter`
  is emitted as a skill, so the method survives but the delegation does not;
  no hooks.
- **Generic `.agents/skills`** takes skills only — one install covers Codex,
  Cursor, Gemini CLI and OpenCode at once. The scripts travel with the skills,
  so `backlog.py`, `ready.py` and `capacity.py` work everywhere; the MCP server
  and the hook do not.
