# developer

The feature development loop, as a plugin: orient in the code, agree a change
plan, build it in slices that stay green, verify with the repository's own
checks, and self-review before handing off. Plus the behaviour-preserving half
— refactors that do not smuggle in features.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `feature-implementation` | The loop: orient → plan → slice → verify → self-review → report |
| Skill | `safe-refactoring` | Pin behaviour, size the blast radius, apply mechanical moves |
| Command | `/implement` | Build a feature, ticket or fix end to end |
| Command | `/refactor` | Restructure without changing behaviour |
| Command | `/verify` | Run the checks the repo declares, and report what actually failed |
| Agent | `implementer` | One slice of the plan, in a fresh context, reported back |
| Hook | `SessionStart` | Branch, divergence, uncommitted count, and the repo's checks |
| MCP | `developer` | Dependency-free stdio server: `verify_commands`, `find_callers`, `dev_playbook` |

Two scripts carry the logic, and everything else imports them rather than
restating a rule:

- `skills/feature-implementation/scripts/verify.py` — reads `package.json`
  scripts, `pyproject.toml` tooling, Makefile targets, `go.mod` and
  `Cargo.toml`, picks the package manager the lockfile implies, and can run the
  checks in feedback order. Exit 2 means the repo declares no checks — a
  different answer from "everything passed".
- `skills/safe-refactoring/scripts/callers.py` — every reference to a symbol,
  grouped into definitions, production call sites and tests.

The heavy detail lives in three references that load on demand:
`change-plan.md` (plan format, slicing rules, expand-contract), `handoff.md`
(the pre-handoff self-review checklist), `refactoring-moves.md` (mechanical
steps per move).

## Try it

```bash
# what would this repo run to verify a change?
python plugins/developer/skills/feature-implementation/scripts/verify.py

# who calls this?
python plugins/developer/skills/safe-refactoring/scripts/callers.py validate_plugin --root tools

# talk to the MCP server directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/developer/mcp/server.py

# run its tests
python -m tools.apkit test --plugin developer
```

## Install it

```bash
python -m tools.apkit build --plugin developer
python -m tools.apkit install developer --target claude-code --scope user
python -m tools.apkit install developer --target agents --scope project --into ~/work/my-repo
```

`dist/<target>/developer/INSTALL.md` says what each target got and what it did
not.

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes skills, commands and the `implementer` agent; no hooks —
  so no session context line.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; `implementer` is
  emitted as a skill, so its standard survives but delegation does not — run
  the slices sequentially in one context instead.
- **Generic `.agents/skills`** takes the two skills only, which is still the
  whole method: both skills' scripts travel with them.
