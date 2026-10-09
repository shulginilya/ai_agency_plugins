---
name: plugin-scaffolding
description: Builds an approved plugin plan into files — scaffolds exactly the planned skills, commands, agents, hooks, MCP server, scripts and tests in this repo's portable plugin format, then writes each one to the conventions the existing plugins settled. Use when a plugin plan has been approved and needs building, or when adding a component to a plugin under plugins/.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Plugin scaffolding

Only an approved plan gets built. If there is no
`.plugin-dev/<name>/requirements.json` that passes both checks in the
`requirements-analysis` skill, stop and go back there.

## 1. Scaffold the plan, nothing else

```bash
python scripts/scaffold.py <name>
```

It refuses a plan that is not ready (exit 1, problems listed) and a name that
is taken (exit 2). On success it creates `plugins/<name>/` with:

- `plugin.json` from the repo template, with the plan's name and description;
- one stub per planned component, each containing `TODO(plugin-developer)`;
- `requirements.json`, moved out of `.plugin-dev/` — the plugin is now its home;
- `README.md` with the components table rendered from `requirements.json`;
- an open build session, which the Stop hook holds to the gate.

The gate fails while any `TODO(plugin-developer)` marker is left, so a stub
cannot ship by accident.

## 2. Write the components, in this order

1. **Scripts first.** They hold the rules; everything else calls them. A
   script answers more than pass/fail: give it an exit code for "unusable
   input" and one for "cannot tell", and document them in its docstring.
2. **Tests for every script and MCP tool, before the prose.** Read
   [test patterns](references/test-patterns.md).
3. **Skills.** The method, with the script calls in it. Skill-relative paths
   (`scripts/x.py`); name a sibling skill instead of linking into it.
4. **Commands.** Entry point, argument handling, `{{ARGS}}`, then "follow the
   `<skill>` skill". Scripts are referenced as
   `{{PLUGIN_ROOT}}/skills/<skill>/scripts/x.py`.
5. **Agents.** One job, its standard, its exact output — including what it
   returns when there is nothing to report.
6. **Hook and MCP server last.** Both import the skill scripts; neither
   restates a rule.

Formats, frontmatter keys and placeholders are in
[component formats](references/component-formats.md). The conventions that
apply to every plugin here are in [conventions](references/conventions.md) —
read it before writing the first script.

## 3. Keep the plan and the files in step

When writing a component shows the plan was wrong — a script is not needed, a
second skill is — change `requirements.json` first, then the files, then
re-render the README table with the `plugin-verification` skill's
`req_trace.py table plugins/<name>/requirements.json --write-readme plugins/<name>/README.md`.

A component on disk that the plan does not list fails the gate, and so does a
planned one that is missing. Never add a component without adding the
requirement that needs it; if no requirement needs it, do not add it.

## 4. Hand over to verification

When no stub is left, follow the `plugin-verification` skill.
