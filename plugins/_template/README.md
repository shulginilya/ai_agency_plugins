# _template

Copy this to start a plugin:

```bash
python -m tools.apkit new my-plugin
```

That copies this directory to `plugins/my-plugin/` and rewrites the name in
`plugin.json`. Then:

1. Write the real `description` in `plugin.json` — it is what a human reads.
2. Rename `skills/example-skill/` and rewrite its `SKILL.md`. The directory
   name and the frontmatter `name` must match.
3. Delete the components you do not need. An empty `commands/`, `agents/`,
   `hooks/` or `mcp/` costs nothing, but a placeholder skill that says nothing
   pollutes every harness it installs into.
4. `python -m tools.apkit validate --plugin my-plugin --strict`

Directories that mean something:

```
plugin.json                     metadata; the only required file
skills/<name>/SKILL.md          Agent Skills spec — portable everywhere
skills/<name>/references/       loaded on demand, keeps SKILL.md short
skills/<name>/scripts/          travels with the skill on every harness
commands/<name>.md              slash commands; {{ARGS}} is the portable placeholder
agents/<name>.md                subagents; emitted as skills where unsupported
hooks/hooks.json                Claude Code lifecycle hooks
mcp/servers.json                MCP servers; {{PLUGIN_ROOT}} resolves per target
scripts/                        shared scripts — bundle targets only
tests/test_*.py                 run by `apkit test`
```
