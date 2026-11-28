# code-reviewer — Claude Code

Harness docs: https://code.claude.com/docs/en/plugins-reference

## Install

```bash
python -m tools.apkit install code-reviewer --target claude-code --scope user
```

**user scope**

- `__bundle__` → `~/.claude/skills/{plugin}` (bundle)

**project scope**

- `skills` → `.claude/skills` (children)
- `commands` → `.claude/commands` (children)
- `agents` → `.claude/agents` (children)

## Notes

- User scope drops the whole bundle into ~/.claude/skills/<plugin>/, which Claude Code loads as a personal-scope plugin (`<plugin>@skills-dir`) with no marketplace step.
- For team distribution, publish this repo as a marketplace instead: `apkit marketplace` regenerates .claude-plugin/marketplace.json.

