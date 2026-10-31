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
| Skill | `acceptance-testing` | Gate on the repo's checks, test on the ticket's review link (re-test on a new one), run every case with evidence, verdict accept / reject, comment, move the card |
| Skill | `bug-reporting` | Reproducible report: steps, expected vs actual, build, severity, evidence, what was ruled out |
| Skill (shared) | `ticket-management` | Create and edit GitHub issues; QA's tickets are labelled **QA testing**. Source: `plugins/_shared/skills/` |
| Skill (shared) | `preview-link` | The fallback when the ticket names no review link: a PR's preview from the Deployments API, used only when it was deployed from the PR's head commit (devops publishes it). Source: `plugins/_shared/skills/` |
| Command | `/plan` | Test plan for a ticket |
| Command | `/verify` | Verify a branch or PR against its ticket and give the verdict |
| Command | `/bug` | Write one bug report and file it, labelled **QA testing** |
| Agent | `acceptance-checker` | Judges each criterion in a fresh context, from the criteria and the running result only |

It creates and edits tickets, but never closes or deletes them. Every bug it
files carries the **QA testing** label, and it may append a test plan to a
ticket. Proposed criterion rewrites go to whoever owns the ticket.

It picks up only tickets in the **QA** column: code review and, unless the
ticket is labelled `skip_approval`, the Captain have approved them.
When it's done testing, it comments the verdict on the ticket and moves the
card: an **accept** to **Ready for Merge**, a **reject** back to **In
progress**, with the comment saying exactly what fails. If the board has no
Ready for Merge column, QA adds it after QA, keeping every other card
where it was. QA never blocks a ticket; when it can't check a criterion, the
verdict is reject and the comment suggests blocking, for the Captain to decide.

**Review links.** Any link shaped `<name>.<project_slug>.<review domain>` in
the ticket's description or comments is a review link, whatever the name is
(usually the branch). The review domain is the repo variable `REVIEW_DOMAIN`,
or the placeholder `review.com` until one is set. Devops' preview workflow
keeps one comment on the ticket, edited on every deploy. Its hidden marker
says which commit the link serves. QA picks the latest version like this:

1. **Newest wins.** The devops comment counts as new as of its last edit, and
   a pasted link as of when it was posted.
2. **Right build, or wait.** If the link serves an older commit than the PR's
   head, the new build hasn't landed: QA waits (`wait`) and never tests it.
3. **Re-test on change.** A different commit or a different link since QA's
   last verdict means every case runs again (`retest`). The same link and
   commit means nothing new (`up-to-date`).
4. **No link on the ticket:** the PR's preview (`preview-link`), else a local
   run.

The whole flow, devops to QA, is drawn in
[`../devops/docs/review-links.drawio`](../devops/docs/review-links.drawio).

There are no hooks, because a crew plugin's hooks run in every crewmate
session.

Three scripts, all standard-library Python:

- `skills/test-planning/scripts/criteria.py` pulls the acceptance criteria
  out of an issue (through `gh`) or a Markdown body, numbers them AC1, AC2, …,
  splits out Given/When/Then, and flags vague or unobservable criteria. It
  exits 2 when there are none.
- `skills/acceptance-testing/scripts/review_link.py` finds the newest review
  link on a ticket and the commit it serves (from the devops marker), compares
  them with the commit under test and QA's last verdict comment, and says
  `wait`, `test`, `retest`, `up-to-date` or `none`. `--wait` polls while the
  new build hasn't landed. It also lists the ticket's boards.
- `skills/acceptance-testing/scripts/qa_report.py` turns recorded results
  into the verdict and the ticket comment. Only when every criterion has a
  passing case with evidence and nothing failed is it **accept**. Anything
  else is **reject**: a failure, an uncovered criterion, or one that couldn't
  be checked (listed under "Suggest blocking"). A pass without evidence counts
  as not run. It exits 0 only on accept.

`references/case-design.md` is the checklist for choosing cases: inputs,
state, failure, regression, UI and accessibility, and what counts as
evidence.

## Try it

```bash
python plugins/qa/skills/test-planning/scripts/criteria.py --issue 52
python plugins/qa/skills/acceptance-testing/scripts/review_link.py --issue 52
python plugins/qa/skills/acceptance-testing/scripts/qa_report.py results.json --link https://52-feat-x.my-app.review.com
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
