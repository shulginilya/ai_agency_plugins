# developer

The feature development loop, as a plugin: orient in the code, agree a change
plan, build it test-first in red-green-refactor slices, verify with the repository's own
checks, and self-review before handing off. Plus the behaviour-preserving half
— refactors that do not smuggle in features.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `feature-implementation` | The loop: orient → plan → slice → verify → self-review → report |
| Skill | `safe-refactoring` | Pin behaviour, size the blast radius, apply mechanical moves |
| Skill | `ship-change` | Ticket on a board, branch, commit, push, PR, card confirmed in review |
| Skill | `root-cause-analysis` | Reproduce, narrow, prove the mechanism, fix the cause, leave a failing-first test |
| Skill | `regression-triage` | "It worked before": bracket good and bad, script a verdict, bisect, read the culprit |
| Skill (shared) | `ticket-management` | Create, batch, edit, close and delete GitHub issues; board cards. Source: `plugins/_shared/skills/` |
| Skill (shared) | `test-driven-development` | Red-green-refactor, one behaviour per cycle; `tdd.py` tells a real red from an errored or empty run. Source: `plugins/_shared/skills/` |
| Command | `/implement` | Build a feature, ticket or fix end to end |
| Command | `/refactor` | Restructure without changing behaviour |
| Command | `/verify` | Run the checks the repo declares, and report what actually failed |
| Command | `/ship` | Put a finished change up for review: ticket, branch, PR, In review |
| Command | `/diagnose` | Diagnose a bug down to its root cause, without changing code |
| Command | `/fix` | Fix a bug whose cause is proved, failing test first |
| Command | `/tdd` | Build one behaviour, or a short list of them, test-first in red-green-refactor cycles |
| Command | `/bisect` | Find the commit that introduced a regression |
| Agent | `implementer` | One slice of the plan, in a fresh context, reported back |
| Agent | `investigator` | Tests one hypothesis about a bug's cause, in a fresh context, with the evidence |
| Hook | `SessionStart` | Branch, divergence, uncommitted count, and the repo's checks |
| Hook | `PostToolUse` | After an edit, flags a change that hides a symptom (swallowed error, skipped test) |
| MCP | `developer` | Dependency-free stdio server: `verify_commands`, `find_callers`, `dev_playbook`, `repro_command`, `change_history`, `bug_playbook` |

Two scripts carry the logic, and everything else imports them rather than
restating a rule:

- `skills/feature-implementation/scripts/verify.py` — reads `package.json`
  scripts, `pyproject.toml` tooling, Makefile targets, `go.mod` and
  `Cargo.toml`, picks the package manager the lockfile implies, and can run the
  checks in feedback order. Exit 2 means the repo declares no checks — a
  different answer from "everything passed".
- `skills/safe-refactoring/scripts/callers.py` — every reference to a symbol,
  grouped into definitions, production call sites and tests.
- `ship-change` files its ticket and moves its card with the shared
  `ticket-management` skill's `tickets.py` and `board.py`. `board.py` re-reads a
  card after moving it, so a board automation cannot silently undo the move.

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
