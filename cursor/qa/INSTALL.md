# qa — Cursor

Harness docs: https://cursor.com/docs/context/skills

## Install

```bash
python -m tools.apkit install qa --target cursor --scope user
```

**user scope**

- `skills` → `~/.cursor/skills` (children)
- `commands` → `~/.cursor/commands` (children)

**project scope**

- `skills` → `.cursor/skills` (children)
- `commands` → `.cursor/commands` (children)
- `mcp` → `.cursor/mcp.json` (merge-json)

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands.

## Notes

- Cursor also reads .agents/skills, .claude/skills and .codex/skills, so the generic `agents` target covers it too — installing both duplicates the skill.

