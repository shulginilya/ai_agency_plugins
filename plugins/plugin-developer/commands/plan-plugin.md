---
description: Turn a requirements prompt into a plugin plan — numbered requirements, the components that cover them and why — and stop for approval.
argument_hint: "[requirements text, or a path to a file holding them]"
model: sonnet
allowed_tools: Bash Read Grep Glob Write Edit
---

Plan a plugin from: {{ARGS}}

Follow the `requirements-analysis` skill. Write nothing under `plugins/`.

1. **Get the prompt.** If {{ARGS}} is a path to a readable file, use the
   file. If it is text, use the text. If it is empty, ask for the requirements
   and stop — there is nothing to plan from.

2. **Name the plugin** from what it does, then start the requirements file:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/requirements-analysis/scripts/requirements.py" new <name> --prompt-file <file>
   ```

   (or `--prompt "<text>"`). Exit 2 means the name is taken or a plan already
   exists in `.plugin-dev/<name>/` — read it and ask whether to continue it.

3. **Split, ask, plan**, as the skill describes. Run both checks until they
   exit 0:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/requirements-analysis/scripts/requirements.py" check .plugin-dev/<name>/requirements.json --root .
   python "{{PLUGIN_ROOT}}/skills/plugin-verification/scripts/req_trace.py" check .plugin-dev/<name>/requirements.json
   ```

   If `requirements.py` exits 3, ask the open questions (at most three,
   together) and stop until they are answered.

4. **Present the plan** in the skill's order — requirements table,
   assumptions, directory tree with one line per file, components and why
   (including what was left out and why), the build flow — and end with one
   question: approve, or what to change.

When the user approves, continue with `/build-plugin <name>`.
