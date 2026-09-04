# code-review

The reference plugin for this repo. It does real work, and it exercises every
component type the portable format supports — so if you want to know how a
piece fits together, it is demonstrated here.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `code-review` | The review method: scope, five passes, a four-line finding format |
| Skill | `pr-audit` | Whole-PR audit: scope, blast radius, reversibility, deploy ordering, verdict |
| Command | `/review` | Review the current diff |
| Command | `/review-pr` | Audit a PR or branch |
| Agent | `reviewer` | One focused pass in a fresh context; returns findings only |
| Hook | `PostToolUse` | Flags `console.log`, `.only`, hard-coded credentials after an edit |
| MCP | `code-review` | Dependency-free stdio server: `changed_files`, `review_checklist` |

Progressive disclosure is the design: `SKILL.md` stays short and the three
heavy references (`security.md`, `performance.md`, `accessibility.md`) load
only when the change touches that surface.

## Try it

```bash
# scope a review from the command line
python plugins/code-review/skills/code-review/scripts/changed_files.py --stat

# talk to the MCP server directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/code-review/mcp/server.py

# run its tests
python -m tools.apkit test --plugin code-review
```

## Install it

```bash
python -m tools.apkit build --plugin code-review
python -m tools.apkit install code-review --target claude-code --scope user
python -m tools.apkit install code-review --target agents --scope project --into ~/work/my-repo
```

`dist/<target>/code-review/INSTALL.md` says what each target got, what it did
not get, and why.

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes skills, commands and agents; no hooks.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; the `reviewer`
  agent is emitted as a skill, so the persona survives but the delegation does
  not; no hooks.
- **Generic `.agents/skills`** takes skills only — but one install covers
  Codex, Cursor, Gemini CLI and OpenCode at once.
