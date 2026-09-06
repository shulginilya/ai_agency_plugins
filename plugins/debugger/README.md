# debugger

Bug fixing, run backwards from the symptom to the mechanism. The plugin exists
to stop the default behaviour — spot something that looks wrong, change it,
hope — and replace it with a reproduction, a narrowed search, a proved cause,
and a test that fails without the fix.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `root-cause-analysis` | The method: reproduce, narrow, prove causation, fix the cause, verify |
| Skill | `regression-triage` | "It worked before": bracket, bisect, read the culprit commit |
| Command | `/diagnose` | Diagnose a symptom without touching code |
| Command | `/bisect` | Find the commit that introduced a regression |
| Command | `/fix` | Implement a fix for an already-proved cause, failing test first |
| Agent | `investigator` | Tests one hypothesis in a fresh context; returns a verdict, not a patch |
| Hook | `PostToolUse` | Notices when an edit swallows the failure instead of removing it |
| MCP | `debugger` | Dependency-free stdio server: `repro_command`, `change_history`, `bug_playbook` |

Progressive disclosure is the design. Each `SKILL.md` carries the method; the
references — `bug-classes.md`, `reproduction.md`, `verification.md`,
`bisect-recipes.md` — load only when the investigation reaches them.

## The scripts

Three things a model should never do by hand, because a script is cheaper and
does not miscount:

```bash
# what does this repo actually declare as its checks?
python skills/root-cause-analysis/scripts/repro.py --discover

# is the failure deterministic, or 3-in-10?
python skills/root-cause-analysis/scripts/repro.py --cmd "npm test -- cart" --times 10

# plan a bisect: range, steps, and the warnings that make bisects lie
python skills/regression-triage/scripts/git_bisect.py --good v1.4.0 --cmd "npm test -- cart"

# ... then run it
python skills/regression-triage/scripts/git_bisect.py --good v1.4.0 --cmd "npm test -- cart" --run

# who owns these lines, and what else landed in this file
python skills/regression-triage/scripts/history.py src/cart/total.ts --lines 40-90
```

`repro.py` exits 2 for "this repo declares no checks", 0 for a clean run, 1 for
a deterministic failure and 3 for an intermittent one — four different answers
that a single boolean would collapse.

`git_bisect.py` prints a plan and changes nothing until `--run`. It refuses a dirty
tree, always `git bisect reset`s in a `finally`, and runs the verdict by
re-invoking itself, so a `--setup` failure becomes exit 125 (skip) rather than
a commit wrongly marked bad — and so it works where `sh -c` is not on PATH.

## One home for a rule

The symptom-suppression patterns live in
`skills/root-cause-analysis/scripts/suppression.py`. The hook imports `scan`
from there rather than restating them, and the MCP server imports `discover`
and `commits`/`blame` from the skills' own scripts. There is one place to
correct a rule, and the server can never contradict the skill.

## Try it

```bash
python plugins/debugger/skills/root-cause-analysis/scripts/repro.py --discover

echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/debugger/mcp/server.py

python -m tools.apkit test --plugin debugger
```

## Install it

```bash
python -m tools.apkit build --plugin debugger
python -m tools.apkit install debugger --target claude-code --scope user
python -m tools.apkit install debugger --target agents --scope project --into ~/work/my-repo
```

`dist/<target>/debugger/INSTALL.md` says what each target got, what it did not,
and why.

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes skills, commands and agents; no hooks.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands; the
  `investigator` agent is emitted as a skill, so the method survives but the
  delegation does not; no hooks.
- **Generic `.agents/skills`** takes skills only — and the skills carry their
  own `scripts/`, so `repro.py`, `git_bisect.py` and `history.py` travel with them.
