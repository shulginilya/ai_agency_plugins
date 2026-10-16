---
name: training-plan
description: Keeps a working engineer's skills sharp next to a full-time job with a daily plan (about 40 minutes) and a weekly plan (two to four longer sessions) across coding patterns, system design, deep-dives into their own stack, engineering practices and small builds, runs today's session, grades it honestly and brings weak topics back sooner. The stack, coding languages, cadence and time budget are settings that can change at any time. Use when asked for a training or study plan, what to practise today, to log a practice session, to see a streak or progress, or to change the stack, language or schedule.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Training plan

Practice that fits in a working week beats a perfect plan that does not. So
every session is short, concrete and graded, and the script, not memory,
decides what comes next.

```bash
python scripts/trainer.py where                                   # which folder, and why
python scripts/trainer.py init --stack "React,TypeScript,Node,Python" --interview-languages "Node,Python,React"
python scripts/trainer.py config show
python scripts/trainer.py config set stack "React,TypeScript,Node,Python,Go"
python scripts/trainer.py config set interview-languages "Node,Python"
python scripts/trainer.py config set cadence weekly               # daily | weekly
python scripts/trainer.py config set focus interview              # skills | interview | mixed
python scripts/trainer.py plan --write                            # both plans, rendered to plan.md
python scripts/trainer.py today                                   # the session to do now
python scripts/trainer.py today --cadence weekly                  # a weekly session today instead
python scripts/trainer.py log --topic sliding-window --score 3 --minutes 35 --notes "missed the shrink step"
python scripts/trainer.py status                                  # 0 nothing due, 1 something due
python scripts/trainer.py topics --area deep-dive
python scripts/trainer.py add-topic --area deep-dive --title "Postgres internals" --hint MVCC --hint vacuum
```

## Settings are never baked in

The stack, the interview coding languages, the cadence, the focus, the minutes,
the weak areas and the interview date all live in `state.json` and change with
`config set`. History is kept across every change. A topic for a technology
that leaves the stack stops coming up, but its scores are kept and return if
the technology comes back. A stack entry the catalog does not know, such as Go,
gets four generated deep-dives (internals, idioms, testing, performance).

The training folder: first match wins: `--home`, then `$SKILL_TRAINER_HOME`,
then the folder saved with `set-home`, then `~/.config/ai-agency/skill-trainer/`.
Windows paths are fine.

## First run

If `where` says the folder is not initialized, ask in one message:

1. Stack (default React, TypeScript, Node, Python) and coding languages for
   interviews (default Node, Python and React).
2. Daily or weekly as the active cadence, and the time: minutes a day, or
   sessions a week and minutes each.
3. Goals for the next few months, and the areas or technologies that feel
   weakest. These come up first.
4. Whether an interview is coming, and its date if known.

Then run `init` with the answers and `plan --write`. Show both plans. The
daily and the weekly plan always both exist, and `config set cadence` switches
between them.

## Running a session

1. Run `today`. Do the items in order. A review comes first because it is due.
2. Load the section of [references/session-formats.md](references/session-formats.md)
   for each item's area, and run the item that way. The topic names a pattern
   or a subject. Choose a real problem or question for it yourself, and don't
   reveal the pattern when the session is meant to test recognizing it.
3. Coding items are solved in the item's `language`. Algorithm drills rotate
   through the interview languages day by day. A framework entry such as React
   adds UI-build drills, solved in that framework. Run the code the user
   writes. Don't write the solution for them.
4. Hold the time box. Running over is part of the grade.
5. Grade with the rubric below, quoting what happened, then `log` it. Log one
   line per topic, even when the session covered two.

## The score

| Score | Meaning |
| --- | --- |
| 1 | Could not do it, even with hints |
| 2 | Got there only with major help, or the result was wrong |
| 3 | Correct, but slow, with hints, or with gaps in the explanation |
| 4 | Solid and inside the time box |
| 5 | Fast and clean, with trade-offs explained well enough to teach it |

Grade the evidence, not the effort. A generous 4 hides a weakness that a 2
would have brought back tomorrow. When unsure between two scores, give the
lower one.

## Reporting

After a session: what was done, the score with one line of evidence, when the
topic returns (from `log`), and the one thing to fix next time. For `status`:
the streaks, what is due, and the weakest area. Offer `/skill-trainer:interview`
when an interview date is within three weeks and the focus is not interview yet.
