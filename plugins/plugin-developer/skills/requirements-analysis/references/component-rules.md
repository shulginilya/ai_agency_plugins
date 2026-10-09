# Component rules

Which component covers which kind of requirement, and what does not justify
a component. `req_trace.py` enforces the rows marked **enforced**; the rest is
judgement, and the plan's `why` column is where that judgement is shown.

## Kinds

| Kind | The requirement is… | Example |
| --- | --- | --- |
| `action` | something the user starts on purpose | "plan a sprint", "draft a reply" |
| `knowledge` | expertise or a procedure the model should apply when it is relevant | "review against our security checklist" |
| `computation` | a calculation, parse, check or saved state that must come out the same every time | "score a posting against the profile", "keep a ledger" |
| `event` | must happen on a lifecycle event, whatever the model decides | "warn before a commit that touches migrations" |
| `integration` | an outside system, or a structured tool another agent or harness calls | "read issues from the tracker", "expose the score to other agents" |
| `isolation` | work that needs a clean context or an independent judgement | "grade the interview without seeing the prep" |
| `constraint` | a property every component must keep | "stdlib only", "never send without approval" |

## Which component covers which kind

| Component | Covers | Rule |
| --- | --- | --- |
| skill | knowledge, and the procedure behind an action | the default home for *how* to do something |
| command | action | one per thing the user starts; it routes to a skill rather than restating it |
| agent | isolation | only when a clean context changes the result — a reviewer, an auditor, a long noisy job |
| hook | event | **enforced**: must cover an `event` requirement |
| MCP server | integration | **enforced**: must cover an `integration` requirement |
| script | computation, integration, event | **enforced**: must cover one of these kinds |
| test | — | **enforced**: every script and MCP server is verified by a test that names it |

A `constraint` is covered by the components that keep it, and checked by the
gate (`apkit validate`, the tests).

## What does not earn a component

- **A hook for something the user starts.** That is a command. A hook is for
  the moment nobody is thinking about the rule — the edit, the commit, the
  end of the session.
- **A hook that speaks every session.** If it cannot stay silent when there is
  nothing to say, it will be ignored by the second day. Plan the silent case
  in the `why`.
- **An MCP server that wraps a script the agent can already run.** Use an MCP
  server when another agent, another harness without a shell, or an outside
  system needs a structured tool. Otherwise the script is enough.
- **A script for judgement.** "Decide whether the reply is polite" is a skill.
  A script is for what must give the same answer twice.
- **An agent for a short task.** A subagent costs a cold start and loses the
  conversation. Use one when not having seen the work is the point.
- **A command per skill.** Commands exist for what users start; a skill the
  model should pick up on its own does not need one.
- **Anything because the reference plugin has it.** `code-review` exercises
  every component type on purpose. That is a demo, not a mandate.

## Choosing between two that both fit

- action **and** knowledge → a command that follows a skill. The command holds
  the entry point and its argument handling; the skill holds the method.
- computation **and** event → a script with the rule, and a hook that imports
  it. One home for the rule.
- computation **and** integration → a script with the logic, and an MCP tool
  that imports it. Never restate the rule in the server.
