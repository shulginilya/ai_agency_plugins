# typescript-code-reviewer — Codex CLI

Harness docs: https://developers.openai.com/codex/skills/

## Install

```bash
python -m tools.apkit install typescript-code-reviewer --target codex --scope user
```

**user scope**

- `skills` → `~/.agents/skills` (children)
- `commands` → `~/.codex/prompts` (children)

**project scope**

- `skills` → `.agents/skills` (children)

## Unverified mappings

These component paths are best-effort and may drift with the harness. Check them against the docs above before trusting them: commands.

## Notes

- Codex resolves skills from .agents/skills (repo, then parents, then repo root), then ~/.agents/skills, then /etc/codex/skills.
- Skills can be toggled per-skill via [[skills.config]] entries in ~/.codex/config.toml.

