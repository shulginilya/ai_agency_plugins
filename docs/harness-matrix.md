# Harness matrix

What each target supports, where it reads from, and how confident the mapping
is. Run `python -m tools.apkit targets` for the live version of the first
table, and `python -m tools.apkit doctor` to see which of these paths exist on
the machine you are on.

## Support

| Target | Skills | Commands | Agents | Hooks | MCP |
| --- | --- | --- | --- | --- | --- |
| `claude-code` | native | native | native | native | native |
| `opencode` | native | native | native | — | native |
| `cursor` | native | native | as skill | — | native |
| `codex` | native | native | as skill | — | manual snippet |
| `gemini-cli` | native | native | as skill | — | native |
| `agents` | native | — | as skill | — | reference only |

## Where skills are read from

| Target | Project | User |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` (a bundle here loads as a plugin) |
| Codex CLI | `.agents/skills/`, then parents, then repo root | `~/.agents/skills/`, then `/etc/codex/skills` |
| Cursor | `.agents/skills/`, `.cursor/skills/` (also reads `.claude/skills`, `.codex/skills`) | `~/.agents/skills/`, `~/.cursor/skills/` |
| OpenCode | `.opencode/skills/` (also `.claude/skills`, `.agents/skills`) | `~/.config/opencode/skills/` |
| Gemini CLI | `.gemini/skills/`, `.agents/skills/` (alias wins) | `~/.gemini/skills/`, `~/.agents/skills/` |

**`.agents/skills/` is the leverage point.** Codex, Cursor, Gemini CLI and
OpenCode all read it. `apkit install <plugin> --target agents` covers four
harnesses in one step; the per-harness targets exist for the components that
`.agents/skills` does not carry — commands, agents, hooks, MCP.

Installing both the generic and a specific target puts the same skill in two
discovered locations. Harnesses resolve that by precedence rather than
erroring, but you now have two copies to keep in step. Pick one.

## Commands

| Target | Location | Format | Arguments |
| --- | --- | --- | --- |
| Claude Code | `commands/<name>.md` in the plugin | markdown + frontmatter | `$ARGUMENTS`, `$1` |
| Codex CLI | `~/.codex/prompts/<name>.md` | plain markdown | `$ARGUMENTS`, `$1` |
| Cursor | `.cursor/commands/<name>.md` | markdown | `$ARGUMENTS` |
| OpenCode | `.opencode/command/<name>.md` | markdown + frontmatter | `$ARGUMENTS` |
| Gemini CLI | `.gemini/commands/<name>.toml` | TOML: `description`, `prompt` | `{{args}}` |

Write `{{ARGS}}` in the source; each target renders its own spelling.

## MCP configuration

| Target | File | Shape |
| --- | --- | --- |
| Claude Code | `.mcp.json` in the plugin | `{"mcpServers": {...}}` |
| Cursor | `.cursor/mcp.json` | `{"mcpServers": {...}}` |
| Gemini CLI | `.gemini/settings.json` | `{"mcpServers": {...}}` |
| OpenCode | `opencode.json` | `{"mcp": {name: {type, command[], enabled}}}` |
| Codex CLI | `~/.codex/config.toml` | `[mcp_servers.<name>]` — emitted as a snippet to merge by hand |

`{{PLUGIN_ROOT}}` in `mcp/servers.json` resolves to `${CLAUDE_PLUGIN_ROOT}` for
Claude Code, and to the plugin's absolute source path everywhere else — because
loose installs scatter skills into harness directories, and nothing there knows
where the plugin came from.

## Verification status

Mappings marked unverified in `targets/*.json` were inferred rather than read
off that harness's documentation. As of this writing:

- `codex.commands`, `cursor.commands`, `opencode.commands`, `gemini-cli.commands`
- `opencode.agents`, `opencode.mcp`, `gemini-cli.mcp`

Skill discovery paths are verified for every target. If you confirm one of the
above against a live harness, set `"verified": true` in the manifest and note
it here — that flag is the repo's memory of what has actually been checked.
