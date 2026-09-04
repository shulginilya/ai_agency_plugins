# Plugin format

A plugin is a directory under `plugins/`. Only `plugin.json` is required;
every component directory is optional and discovered by convention.

```
plugins/<name>/
├── plugin.json                  metadata (required)
├── README.md                    what it does, for humans
├── skills/<skill>/SKILL.md      Agent Skills spec
│   ├── references/*.md          loaded on demand
│   ├── scripts/*                travels with the skill everywhere
│   └── assets/*                 templates, data
├── commands/<name>.md           slash commands
├── agents/<name>.md             subagents
├── hooks/hooks.json             Claude Code lifecycle hooks
├── mcp/servers.json             MCP server declarations
├── mcp/*                        server implementations (shipped with bundles)
├── scripts/*                    shared scripts — bundle targets only
└── tests/test_*.py              run by `apkit test`
```

## `plugin.json`

```json
{
  "name": "code-review",
  "displayName": "Code Review",
  "version": "0.1.0",
  "description": "What it does, and when someone would reach for it.",
  "author": { "name": "...", "email": "..." },
  "license": "MIT",
  "homepage": "https://...",
  "repository": "https://...",
  "keywords": ["code-review", "audit"],
  "targets": {
    "exclude": ["gemini-cli"],
    "overrides": {
      "cursor": { "mcpServers": { "extra": { "command": "..." } } }
    }
  }
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | lowercase-hyphenated, must equal the directory name |
| `version` | yes | semver; CI checks nothing else, but releases depend on it |
| `description` | yes | ends up in the Claude Code marketplace listing |
| `license` | no | warned on when absent |
| `targets.exclude` | no | target ids to skip entirely for this plugin |
| `targets.overrides` | no | per-target additions; currently `mcpServers` |

## Commands

Markdown with frontmatter. Keys are mapped per target; unmapped keys are
dropped rather than passed through.

```markdown
---
description: One line, shown in the harness's command list.
argument_hint: "[what to type after the command]"
model: sonnet
allowed_tools: Bash(git:*) Read Grep
---

Do the thing with: {{ARGS}}
```

| Portable | Claude Code / Codex / Cursor / OpenCode | Gemini CLI |
| --- | --- | --- |
| `{{ARGS}}` | `$ARGUMENTS` | `{{args}}` |
| `{{ARG1}}` | `$1` | `{{args}}` |
| `{{PLUGIN_ROOT}}` | `${CLAUDE_PLUGIN_ROOT}` (bundles) | plugin source path |

Always give the command a defined behaviour for empty arguments. A command that
asks a question when it could have picked a sensible default wastes a turn.

## Agents

Markdown with frontmatter and a system prompt body. On targets without
subagents the file is emitted as a skill with a preamble explaining that the
role is being adopted inline — so write the body to survive that.

```markdown
---
name: reviewer
description: What it does and when to delegate to it.
model: sonnet
tools: Read, Grep, Glob, Bash
---

You do one thing. Here is your standard. Here is exactly what you return, and
what you return when there is nothing to report.
```

The frontmatter `name` must match the file name.

## Hooks

Claude Code's schema, verbatim, because no other target has an equivalent. Use
`${CLAUDE_PLUGIN_ROOT}` for script paths.

Hook scripts must always exit 0. A hook that fails a legitimate action blocks
work the user asked for, and the failure is hard to attribute back to the hook.

## MCP servers

Standard MCP server objects. `{{PLUGIN_ROOT}}` resolves per target.

```json
{
  "mcpServers": {
    "code-review": {
      "command": "python",
      "args": ["{{PLUGIN_ROOT}}/mcp/server.py"],
      "env": {}
    }
  }
}
```

Anything else in `mcp/` is treated as the server implementation and ships with
bundle targets, so the config never points at a file that is not there. A
dependency-free stdio server is about 150 lines — see
`plugins/code-review/mcp/server.py` — and is worth far more than a config entry
pointing at a package the user has to install first.
