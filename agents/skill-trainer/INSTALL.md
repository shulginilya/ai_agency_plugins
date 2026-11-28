# skill-trainer — Generic Agent Skills (.agents/skills)

Harness docs: https://agentskills.io/specification

## Install

```bash
python -m tools.apkit install skill-trainer --target agents --scope user
```

**user scope**

- `skills` → `~/.agents/skills` (children)

**project scope**

- `skills` → `.agents/skills` (children)

## Not emitted for this target

- **commands** — The open standard covers skills only. Commands are per-harness; use a specific target.
- **hooks** — no lifecycle hooks; enforce the same checks in CI or a git hook
- **scripts** — plugin-level scripts/ only ships with bundle targets; skills that need a script on this harness must carry it in their own scripts/ directory

## Notes

- The lowest common denominator, and the highest-leverage target: Codex CLI, Cursor, Gemini CLI and OpenCode all read .agents/skills. One install, four harnesses.

