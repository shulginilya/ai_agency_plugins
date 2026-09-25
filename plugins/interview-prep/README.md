# interview-prep

Preparation aimed at a specific loop, not at interviews in general. The plugin
exists to make four things cheap: knowing which rounds you will actually sit,
practising them against someone willing to fail you, having the stories ready
before the question arrives, and never forgetting what a real round asked.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `loop-mapping` | Turn a description, Notion page or notes into the loop it implies and a risk-ranked plan |
| Skill | `mock-interview` | Run a round for real — one question at a time — then grade it against a rubric |
| Skill | `story-bank` | Pull STAR stories out of the user's own history; check coverage and thinness |
| Skill | `prep-tracker` | Every loop's rounds, dates, prep items, mock results and debriefs |
| Command | `/prep` | Map a role into a loop and a dated plan |
| Command | `/mock` | Run and grade one mock round |
| Command | `/story` | Build, review or check the story bank |
| Command | `/debrief` | Capture what a real round asked, while it is still verbatim |
| Command | `/readiness` | What the prep needs today |
| Agent | `interviewer` | Writes the question ladder from the description alone, never having seen the prep plan |
| Agent | `grader` | Grades a transcript without knowing what the candidate meant to say |
| Hook | `SessionStart` | Says what is due — and stays silent when nothing is |
| MCP | `interview-prep` | Dependency-free stdio server: `prep_status`, `scan_jd`, `story_coverage`, `interview_playbook` |

## Setup

Two files in the user's own repo, both theirs to edit:

```bash
python skills/prep-tracker/scripts/prep.py init      # .interview/state.json
python skills/story-bank/scripts/stories.py init     # .interview/stories.json
```

Nothing in the plugin is personalised. The state file and the story bank are —
which is why the skills interview the user for material rather than writing
plausible stories on their behalf.

## The scripts

```bash
# what a description says the interview will test: 0 mapped, 1 thin, 3 unclear, 2 unusable
python skills/loop-mapping/scripts/jd_scan.py .interview/jd/acme.txt
cat jd.txt | python skills/loop-mapping/scripts/jd_scan.py - --json

# the loop, the plan, the mocks, the debriefs
python skills/prep-tracker/scripts/prep.py add --company Acme --role "Senior AI Engineer" \
  --rounds recruiter-screen,live-coding,system-design,behavioral
python skills/prep-tracker/scripts/prep.py status     # 0 clear, 1 action, 3 undeclared, 2 unusable
python skills/prep-tracker/scripts/prep.py render     # .interview/brief.md

# the story bank: 0 covered, 1 gaps, 3 thin, 2 unusable
python skills/story-bank/scripts/stories.py check
```

`jd_scan.py` is an extractor over declared terms, not a judgement — and
*unclear* is a distinct answer from *thin*, because a description that says
nothing about its process needs a question to the recruiter, not a study plan.

`prep.py` owns `.interview/state.json`; `.interview/brief.md` is rendered from
it one way only. Every write backs the file up first and refuses a JSON file
that is not an interview state. Dates are ISO and only ever come from the user:
"next week" is rejected, not interpreted.

`stories.py` separates *missing* from *thin*. A competency covered only by a
story with no outcome and no first-person verb is the most dangerous state in
the bank, because the user believes they are covered there.

## Why the exit codes have four answers

`status` returns **undeclared** (3) when a round is scheduled and nothing has
been prepared for it and no mock has been run — and that outranks *action* (1),
because "two items are overdue" is a smaller problem than "there is a round on
Thursday that nobody has touched", and the second is invisible unless it is its
own answer.

## The design choice that matters

A mock interview that grades kindly is worse than no mock: it converts an
unknown weakness into a believed strength. So the rubric has a **no signal**
level that is not *adequate*, the grader is told that *lean no* is the normal
outcome for an unprepared candidate, and where subagents exist the round is
planned by an agent that has not seen the prep plan and graded by one that has
not seen the story bank. An interviewer hears the round and nothing else.
