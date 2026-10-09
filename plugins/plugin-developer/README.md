# Plugin Developer

Builds an agent plugin from a requirements prompt. It splits the prompt into
testable requirements, maps each one to the component that covers it, and
stops for your approval. After that it scaffolds and writes the plugin, writes
its tests, and runs a gate that validates, builds, loads and tests it. A
separate auditor that never saw the plan then checks the result against the
original prompt.

```
/plan-plugin  <requirements text or file>   plan only — requirements, components, why — then stop
/build-plugin <requirements or plan name>    plan → approval → build (fresh context) → gate → audit
/check-plugin <name> [--audit]               re-run the gate on any plugin under plugins/
```

## How a prompt becomes a plugin

1. **Intake.** `requirements.py new` stores the prompt verbatim in
   `.plugin-dev/<name>/requirements.json`. The prompt is split into
   requirements, each with a kind and an acceptance test. `requirements.py
   check` refuses an acceptance test nobody could check, and holds the plan
   while questions are open.
2. **Plan.** Each requirement gets the component its kind calls for
   (`references/component-rules.md`). `req_trace.py check` enforces coverage
   in both directions. A hook must cover an `event` requirement and an MCP
   server an `integration` one, and every script and server needs a test.
3. **Approval.** You see the requirements, the tree, the components and why,
   and what was left out. Nothing is written under `plugins/` until you
   approve.
4. **Build** (the `plugin-developer` agent). `scaffold.py` creates exactly the
   planned components as marked stubs and opens a build session. The agent
   writes scripts and tests first, then everything else.
5. **Gate.** `gate.py run` checks, in order:
   1. no stub is left
   2. coverage holds
   3. the README table is current
   4. `apkit validate --strict`
   5. `apkit build`, with what each harness cannot express recorded
   6. `claude plugin validate --strict`
   7. the plugin loads under `--plugin-dir`
   8. `claude plugin details` lists what the source declares
   9. the tests pass
   10. any MCP servers answer and survive their tools

   The fix loop is capped at three rounds.
6. **Audit** (the `requirements-auditor` agent). It gets the original prompt
   and the plugin directory, nothing else, and reports anything not covered,
   covered in name only, not asked for, or misread.

The Stop hook holds an open build session to the gate. The session cannot
end on a gate that is missing, failing or older than the last edit without
one more attempt.

## Gate results

`PASS`, `FAIL at <step>`, or `INCOMPLETE`. Incomplete means nothing failed but
a step could not run here. This is usually because the `claude` CLI is missing
or restricted to `claude -p` (as in the Claude desktop VM). Point the gate at a
working CLI with `--claude <path>` or `PLUGIN_DEV_CLAUDE`.

## Components and why

<!-- plugin-developer:components -->
| Component | Type | Covers | Why |
| --- | --- | --- | --- |
| `requirements-analysis` | skill | R2, R4, R7 | How to turn a prompt into checkable requirements and choose the components they need; holds the decision table that keeps hooks, MCP servers and scripts out unless earned. |
| `plugin-scaffolding` | skill | R1, R12 | How to write each component in the repo's portable format, following the conventions the existing plugins settled. |
| `plugin-verification` | skill | R3, R5, R6, R11 | What 'done' means: the gate, the fix loop, and how to report a step that could not run. |
| `plan-plugin` | command | R7 | Planning is a separate, user-started step so approval happens before any plugin file exists. |
| `build-plugin` | command | R1, R10 | The entry point: plans if needed, waits for approval, hands the build to the agent, then runs the audit. |
| `check-plugin` | command | R11 | Re-runs the gate after manual edits, and on plugins the developer did not build. |
| `plugin-developer` | agent | R1, R10 | The build writes and re-checks many files; a fresh context keeps that noise out of the conversation. |
| `requirements-auditor` | agent | R9 | Checks the result without having seen the build, catching a misread prompt or coverage that is only claimed. |
| `Stop` | hook | R8 | 'Not done until the gate passes on the final files' is a rule prose cannot enforce. |
| `skills/requirements-analysis/scripts/requirements.py` | script | R2, R3 | Checks the requirements file mechanically: ids, kinds, checkable acceptance, open questions. |
| `skills/plugin-scaffolding/scripts/scaffold.py` | script | R1, R3 | Creates exactly the planned components, each stubbed with a marker the gate refuses. |
| `skills/plugin-verification/scripts/req_trace.py` | script | R3, R4, R5 | The two-way coverage check, and the README table rendered from requirements.json. |
| `skills/plugin-verification/scripts/gate.py` | script | R6, R8, R11 | Runs every check in order, records the result and its fingerprint, and owns the freshness rule the hook uses. |
| `skills/plugin-verification/scripts/mcp_smoke.py` | script | R5, R6 | Starts a generated MCP server and proves it answers and survives its own tools. |
| `scripts/stop_gate.py` | script | R8 | The Stop hook's entry point; imports gate.freshness rather than restating it. |
| `tests/test_scripts.py` | test | - | Every script and the hook, against temporary repos and literal CLI output. |

| Requirement | Kind | Covered by |
| --- | --- | --- |
| **R1** Take a requirements prompt (pasted text or a file) and build a plugin from it | action | `plugin-scaffolding`, `build-plugin`, `plugin-developer`, `skills/plugin-scaffolding/scripts/scaffold.py` |
| **R2** Split the prompt into atomic requirements, each with a kind and an acceptance test; ask the user about gaps that change the plugin and record the rest as assumptions | knowledge | `requirements-analysis`, `skills/requirements-analysis/scripts/requirements.py` |
| **R3** Every requirement maps to a component that covers it, and every component maps back to a requirement with a stated reason | computation | `plugin-verification`, `skills/requirements-analysis/scripts/requirements.py`, `skills/plugin-scaffolding/scripts/scaffold.py`, `skills/plugin-verification/scripts/req_trace.py` |
| **R4** Include hooks, an MCP server and scripts only when a requirement needs them | constraint | `requirements-analysis`, `skills/plugin-verification/scripts/req_trace.py` |
| **R5** Ship tests for the scripts and the MCP server whenever either exists, and make them pass | computation | `plugin-verification`, `skills/plugin-verification/scripts/req_trace.py`, `skills/plugin-verification/scripts/mcp_smoke.py` |
| **R6** A built plugin installs cleanly | computation | `plugin-verification`, `skills/plugin-verification/scripts/gate.py`, `skills/plugin-verification/scripts/mcp_smoke.py` |
| **R7** Present the planned structure (tree, one-line purpose per component, the build flow) and stop for approval before writing plugin files | action | `requirements-analysis`, `plan-plugin` |
| **R8** A build cannot be reported finished while its checks are failing or older than the latest edit | event | `Stop`, `skills/plugin-verification/scripts/gate.py`, `scripts/stop_gate.py` |
| **R9** An independent check that the built plugin does what the original prompt asked | isolation | `requirements-auditor` |
| **R10** The long build runs in its own context, so the conversation keeps only the plan and the report | isolation | `build-plugin`, `plugin-developer` |
| **R11** Re-run the checks on an existing plugin | action | `plugin-verification`, `check-plugin`, `skills/plugin-verification/scripts/gate.py` |
| **R12** Generated plugins use this repo's portable source format and conventions; scripts are standard-library Python 3.9+ | constraint | `plugin-scaffolding` |
<!-- /plugin-developer:components -->

## Not included

- **MCP server.** Every operation is a local command the agent already runs
  through Bash, and nothing outside this repo needs these as structured tools.
- **Evals.** `claude plugin eval` was considered and deferred. A per-PR bar
  should be deterministic, and each eval case of this plugin builds a whole
  plugin several times over.
