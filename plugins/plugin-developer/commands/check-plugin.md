---
description: Re-run the plugin gate — coverage, validation, build, Claude Code load, tests, MCP smoke test — on an existing plugin and report each step.
argument_hint: "[plugin name under plugins/] [--audit]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Check the plugin: {{ARGS}}

Follow the `plugin-verification` skill. This command reports; it does not fix.

1. **Which plugin.** Take the first word of {{ARGS}}. If it is empty, use the
   open build session in `.plugin-dev/active.json`; if there is none, list
   the directories under `plugins/` and ask which one.

2. **Run the gate:**

   ```bash
   python "{{PLUGIN_ROOT}}/skills/plugin-verification/scripts/gate.py" run <name>
   ```

3. **Report** in the skill's report block. For a failing step, quote its
   output and name the likely cause from the skill's fix list. For an
   incomplete result, name the steps not checked and why.

4. **Audit only when asked.** If {{ARGS}} contains `--audit` and the plugin
   has a `requirements.json`, delegate to the `requirements-auditor` agent
   with the original prompt
   (`python "{{PLUGIN_ROOT}}/skills/requirements-analysis/scripts/requirements.py" prompt plugins/<name>/requirements.json`)
   and the plugin path — nothing else — and add its findings.

Offer to fix what failed; do not start fixing in this command.
