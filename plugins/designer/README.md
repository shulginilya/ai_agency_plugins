# designer

The crew's UI/UX designer. It specifies a screen before it is built and
reviews it after: every state the user can hit, the copy they read, whether
they can use it with a keyboard, and whether it matches the rest of the
product. It works from the repository and the running app, with no outside
accounts, so it also works for unattended crewmates.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `design-spec` | Flow, every screen state, layout, copy, accessibility and acceptance criteria for one ticket; optional HTML wireframe |
| Skill | `ux-review` | Usability, WCAG 2.2 AA and design-system review, findings ranked by harm |
| Command | `/spec` | Write the design spec for a ticket and attach it |
| Command | `/review` | Review a flow, screen or UI diff |
| Agent | `first-time-user` | Walks one flow in a fresh context knowing only what the screens say |

It doesn't manage tickets. Specs and findings that need a ticket are handed to
developer or scrum-master, the only crew members that manage them.

There are no hooks. A crew plugin's hooks would run in every crewmate session,
and nothing here needs one.

Two scripts carry the checks, both standard-library Python:

- `skills/ux-review/scripts/ui_inventory.py` finds the UI stack, where the
  design tokens are defined, the component directories, the page and route
  files, and the theming signals. It exits 2 when the repository has no UI.
- `skills/ux-review/scripts/contrast.py` gives the WCAG 2.x contrast ratio for
  a color pair, or a file of pairs, and the AA and AAA marks each one meets.
  It exits 1 if any pair fails AA for normal text.

The detail lives in references that load on demand: `heuristics.md`
(Nielsen's ten as yes/no checks, plus the states to force),
`wcag-checklist.md` (the WCAG 2.2 AA criteria product UI fails most, each with
a quick test), and `spec-template.md` (the spec to paste into a ticket).

## Try it

```bash
python plugins/designer/skills/ux-review/scripts/ui_inventory.py --root ~/work/my-app
python plugins/designer/skills/ux-review/scripts/contrast.py "#767676" "#ffffff"
python -m tools.apkit test --plugin designer
```

## Install it

It is a crew plugin: `integrations/firstmate/deploy.sh --with-plugins` installs
it with the others. On its own:

```bash
python -m tools.apkit build --plugin designer
python -m tools.apkit install designer --target claude-code --scope user
```

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes the skills, commands and the `first-time-user` agent.
- **Codex CLI, Cursor, Gemini CLI** take the skills and commands.
  `first-time-user` becomes a skill, so its walk-through survives but the
  fresh context does not. Run it after clearing the conversation, or in a new
  session.
- **Generic `.agents/skills`** takes the skills only. Both scripts travel with
  `ux-review`.
