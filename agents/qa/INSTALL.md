# qa — Generic Agent Skills (.agents/skills)

Harness docs: https://agentskills.io/specification

## Install

```bash
python -m tools.apkit install qa --target agents --scope user
```

**user scope**

- `skills` → `~/.agents/skills` (children)

**project scope**

- `skills` → `.agents/skills` (children)

## Not emitted for this target

- **commands** — The open standard covers skills only. Commands are per-harness; use a specific target.

## Notes

- The lowest common denominator, and the highest-leverage target: Codex CLI, Cursor, Gemini CLI and OpenCode all read .agents/skills. One install, four harnesses.

