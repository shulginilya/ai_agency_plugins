---
name: plugin-verification
description: Decides whether a plugin under plugins/ is done — every requirement traced to a component and every component to a requirement, no stub left, valid and buildable for every harness, loadable by Claude Code with the components its source declares, tests passing, MCP servers answering — and drives the fix loop until it is or says exactly why not. Use when a plugin has been built or edited, when asked whether a plugin is finished, installs cleanly or covers its requirements, or to re-check an existing plugin.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Plugin verification

"Done" is a gate result, not an impression. Run it on the final files, and
report what it says.

## 1. Run the gate

```bash
python scripts/gate.py run <name>
```

Run it from anywhere inside the repo. It runs these steps in order, stops at
the first failure, and writes `.plugin-dev/<name>/gate.json` with a
fingerprint of the plugin's files:

| Step | Checks |
| --- | --- |
| markers | no `TODO(plugin-developer)` stub is left |
| trace | `scripts/req_trace.py check` against the plugin on disk |
| readme | the README's components table matches `requirements.json` |
| validate | `apkit validate --plugin <name> --strict` |
| build | `apkit build --plugin <name>`, with what each harness cannot express recorded |
| claude-validate | `claude plugin validate dist/claude-code/<name> --strict --json` |
| load | `claude --plugin-dir dist/claude-code/<name> plugin list --json` shows `<name>@inline` enabled |
| inventory | `claude plugin details` lists every skill, command, agent, hook event and MCP server the source declares |
| tests | `apkit test --plugin <name>` |
| mcp | `scripts/mcp_smoke.py`: each server starts, lists its tools and survives calling each one |

| Exit | Result | Meaning |
| --- | --- | --- |
| 0 | pass | every step passed |
| 1 | fail | a step failed; its output is printed |
| 2 | unusable | not in the repo, or the plugin does not exist |
| 3 | incomplete | nothing failed, but a step could not run here |

**Incomplete is not pass.** It usually means the `claude` CLI is missing or
restricted to `claude -p` on this machine, so the three Claude Code steps
did not run. Report which steps were not checked and where they can be run
(`--claude <path>` or `PLUGIN_DEV_CLAUDE` points the gate at another CLI).
Never describe an incomplete gate as a clean install.

## 2. Fix what failed, at the cause

Read the failing step's output and fix the source in `plugins/<name>/`, never
`dist/`.

- **trace** — a gap in coverage is a plan problem before it is a file
  problem. A requirement not covered: add the component, or ask whether the
  requirement was misread. A component not justified: remove it, or name the
  requirement that needs it. Change `requirements.json` first, then the
  files, then re-render the README with
  `scripts/req_trace.py table <plugin>/requirements.json --write-readme <plugin>/README.md`.
- **validate / claude-validate** — frontmatter. Names must equal file and
  directory names; descriptions must say when to use it; `--strict` fails
  unknown keys, so keep traceability in `requirements.json`, never in
  frontmatter.
- **inventory** — something in the source never reached Claude Code: a file
  in the wrong directory, or a mapping in `targets/claude-code.json` that drops
  it. Check `dist/claude-code/<name>/` before changing the source.
- **tests** — fix the code, not the assertion, unless the assertion contradicts
  the requirement's acceptance test. Then the requirement decides.

Re-run the whole gate after each fix. A step that passed before an edit has
not passed after it.

**Three fix loops, then stop.** If the gate still fails after three rounds,
stop editing. Report the failing step, its output, and what you tried, then
close the session with `scripts/gate.py close <name> --abandon`. A precise
failure report is a result; a fourth blind attempt is not.

## 3. Close the session

```bash
python scripts/gate.py close <name>
```

Refused while the gate is failing or stale. A Stop hook enforces the same
rule: while a build session is open, the session will not end on a missing,
failing or stale gate without one more attempt.

## 4. Report

```
Plugin: plugins/<name>  (version)
Gate: PASS | INCOMPLETE (not checked here: <steps>) | FAIL at <step>
Requirements: <n>, all covered | <gaps>
Components: <type: names>
Not included: <component types left out, and why>
Other harnesses: <degradations from the build step, one line each>
```

Then the audit, when one was run — see the `requirements-auditor` agent.

To check a plugin that predates this workflow and has no `requirements.json`,
run the gate anyway: the trace step fails with "cannot read", which is the
honest answer. Offer to write its requirements file from its README.
