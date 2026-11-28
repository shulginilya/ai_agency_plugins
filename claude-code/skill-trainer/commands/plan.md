---
description: Set up or show your training plans — a daily plan and a weekly plan across coding, system design, stack deep-dives, practices and builds.
argument-hint: "[nothing to show the plans, or what to change, e.g. \\\"weekly, 3 sessions of 90 min\\\"]"
model: claude-opus-5-5
effort: high
allowed-tools: Bash(python:*) Read
---

Training plan: $ARGUMENTS

Follow the `training-plan` skill.

1. Run `python "${CLAUDE_PLUGIN_ROOT}/skills/training-plan/scripts/trainer.py" where`. If it is not initialized, run the skill's **First run**
   questions in one message, then `python "${CLAUDE_PLUGIN_ROOT}/skills/training-plan/scripts/trainer.py" init` with the answers. Defaults: stack
   React,TypeScript,Node,Python, interview languages Node, Python and React, daily cadence of 40 min.
2. If the arguments ask for a change (cadence, minutes, sessions, focus, stack,
   interview languages, goals, weak areas, interview date), apply each with
   `python "${CLAUDE_PLUGIN_ROOT}/skills/training-plan/scripts/trainer.py" config set KEY VALUE` and say what changed.
3. Run `python "${CLAUDE_PLUGIN_ROOT}/skills/training-plan/scripts/trainer.py" plan --write`. Show both plans, and say which cadence is active and
   that `/skill-trainer:settings cadence weekly` (or daily) switches it.
4. End with the first session: `python "${CLAUDE_PLUGIN_ROOT}/skills/training-plan/scripts/trainer.py" today`, and offer to start it with
   `/skill-trainer:today`.
