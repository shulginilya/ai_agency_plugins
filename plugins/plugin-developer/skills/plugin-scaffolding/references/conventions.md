# Conventions

Rules the plugins in this repo settled the hard way. A generated plugin
follows all of them; the reason is given so the rule can be applied to a case
it does not name.

## Scripts

- **Answer more than pass/fail.** Exit 0 is the pass. Give the failure its own
  code, and give "the input is unusable" and "cannot tell" their own codes too.
  "The suite collected zero tests" or "no scope was declared" are questions for
  the user, not passes and not failures.
- **One home for a rule.** The rule lives in the skill's script. The hook and
  the MCP server put that directory on `sys.path` and import it. A rule
  restated in two places ends up disagreeing with itself.
- **Standard library only, Python 3.9+.** `from __future__ import annotations`;
  no `X | Y` at runtime, no `tomllib`, no `match`.
- **Check the file name against the standard library** before putting its
  directory on `sys.path`. `bisect.py` shadowed `bisect`; `trace.py` would
  shadow `trace`.
- **Ask git for a ref, not its prose.** Porcelain messages change between
  versions and locales. Use `--absolute-git-dir`, never `--git-dir`.
- **Writes back up first and refuse malformed input.** Copy to `.bak` before
  rewriting a user's file; refuse to overwrite a file that is not what the
  script expects.
- **State is JSON; markdown is rendered from it, one way.** A file parsed back
  out of prose loses an entry eventually.
- **Dates come from the user.** Refuse "next week"; the skill converts it and
  says which date it used.

## Hooks

- **Silent unless there is something to say.** A hook that speaks every
  session gets ignored. Decide the silent case first.
- **Always exit 0.** A hook that fails blocks work the user asked for, and the
  failure is hard to trace back to the hook.
- **Earn it.** A hook is for a rule prose cannot enforce at the moment it
  matters. If a command would do, it is a command.

## MCP servers

- **Survive your own tools.** Catch `(Exception, SystemExit)` in `tools/call`
  and answer `isError`.
- **No SDK.** A stdlib stdio server is portable; a package the user has to
  install first is not.

## Layout

- **Skill-level `scripts/` travel to every harness; plugin-level `scripts/`
  only to bundle targets.** Anything a non-Claude-Code harness must run belongs
  in a skill's own `scripts/`; only hook entry points belong at plugin level.
- **Cross-skill imports are fine, with a fallback.** Reach
  `Path(__file__).resolve().parents[2] / "<sibling>" / "scripts"` and wrap the
  import in `try/except ImportError`.
- **Never link across skills by relative path in prose.** Name the sibling
  skill instead.

## Behaviour

- **External CLIs are read-only by default.** Propose `gh` writes, sending a
  message, or anything else done on the user's behalf; do not execute it
  without approval.
- **The user's state lives in the user's project** (`.plugin-dev/`), not
  inside the plugin.
