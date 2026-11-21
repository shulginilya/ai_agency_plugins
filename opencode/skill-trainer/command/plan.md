---
description: Set up or show your training plans — a daily plan and a weekly plan across coding, system design, stack deep-dives, practices and builds.
model: claude-opus-5-5
---

Training plan: $ARGUMENTS

Follow the `training-plan` skill.

1. Run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" where`. If it is not initialized, run the skill's **First run**
   questions in one message, then `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" init` with the answers. Defaults: stack
   React,TypeScript,Node,Python, interview languages Node, Python and React, daily cadence of 40 min.
2. If the arguments ask for a change (cadence, minutes, sessions, focus, stack,
   interview languages, goals, weak areas, interview date), apply each with
   `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" config set KEY VALUE` and say what changed.
3. Run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" plan --write`. Show both plans, and say which cadence is active and
   that `/skill-trainer:settings cadence weekly` (or daily) switches it.
4. End with the first session: `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" today`, and offer to start it with
   `/skill-trainer:today`.
