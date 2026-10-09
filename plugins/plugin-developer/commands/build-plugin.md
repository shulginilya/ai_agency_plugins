---
description: Build a plugin from a requirements prompt — plan it, get approval, build and test it in a fresh context, gate it, and audit it against the original prompt.
argument_hint: "[requirements text or file, or the name of an approved plan]"
model: sonnet
allowed_tools: Bash Read Grep Glob Write Edit
---

Build a plugin from: {{ARGS}}

1. **Find or make the plan.**
   - If {{ARGS}} names a plan in `.plugin-dev/<name>/requirements.json` that
     the user has approved in this conversation, use it.
   - Otherwise do everything `/plan-plugin` does with {{ARGS}}, present the
     plan, and **stop for approval**. Do not scaffold anything before the user
     says yes.
   - If {{ARGS}} is empty, ask for the requirements and stop.

2. **Build in a fresh context.** Once approved, delegate to the
   `plugin-developer` agent with: the plugin name, the path to the approved
   `requirements.json`, the repo root, and any decisions the user made while
   approving that the file does not record. It scaffolds, writes, tests and
   gates the plugin, and returns a report.

   If subagents are not available, follow the `plugin-scaffolding` and then
   the `plugin-verification` skills yourself.

3. **Audit in a second fresh context.** Delegate to the
   `requirements-auditor` agent with exactly two things: the original prompt
   (print it with
   `python "{{PLUGIN_ROOT}}/skills/requirements-analysis/scripts/requirements.py" prompt plugins/<name>/requirements.json`)
   and the path `plugins/<name>/`. Do not pass the plan, the requirements
   list or the build report — its value is not having seen them.

4. **Report.** Relay the developer's report block as it is, then the audit.
   For each audit finding, say whether you agree and what you would change —
   but change nothing without the user's go-ahead. Finish by naming the
   gate result plainly: PASS, INCOMPLETE with the steps not checked here, or
   FAIL with the step.

Do not stage, commit or push. Say which branch the plugin was built on
(`git branch --show-current`) so the user can decide where it goes.
