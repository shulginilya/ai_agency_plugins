---
description: Write a bug report a developer can reproduce on the first try, ready to be filed as a ticket.
argument_hint: "[what went wrong, or a failing QA case]"
model: claude-sonnet-5-5
effort: medium
allowed_tools: Bash Read Grep Glob
---

Report a bug: {{ARGS}}

Follow the `bug-reporting` skill:

1. Reproduce it twice from a clean start. If it's intermittent, count how often it fails.
2. Cut the steps down to the shortest path that still fails.
3. Write the report in the skill's format: title, severity with its reason, where it was
   found, build and environment, steps, expected versus actual, frequency, evidence, and
   what was ruled out.
4. Hand it over for developer or scrum-master to file. QA doesn't write tickets.
