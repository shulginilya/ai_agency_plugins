# skill-trainer — OpenCode

Harness docs: https://opencode.ai/docs/skills/

## Install

```bash
python -m tools.apkit install skill-trainer --target opencode --scope user
```

**user scope**

- `skills` → `~/.config/opencode/skills` (children)
- `commands` → `~/.config/opencode/command` (children)
- `agents` → `~/.config/opencode/agent` (children)

**project scope**

- `skills` → `.opencode/skills` (children)
- `commands` → `.opencode/command` (children)
- `agents` → `.opencode/agent` (children)
- `mcp` → `opencode.json` (merge-json)

## Not emitted for this target

- **hooks** — Use OpenCode plugins/CI for equivalent enforcement.
- **scripts** — plugin-level scripts/ only ships with bundle targets; skills that need a script on this harness must carry it in their own scripts/ directory

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands, agents, mcp.

## Notes

- OpenCode reads .opencode/skills, ~/.config/opencode/skills, and — for compatibility — .claude/skills and .agents/skills.

