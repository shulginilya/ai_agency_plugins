---
description: Run a realistic mock interview round and grade it against a rubric, or critique one answer or take-home.
argument_hint: "[round type] [company] — e.g. system-design Acme"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Run this mock: {{ARGS}}

If no round type is given, ask which one — recruiter-screen, live-coding,
take-home, system-design (say whether the AI/LLM variant), behavioral,
hiring-manager or leadership. If a company is named, read its loop first:

```bash
python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" status --company <name>
```

Follow the `mock-interview` skill, and load only the section of
`references/round-formats.md` for the round being run.

1. State the round, the time box and what is being graded. Then start.
2. Ask one question at a time. Do not coach, do not praise, do not hint unless a
   real interviewer would. Probe every claim once. Climb the follow-up ladder
   until the answer stops holding.
3. Hold the time box. Running over is a finding, not a courtesy.
4. Grade only after the round, against `references/rubrics.md`: a level per
   dimension with quoted evidence, then hire / lean hire / lean no / no, then
   **one** rewrite of the weakest answer in the user's own voice and facts.
5. Record it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" mock \
     --company <name> --round <round> --grade strong|mixed|weak \
     --weak "<point>;<point>" --strong "<point>"
   ```
6. Turn each weak point into a prep item with a date, or say plainly that the
   user should re-run this round before the real one.

Where subagents exist, get the question ladder from the `interviewer` agent and
the grade from the `grader` agent, so neither has seen the prep plan.
