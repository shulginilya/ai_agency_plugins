---
description: Show or change your training settings — stack, interview coding languages, cadence, focus, minutes, goals, weak areas, interview date, and where the training is kept.
argument_hint: "[e.g. \"stack React,TypeScript,Node,Python,Go\", \"interview-languages Node,Python,React\", \"cadence weekly\"]"
model: sonnet
allowed_tools: Bash(python:*) Read
---

Training settings: {{ARGS}}

With no arguments, run `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" config show` and `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" where`, and list the settings
with their values.

Otherwise apply each change with `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" config set KEY VALUE`:

| Key | Value |
| --- | --- |
| stack | comma-separated, e.g. `React,TypeScript,Node,Python` |
| interview-languages | comma-separated, e.g. `Node,Python,React`. Algorithm drills rotate through the languages; a framework such as React adds UI-build drills |
| cadence | `daily` or `weekly` |
| focus | `skills`, `interview` or `mixed` |
| daily-minutes / session-minutes | 10–240 |
| weekly-sessions | 1–4 |
| goals | semicolon-separated |
| weak-areas | comma-separated areas, stack entries or topic ids |
| interview-date | `YYYY-MM-DD` or `none` |

To move the training folder, run `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" set-home "<path>"`. Windows paths are
fine. Say that the existing `state.json` has to be moved there too, or offer to
copy it.

History is kept across every change. After changing stack, focus or cadence,
show the new plan with `python "{{PLUGIN_ROOT}}/skills/training-plan/scripts/trainer.py" plan --write`.
