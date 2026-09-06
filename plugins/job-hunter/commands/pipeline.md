---
description: Show what needs chasing in the job search today, and record stage changes.
argument_hint: "[nothing for what is due, or: add / move <company> to <stage>]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Pipeline: {{ARGS}}

Follow the `application-pipeline` skill. Read the file before changing it — the
user may have edited it by hand.

With no argument, report what needs action:

```bash
python "{{PLUGIN_ROOT}}/skills/application-pipeline/scripts/pipeline.py" due
```

Group the output shortest-first and turn each row into a specific action —
"send the follow-up to Acme, it was due yesterday" rather than a count. For
anything stale past a month, propose closing it.

To record a change, use `add` or `move` with an explicit ISO due date:

```bash
python "{{PLUGIN_ROOT}}/skills/application-pipeline/scripts/pipeline.py" list
python "{{PLUGIN_ROOT}}/skills/application-pipeline/scripts/pipeline.py" \
  move <company> --to <sourced|applied|screening|interview|offer|closed> \
  --next "<next action>" --due <YYYY-MM-DD>
```

Never move a row on an assumption, and never write a due date the user has not
agreed to. If they say "next week", convert it and say which date you used.
