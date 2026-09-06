# job-hunter

A job or contract search run as a pipeline instead of a pile of open tabs. The
plugin exists to make three things cheap: killing a posting that was never going
to work, writing the one that was, and never losing an application to silence.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `opportunity-triage` | Score a posting against the profile; pursue, skip or unclear, with the reason |
| Skill | `application-tailoring` | Write the bid, cover letter or CV variant for one specific posting |
| Skill | `application-pipeline` | Track every opportunity through its stages; say what is due |
| Command | `/triage` | Score a posting and record it if it survives |
| Command | `/tailor` | Draft the application for one posting |
| Command | `/pipeline` | What needs chasing today; record stage changes |
| Agent | `screener` | Judges one posting in a fresh context, so a shortlist does not get progressively more agreeable |
| Hook | `SessionStart` | Says what is overdue — and stays silent when nothing is |
| MCP | `job-hunter` | Dependency-free stdio server: `pipeline_status`, `score_fit`, `hunt_playbook` |

## Setup

Two files in the user's own repo, both theirs to edit:

```bash
python skills/opportunity-triage/scripts/fit.py --init        # .jobhunt/profile.json
python skills/application-pipeline/scripts/pipeline.py init   # .jobhunt/pipeline.md
```

`profile.json` declares titles, must-haves, nice-to-haves, markets, tracks, rate
floor and deal-breakers. Nothing in the plugin is personalised — the profile is,
which is why the skills refuse to score anything before one exists rather than
guessing at the user's requirements.

## The scripts

```bash
# score a posting: 0 pursue, 1 skip, 3 unclear, 2 unusable
python skills/opportunity-triage/scripts/fit.py posting.txt
cat posting.txt | python skills/opportunity-triage/scripts/fit.py - --json

# what needs action today: exits 1 when something does
python skills/application-pipeline/scripts/pipeline.py due
python skills/application-pipeline/scripts/pipeline.py add --company Acme \
  --role "Senior AI Engineer" --track contract --next "send proposal" --due 2026-09-10
python skills/application-pipeline/scripts/pipeline.py move Acme --to screening
```

`fit.py` is a rule engine over terms the user declared, not a judgement. It
reports coverage and gaps so the model decides from a list of what is actually
missing rather than a general impression — and *unclear* is a distinct answer
from *bad fit*, because a posting that never says whether it is remote needs a
question, not a score.

`pipeline.py` backs the file up before every write and refuses a table it cannot
parse. Dates are ISO and only ever come from the user; "next week" is not a due
date this script will invent.

## Where the rules live

`due_report` in `pipeline.py` decides what "overdue", "stale" and "needs a next
action" mean. The SessionStart hook and the MCP server both import it rather
than each deciding for themselves, so the hook can never disagree with `/pipeline`.

## What it will not do

- **Send anything.** Drafts go to the user; the user sends them.
- **Invent evidence.** A tailored application with a plausible metric nobody
  verified is the worst thing this plugin could produce, so the tailoring skill
  asks instead of filling in.
- **Estimate your odds.** Triage decides whether a posting is worth the next two
  hours. That is all it claims.

## Try it

```bash
python -m tools.apkit test --plugin job-hunter

echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/job-hunter/mcp/server.py
```

## Install it

```bash
python -m tools.apkit build --plugin job-hunter
python -m tools.apkit install job-hunter --target claude-code --scope user
python -m tools.apkit install job-hunter --target agents --scope project --into ~/search
```

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes skills, commands and agents; no hooks.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; `screener` is
  emitted as a skill, so the method survives but the delegation does not.
- **Generic `.agents/skills`** takes skills only — and both scripts live under
  their skills, so `fit.py` and `pipeline.py` travel with them.
