---
description: What the interview prep needs today — rounds coming up, overdue items, and anything scheduled that nothing has been done for.
argument_hint: "[company, or leave empty for all loops]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Report readiness: {{ARGS}}

```bash
python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" status
python "{{PLUGIN_ROOT}}/skills/story-bank/scripts/stories.py" check
```

Follow the `prep-tracker` skill for what the four exit codes mean.

- Exit 2 on `status`: there is no state file. Offer to start one from a
  description with `/prep`.
- Exit 3: a scheduled round has no prep and no mock. Lead with that — it
  outranks a pile of overdue items.
- Exit 1: name the specific actions, grouped, shortest first.
- Exit 0 on both: say so in one line and stop. Do not invent work.

Then say, in one sentence per round, what the user would walk into it with
today — and be willing to say "not ready" when the mocks say so.
