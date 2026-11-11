# crew diagrams

The crew is the `crew` plugin (the workflow, owned by no role) plus the role
plugins listed under `crew` in `team.json`: developer, scrum-master, designer,
qa, devops and code-reviewer. A session in a repository with a crew board is
pointed at the `crew-workflow` skill, which routes every step to a crew command.
This folder draws that crew.

## Diagrams

Three diagrams are generated from this folder and the repo. CI regenerates them on
`main` after each merge, so a branch never commits them (the `generated-files` check
fails if one does):

| Diagram | Script | Hand-kept half |
| --- | --- | --- |
| `docs/crew/team.drawio`: who does what, the RACI matrix, a worked example | `team_diagram.py` | `team.json` |
| `docs/crew/lifecycle.drawio`: a ticket's columns, who moves it between them, and the ways back | `lifecycle_diagram.py` | `lifecycle.json` |
| `docs/crew/skills.drawio`: every skill, the plugin that owns it, what loads it and what it hands off to, and the model and effort each command and subagent pins | `skills_diagram.py` | none: all read from `plugins/` and `team.json` |

Who is crew is the keys of `crew` in `team.json`, in order. What each crew plugin is
routed for, and the rules every session keeps, come from the `## Routing` and
`## Rules for every session` sections of
`plugins/_shared/skills/crew-workflow/SKILL.md`. To add a plugin to the crew, add it
under `crew` in `team.json` and give it a routing line in that skill;
`tests/test_team_diagram.py` fails until both are there.

When the ticket lifecycle changes (a column in board-setup's `DEFAULT_COLUMNS`, or a
plugin command that moves cards with `board.py move` or `tickets.py ... --status`),
update `lifecycle.json` in the same PR. `tests/test_lifecycle_diagram.py` runs the
generator with `--strict` and fails on any drift. The warning names the column or the
command and plugin to describe. Preview with
`python integrations/crew/lifecycle_diagram.py --out /tmp/x`.

The skills diagram needs no hand-kept file: add a skill, command or subagent, or
change a `model:`/`effort:` pin, and CI redraws it. `tests/test_skills_diagram.py`
runs it with `--strict`, which fails when a command names no skill or subagent, a
command or subagent pins no model, or a plugin uses a shared skill its
`plugin.json` does not list in `shared_skills`. Preview with
`python integrations/crew/skills_diagram.py --out /tmp/x`.

## Install the crew

From the repo root, for Claude Code at user scope:

```bash
python -m tools.apkit build
for p in crew developer scrum-master designer qa devops code-reviewer; do
  python -m tools.apkit install "$p" --target claude-code
done
```

Install Captain-only plugins (every other plugin under `plugins/`) the same way when
you want them in your own sessions. They are not part of the crew, and the
crew-workflow skill routes no ticket work to them.
