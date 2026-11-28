# notes — Gemini CLI

Harness docs: https://geminicli.com/docs/cli/skills/

## Install

```bash
python -m tools.apkit install notes --target gemini-cli --scope user
```

**user scope**

- `skills` → `~/.gemini/skills` (children)
- `commands` → `~/.gemini/commands` (children)
- `mcp` → `~/.gemini/settings.json` (merge-json)

**project scope**

- `skills` → `.gemini/skills` (children)
- `commands` → `.gemini/commands` (children)
- `mcp` → `.gemini/settings.json` (merge-json)

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands, mcp.

## Notes

- Gemini CLI reads .agents/skills as an alias for .gemini/skills and gives the alias higher precedence within each tier.
- Gemini custom commands are TOML with `description` and `prompt` keys; arguments interpolate as {{args}}.

