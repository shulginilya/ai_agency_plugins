---
description: Run today's training session — reviews that are due first, then the next topic — and grade and log it.
---

Today's session: $ARGUMENTS

Follow the `training-plan` skill.

1. Run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" today` (add `--cadence weekly` when the arguments say weekly). When a
   topic id is given instead, run that topic alone. When nothing is set up, run
   `/skill-trainer:plan` first.
2. Say the session in one line: the items, the minutes, and why each was picked.
   Then start the first item.
3. Run each item with its area's section of the skill's
   `references/session-formats.md`. Coding items use the item's language and
   the interview-track skill's `references/coding-patterns.md` for the harness.
   Run the code the user writes; never write the solution for them first.
4. Hold the time box. After each item, grade it with the skill's score table,
   quoting the evidence, and log it:
   `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" log --topic <id> --score <1-5> --minutes <m> --notes "<the one thing to fix>"`.
5. Close with the scores, when each topic returns, and the streak from
   `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" status`.
