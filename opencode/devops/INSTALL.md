# devops — OpenCode

Harness docs: https://opencode.ai/docs/skills/

## Install

```bash
python -m tools.apkit install devops --target opencode --scope user
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

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands, agents, mcp.

## Notes

- OpenCode reads .opencode/skills, ~/.config/opencode/skills, and — for compatibility — .claude/skills and .agents/skills.

