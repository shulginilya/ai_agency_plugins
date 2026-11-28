# developer — Cursor

Harness docs: https://cursor.com/docs/context/skills

## Install

```bash
python -m tools.apkit install developer --target cursor --scope user
```

**user scope**

- `skills` → `~/.cursor/skills` (children)
- `commands` → `~/.cursor/commands` (children)

**project scope**

- `skills` → `.cursor/skills` (children)
- `commands` → `.cursor/commands` (children)
- `mcp` → `.cursor/mcp.json` (merge-json)

## Not emitted for this target

- **hooks** — No lifecycle hook equivalent at this fidelity. Use Cursor rules or CI.
- **scripts** — plugin-level scripts/ only ships with bundle targets; skills that need a script on this harness must carry it in their own scripts/ directory

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands.

## Notes

- Cursor also reads .agents/skills, .claude/skills and .codex/skills, so the generic `agents` target covers it too — installing both duplicates the skill.

