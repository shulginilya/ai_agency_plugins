# skill-trainer

Training that fits next to a full-time job. Every session is short, concrete
and graded, and the script decides what comes next: weak topics come back
tomorrow, strong ones space out to weeks.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `training-plan` | Daily and weekly plans, today's session, honest 1–5 grading, spaced review, settings |
| Skill | `interview-track` | Coding patterns and system design for the technical interview phases (no screening) |
| Command | `/skill-trainer:plan` | First-run setup, then both plans |
| Command | `/skill-trainer:today` | Run, grade and log today's session |
| Command | `/skill-trainer:log` | Log practice done on your own |
| Command | `/skill-trainer:status` | Streaks, what is due, coverage, weakest area |
| Command | `/skill-trainer:interview` | Coding or design drill, or interview readiness |
| Command | `/skill-trainer:settings` | Change stack, interview languages, cadence, focus, time, folder |
| Hook | `SessionStart` | One line when today's training is not done — at most once a day |

## Both plans

- **Daily:** about 40 minutes a day. A different area each weekday, with a
  short review first when something is due.
- **Weekly:** two to four sessions of 60–90 minutes, each pairing two areas.

Both always exist. `config set cadence daily|weekly` picks the active one.
`today --cadence weekly` runs a weekly session on a daily plan.

Areas: `coding` (19 patterns, plus 7 React UI builds), `design` (16 system designs), `deep-dive`
(your stack), `practices` (testing, observability, security, data,
delivery…), `build` (small projects with acceptance criteria). The focus
weights them:
- `skills`: all five areas;
- `interview`: coding and design only;
- `mixed` (default): interview areas first, the rest in between.

## Everything is a setting

```bash
python skills/training-plan/scripts/trainer.py config set stack "React,TypeScript,Node,Python"
python skills/training-plan/scripts/trainer.py config set interview-languages "Node,Python,React"
python skills/training-plan/scripts/trainer.py config set cadence weekly
python skills/training-plan/scripts/trainer.py config set interview-date 2026-11-20
python skills/training-plan/scripts/trainer.py set-home "C:\Users\me\training"
```

- **Defaults:** stack React, TypeScript, Node, Python; interview coding in
  Node, Python and React; daily, mixed focus.
- **Interview languages:** algorithm drills rotate through the languages day
  by day. A framework entry such as React adds UI-build drills (an
  autocomplete, a form, an accessible modal…).
- **Stack changes keep history.** Topics for a dropped technology stop coming
  up but keep their scores. A technology the catalog doesn't know gets
  generated deep-dives.
- **Custom topics:** `add-topic` adds your own to any area.

State: `state.json` in the training folder, which defaults to
`~/.config/ai-agency/skill-trainer/`. Override it with `$SKILL_TRAINER_HOME`
or `set-home`. Every write backs up the old file first, and the script
refuses a JSON file that isn't its own. `plan.md` is rendered from the state,
one way only.

## Interview track

Coding drills don't name the pattern, because recognizing it is half the test.
- **Time boxes:** 20, 30 and 40 minutes by level.
- **Order:** brute force out loud, then the better approach.
- **Harness:** a real test harness in each interview language (`node --test`
  for Node, pytest or plain asserts for Python, Vitest with Testing Library
  for React). `coding-patterns.md` also lists the language's gotchas.

System design runs a fixed seven-step framework with times and probes. For
full graded mocks, the track hands off to `/interview-prep:mock` when that
plugin is installed: its grader hasn't seen this plan. The grade is then
logged back here with `--kind mock`.

## Exit codes

`trainer.py status`:
- 0: nothing is due;
- 1: something is due;
- 2: bad input or an unusable state file.

The hook always exits 0.
