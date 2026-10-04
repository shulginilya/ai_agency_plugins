# job-hunter

A job or contract search run as a pipeline instead of a pile of open tabs. The
plugin exists to make four things cheap: killing a posting that was never going
to work, showing the projects that prove you can do the one that was, writing
that application, and never losing it to silence.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `platform-search` | Search Upwork, Arc or Contra from the profile; drop seen, below-floor and re-posted jobs; return a screened shortlist |
| Skill | `opportunity-triage` | Score a posting against the profile; pursue, skip or unclear, with the reason |
| Skill | `portfolio-case-study` | Describe one project for a portfolio, CV or platform profile from its codebase or live app — facts only |
| Skill | `application-tailoring` | Write the bid, cover letter or CV variant for one specific posting |
| Skill | `application-pipeline` | Track every opportunity through its stages; say what is due |
| Command | `/search` | Search one platform (or all) and list the best — never applies |
| Command | `/triage` | Score a posting and record it if it survives |
| Command | `/portfolio` | Write a portfolio entry from a local project folder, git URL or web app URL — or a URL plus `--path <folder>` |
| Command | `/tailor` | Draft the application for one posting |
| Command | `/pipeline` | What needs chasing today; record stage changes |
| Agent | `screener` | Judges one posting in a fresh context, so a shortlist does not get progressively more agreeable |
| Agent | `project-analyst` | Reads a large codebase or a live app in a fresh context and returns a sourced facts sheet |
| Hook | `SessionStart` | Says what is overdue — and stays silent when nothing is |
| MCP | `job-hunter` | Dependency-free stdio server: `pipeline_status`, `score_fit`, `project_facts`, `hunt_playbook` (incl. platform references) |

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

```bash
# facts about a project before writing it up: 0 usable, 3 thin, 2 unusable
python skills/portfolio-case-study/scripts/project_facts.py ~/code/my-app --author "Ilya"
python skills/portfolio-case-study/scripts/project_facts.py --page saved_home.html --json
```

`project_facts.py` never describes a project. It reports what the manifests,
files and git history prove — each technology with the file it came from — and
lists what only the user can supply: role, outcomes, confidentiality. *Thin*
means something decisive is missing (nothing says what the project is, or none
of the commits are the user's). Entries land in `.jobhunt/portfolio/`, where
`/tailor` picks them up as evidence.

```bash
# search a platform: plan from the profile, filter what was found, record the run
python skills/platform-search/scripts/search_log.py plan upwork
python skills/platform-search/scripts/search_log.py filter upwork found.json > filtered.json  # 0 kept, 1 none, 2 unusable
python skills/platform-search/scripts/search_log.py record upwork filtered.json
```

`search_log.py` does not search — the model does, through the platform's
connector, alert emails, public board or a signed-in browser, as
`references/<name>.md` describes. The script owns what must not
depend on judgement: the queries built from the profile, the real rate floor
(Upwork's own filter only checks that ranges overlap), postings already seen in
an earlier run, and a client re-posting the same job. Runs are written to
`.jobhunt/searches/<date>-<platform>.md`; `seen.json` beside them is backed up
before every write and never overwritten when it cannot be parsed.

## Where the rules live

`due_report` in `pipeline.py` decides what "overdue", "stale" and "needs a next
action" mean. The SessionStart hook and the MCP server both import it rather
than each deciding for themselves, so the hook can never disagree with `/pipeline`.

## What it will not do

- **Send anything.** Drafts go to the user; the user sends them. A search
  reads only — it never applies, bids, saves or messages.
- **Publish anything.** Portfolio entries are files; the user posts them.
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
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; `screener` and
  `project-analyst` are emitted as skills, so the method survives but the
  delegation does not.
- **Generic `.agents/skills`** takes skills only — and all four scripts live
  under their skills, so `fit.py`, `pipeline.py`, `project_facts.py` and
  `search_log.py` travel with them.
