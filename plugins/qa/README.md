# qa

The crew's QA engineer. Before a change is built, it turns the ticket's
acceptance criteria into test cases and flags the criteria that can't be
tested. After it's built, it checks the change against every criterion with
evidence and gives a verdict by fixed rules. When something fails, it writes
the bug report a developer can reproduce on the first try.

Developer writes and runs the unit tests for its own code. QA checks that
the change does what the ticket promised, from the outside, including when
things go wrong.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `test-planning` | Criteria → cases (happy, edge and boundary, negative, regression, accessibility); flag untestable criteria |
| Skill | `acceptance-testing` | Gate on the repo's checks, run every case with evidence, verdict: accept / reject / blocked |
| Skill | `bug-reporting` | Reproducible report: steps, expected vs actual, build, severity, evidence, what was ruled out |
| Skill (shared) | `ticket-management` | Create and edit GitHub issues; QA's tickets are labelled **QA testing**. Source: `plugins/_shared/skills/` |
| Skill (shared) | `preview-link` | A PR's review link from the Deployments API, used only when it was deployed from the PR's head commit (devops publishes it). Source: `plugins/_shared/skills/` |
| Command | `/plan` | Test plan for a ticket |
| Command | `/verify` | Verify a branch or PR against its ticket and give the verdict |
| Command | `/bug` | Write one bug report and file it, labelled **QA testing** |
| Agent | `acceptance-checker` | Judges each criterion in a fresh context, from the criteria and the running result only |

It creates and edits tickets, but never closes or deletes them. Every bug it
files carries the **QA testing** label, and it may append a test plan to a
ticket. Proposed criterion rewrites go to whoever owns the ticket.

There are no hooks, because a crew plugin's hooks run in every crewmate
session.

Two scripts, both standard-library Python:

- `skills/test-planning/scripts/criteria.py` pulls the acceptance criteria
  out of an issue (through `gh`) or a Markdown body, numbers them AC1, AC2, …,
  splits out Given/When/Then, and flags vague or unobservable criteria. It
  exits 2 when there are none.
- `skills/acceptance-testing/scripts/qa_report.py` turns recorded results
  into the verdict. Any failure or uncovered criterion means **reject**. A
  criterion whose cases were all blocked or skipped means **blocked**. Only
  when every criterion has a passing case with evidence and nothing failed
  is it **accept**. A pass without evidence counts as not run. It exits 0
  only on accept.

`references/case-design.md` is the checklist for choosing cases: inputs,
state, failure, regression, UI and accessibility, and what counts as
evidence.

## Try it

```bash
python plugins/qa/skills/test-planning/scripts/criteria.py --issue 52
python plugins/qa/skills/acceptance-testing/scripts/qa_report.py results.json
python -m tools.apkit test --plugin qa
```

## Install it

It's a crew plugin: `integrations/firstmate/deploy.sh --with-plugins`
installs it with the others.

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes the skills, commands and the `acceptance-checker` agent.
- **Codex CLI, Cursor, Gemini CLI** take the skills and commands.
  `acceptance-checker` becomes a skill, so the checks survive but the fresh
  context doesn't. Run it in a new session.
- **Generic `.agents/skills`** takes the skills only. Each skill carries its
  own script.
