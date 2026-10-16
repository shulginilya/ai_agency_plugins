---
description: Interview training for the coding and system design phases (no screening) — timed pattern drills, design rounds with a framework, readiness.
argument_hint: "[coding | design | readiness | a topic id, e.g. graphs-bfs-dfs or sd-chat]"
model: claude-opus-5-5
allowed_tools: Bash Read Write Edit
---

Interview track: {{ARGS}}

Follow the `interview-track` skill. Screening and behavioral rounds are out of scope.

1. Run `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" interview`. If nothing is set up, run `/skill-trainer:plan` first.
2. **readiness**, or no arguments: report the readiness bars from the skill
   and which do not hold yet. Recommend a focus change with
   `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" config set focus interview` when an interview is close. Offer the next
   drill.
3. **coding**, **design** or a topic id: run one drill. Take the topic from the
   `next` list for that area unless an id is given. Coding is solved in the
   interview language (`python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" config show`), with the harness from
   `references/coding-patterns.md`. Design uses
   `references/system-design-framework.md`. Hold the time box, grade strictly,
   then log:
   `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" log --topic <id> --score <1-5> --minutes <m> --notes "<what to fix>"`.
4. For a full graded mock, hand off to `/interview-prep:mock live-coding` or
   `/interview-prep:mock system-design` when that plugin is installed. Then log
   its grade with `--kind mock` (strong 4, mixed 3, weak 2).
