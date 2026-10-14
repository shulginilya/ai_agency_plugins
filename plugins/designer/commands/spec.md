---
description: Write the design spec for a ticket — flow, every screen state, layout, copy, accessibility and acceptance criteria — and attach it to the ticket.
argument_hint: "[issue number, URL, or a description of the screen or flow]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Read Grep Glob Write
---

Spec the design for: {{ARGS}}

If that is empty, ask which ticket or screen to design.

Follow the `design-spec` skill:

1. Read the ticket whole (`gh issue view <n> --comments`), and restate the user,
   the job and what done looks like in one sentence. If you can't, ask and stop.
2. Find what exists:
   `python {{PLUGIN_ROOT}}/skills/ux-review/scripts/ui_inventory.py --root .`, then open
   the closest existing screen and its shared components.
3. Write the flow, then each screen with the template in the skill's
   references: layout and breakpoints, components and tokens by name, every
   state, final copy, and accessibility.
4. Add a low-fidelity HTML wireframe under `docs/design/` only when layout is
   the hard part.
5. End with testable acceptance criteria. Hand the spec over without writing
   to the ticket yourself: give it in your reply or report, ready to paste under
   `## Design`, for the developer or scrum-master to attach.
