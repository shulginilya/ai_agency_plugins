---
description: One line on what this command does. Shown in the harness's command list.
argument_hint: "[what the user should type after the command]"
model: sonnet
allowed_tools: Read Grep Glob
---

Do the thing, using: {{ARGS}}

If that is empty, state the default behaviour here rather than asking.

Then follow the `example-skill` skill.

Portable placeholders: `{{ARGS}}` for everything the user typed, `{{ARG1}}` and
`{{ARG2}}` for positional arguments, `{{PLUGIN_ROOT}}` for the plugin's own
directory. Each target renders them in its own dialect.
