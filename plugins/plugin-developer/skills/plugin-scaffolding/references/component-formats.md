# Component formats

The portable source format under `plugins/<name>/`. `apkit build` renders it
for every harness; `docs/plugin-format.md` in the repo is the full reference.

## plugin.json

```json
{
  "name": "my-plugin",
  "displayName": "My Plugin",
  "version": "0.1.0",
  "description": "What it does. Use when the user asks to ...",
  "author": {"name": "...", "email": "..."},
  "license": "MIT",
  "keywords": [],
  "targets": {"exclude": [], "overrides": {}}
}
```

`name` equals the directory name. The description is what a model reads
before deciding to use the plugin: say what it does and when, in the words a
user would type.

## Skill — `skills/<name>/SKILL.md`

```markdown
---
name: <name, equal to the directory>
description: What it does and when to use it, ≤1024 chars, ending in "Use when ...".
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---
```

Body: imperative, under 500 lines, detail in `references/*.md` (one level
deep). Scripts in `scripts/` travel with the skill to every harness. No
harness-specific text in the body.

## Command — `commands/<name>.md`

```markdown
---
description: One line for the command list.
argument_hint: "[what to type after the command]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Do the thing with: {{ARGS}}

Follow the `<skill>` skill.
```

| Placeholder | Becomes |
| --- | --- |
| `{{ARGS}}` | `$ARGUMENTS` (Claude Code, Codex, Cursor, OpenCode), `{{args}}` (Gemini) |
| `{{ARG1}}` | `$1` |
| `{{PLUGIN_ROOT}}` | `${CLAUDE_PLUGIN_ROOT}` in bundles, the source path elsewhere |

Always define what the command does with empty arguments.

## Agent — `agents/<name>.md`

```markdown
---
name: <name, equal to the file name>
description: What it does and when to delegate to it.
model: sonnet
tools: Read, Grep, Glob, Bash
---
```

Body: the one job, the standard, the exact output block, and what to return
when there is nothing to report. On harnesses without subagents the file is
emitted as a skill, so write it to survive being adopted inline.

## Hooks — `hooks/hooks.json`

Claude Code's schema, verbatim:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {"type": "command",
           "command": "\"$(command -v python3 || command -v python)\" \"${CLAUDE_PLUGIN_ROOT}/scripts/check.py\""}
        ]
      }
    ]
  }
}
```

Hook entry points live in plugin-level `scripts/`, put the skill's
`scripts/` on `sys.path`, and import the rule. They always exit 0. To block a
Stop, print `{"decision": "block", "reason": "..."}` and honour
`stop_hook_active` so it blocks at most once.

## MCP server — `mcp/servers.json` and `mcp/server.py`

```json
{
  "mcpServers": {
    "my-plugin": {
      "command": "sh",
      "args": ["-c", "exec \"$(command -v python3 || command -v python)\" \"$@\"", "sh",
               "{{PLUGIN_ROOT}}/mcp/server.py"],
      "env": {}
    }
  }
}
```

`server.py` is a dependency-free JSON-RPC 2.0 stdio server, about 150 lines:
copy the shape of `plugins/scrum-master/mcp/server.py`. It answers
`initialize`, `tools/list` and `tools/call`; each tool imports its logic from
a skill's `scripts/`. `tools/call` catches `(Exception, SystemExit)` and
returns `isError`, because the imported scripts are CLIs that exit on bad
input.

## Tests — `tests/test_*.py`

Standalone `unittest` scripts — `apkit test` runs each one as a script, so
they cannot import a shared helper. See [test patterns](test-patterns.md).
