---
name: requirements-analysis
description: Turns a prompt that describes what a plugin should do into numbered, testable requirements and a component plan — which skills, commands and agents cover each requirement, and whether a hook, an MCP server or scripts are actually needed — then presents the plan for approval before anything is built. Use when the user asks to plan, design or scope a plugin or agent, pastes requirements for one, or asks which components a plugin needs.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Requirements analysis

A plugin built straight from a prompt covers what the builder remembered of
the prompt. This skill makes the prompt into a contract first: a file of
requirements, each one checkable, and a plan where every component names the
requirements it covers and says why it is there. Everything later — the
scaffold, the tests, the gate, the audit — is checked against that file.

The file is `.plugin-dev/<name>/requirements.json` until the plan is approved,
then `plugins/<name>/requirements.json` for the life of the plugin.

## 1. Start the file with the prompt verbatim

```bash
python scripts/requirements.py new <name> --prompt-file <file>
python scripts/requirements.py new <name> --prompt "<pasted text>"
```

Pick the name from what the plugin does, lowercase-hyphenated. The script
refuses a name already taken under `plugins/`. The prompt is stored exactly as
given — the auditor later reads it and nothing else, so never paraphrase it.

## 2. Split it into requirements

Edit the `requirements` list. One requirement is one thing someone could check:

```json
{"id": "R3", "kind": "event",
 "text": "Warn before a commit that touches a migration file",
 "acceptance": "a PreToolUse event for `git commit` with a staged migrations/ file prints a warning; any other commit prints nothing"}
```

- **Split compound sentences.** "Triage and reply to recruiter messages" is
  two requirements, because either half can be missing.
- **Keep the user's words in `text`.** Interpretation goes in `acceptance`,
  where the user can see and correct it.
- **`acceptance` says what is observed**, not how it feels. "Works properly",
  "fast", "user-friendly" are refused by the check unless a number makes them
  testable.
- **`kind`** is the shape of the need, and it decides which components may
  cover it. Choose it honestly — see [component rules](references/component-rules.md).
  The kinds: `action`, `knowledge`, `computation`, `event`, `integration`,
  `isolation`, `constraint`.
- **Implied requirements count only if the prompt implies them.** "Tests for
  the scripts" is in almost every prompt; "a dashboard" is not, however useful
  it seems.

## 3. Ask, or assume and say so

A gap that would change which components exist, or what a component does, is
an `open_questions` entry. Ask at most three, together, and wait. Anything
else goes in `assumptions` as one sentence, so the user can overrule it from
the plan.

```bash
python scripts/requirements.py check .plugin-dev/<name>/requirements.json --root .
```

| Exit | Meaning | Do |
| --- | --- | --- |
| 0 | ready | plan the components |
| 1 | issues listed | fix the file; do not plan around them |
| 2 | unusable | the file is missing or not JSON — say so |
| 3 | open questions | ask them; do not guess the answers |

## 4. Plan the components

Fill `components`. Each entry has a `type`, a `name`, the `covers` list and a
`why` in one sentence. Scripts and tests are named by their path inside the
plugin; tests also list what they `verifies`.

```json
{"type": "hook", "name": "PreToolUse", "covers": ["R3"],
 "why": "a warning on every such commit cannot depend on the model remembering to check"}
```

Start from the requirements, not from a template. Walk the decision table in
[component rules](references/component-rules.md) for each requirement, and
choose the smallest set that covers them all. Copying the full set of
component types because `code-review` has them is the most common way a
plan goes wrong.

Then check coverage both ways with the `plugin-verification` skill's
`req_trace.py check <file>` (no `--plugin-dir` yet — nothing is built). Exit 0
means every requirement is covered and every component is justified. Fix
every gap it lists before presenting.

## 5. Present the plan and stop

Present, in this order, and nothing else:

1. **The requirements** — the table from `req_trace.py table <file>`, plus the
   assumptions.
2. **The directory tree** of `plugins/<name>/`, one line of purpose per file.
3. **Components and why** — including every component type left out, and why
   it was not needed. "No MCP server: nothing here is used by another agent or
   an outside system" is part of the plan.
4. **The build flow** — scaffold, write, test, gate, audit.
5. **One question:** approve, or what to change.

Write nothing under `plugins/` until the user approves. If they change the
plan, edit the file, re-run both checks, and present again.
