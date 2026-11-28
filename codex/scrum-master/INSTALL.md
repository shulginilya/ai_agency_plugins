# scrum-master — Codex CLI

Harness docs: https://developers.openai.com/codex/skills/

## Install

```bash
python -m tools.apkit install scrum-master --target codex --scope user
```

**user scope**

- `skills` → `~/.agents/skills` (children)
- `commands` → `~/.codex/prompts` (children)

**project scope**

- `skills` → `.agents/skills` (children)

## Not emitted for this target

- **hooks** — Codex has no equivalent of Claude Code lifecycle hooks. Wire the same checks into CI or a git pre-commit hook.
- **scripts** — plugin-level scripts/ only ships with bundle targets; skills that need a script on this harness must carry it in their own scripts/ directory

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands.

## Notes

- Codex resolves skills from .agents/skills (repo, then parents, then repo root), then ~/.agents/skills, then /etc/codex/skills.
- Skills can be toggled per-skill via [[skills.config]] entries in ~/.codex/config.toml.

