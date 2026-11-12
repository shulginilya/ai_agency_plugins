# ai_agency_plugins

Harness-agnostic agent plugins. Author once in a portable source format, build
per-harness bundles, install into whichever agent you happen to be using.

Targets out of the box: **Claude Code**, **Codex CLI**, **Cursor**,
**OpenCode**, **Gemini CLI** — plus a generic `.agents/skills/` bundle that any
Agent Skills–compatible tool can pick up.

---

## Why a build step

Every harness agrees on one thing and disagrees on everything else.

| Concern | Portable? | Reality |
| --- | --- | --- |
| Skills | ✅ yes | [Agent Skills open standard](https://agentskills.io/specification) — `SKILL.md` in a folder. Read from `.agents/skills/` by Codex, Cursor, OpenCode, Gemini CLI. |
| MCP servers | ⚠️ mostly | Same server shape, five different config files. |
| Slash commands | ❌ no | Markdown here, TOML there, different argument placeholders. |
| Subagents | ❌ no | Claude Code has them as first-class files; most others don't. |
| Hooks | ❌ no | Claude Code only, at this level of fidelity. |

So: one canonical source of truth per plugin, and thin, **declarative**
adapters (`targets/*.json`) that project it into each harness's dialect. When a
harness changes a path or a placeholder, you edit data, not code.

## Layout

```
.
├── plugins/                  # ← source of truth. One directory per plugin.
│   ├── _template/            #   copy this to start a new plugin
│   └── scrum-master/         #   the reference plugin (see below)
├── targets/                  # declarative harness manifests (paths, dialects)
├── tools/apkit/              # the CLI: validate · build · pack · install · doctor
├── tools/install.sh          # install many plugins into many harnesses
├── tools/pack.sh             # pack plugins into archives to hand over
├── dist/                     # build output, gitignored, one dir per target
├── docs/                     # architecture, authoring guide, harness matrix
└── .claude-plugin/           # generated Claude Code marketplace manifest
```

## Quick start

```bash
python -m tools.apkit validate            # lint every plugin against the spec
python -m tools.apkit build               # → dist/<target>/<plugin>/
python -m tools.apkit build --target codex --plugin scrum-master
python -m tools.apkit install scrum-master --target cursor --scope user
python -m tools.apkit pack --plugin scrum-master --target claude-code
python -m tools.apkit doctor              # what's installed where, on this machine
python -m tools.apkit marketplace         # regenerate the marketplace index
python -m tools.apkit docs                # rebuild docs/handbook.pdf from source
```

Two wrappers do the batch versions of that, since one plugin into one harness
per command is rarely what you want:

```bash
tools/install.sh --all                    # build and install everything locally
tools/pack.sh --all -T                    # one archive per plugin per harness
tools/pack.sh developer -o ~/Desktop      # a .plugin file to upload by hand
```

No third-party dependencies. Python 3.9+, standard library only.

Install the console script if you'd rather type `apkit`:

```bash
pip install -e .
apkit build
```

## The reference plugin: `scrum-master`

`plugins/scrum-master/` is a working plugin that exercises every component type
the format supports, so the `apkit` tests build, install, pack and validate it,
and the docs use it as the worked example:

- **skills** — `backlog-refinement` (the Definition of Ready and the refinement
  loop, with references loaded on demand) and `sprint-planning`, plus the
  shared `ticket-management` skill from `plugins/_shared/skills/`
- **commands** — `/refine`, `/plan-sprint` and `/backlog-health`, rendered into
  each harness's command dialect
- **agent** — a `story-splitter` subagent (Claude Code; degrades to a skill elsewhere)
- **hook** — a `SessionStart` hook that prints the active sprint (Claude Code only)
- **mcp** — a dependency-free stdio server (`backlog`, `readiness_check`,
  `scrum_checklist`), projected into each harness's MCP config
- **scripts** — `ready.py`, `backlog.py` and `capacity.py`,
  real helpers the skills call

Build it and diff the outputs to see exactly what each adapter does:

```bash
python -m tools.apkit build --plugin scrum-master
find dist -type f | sort
```

## Starting a new project with the crew

The crew's process lives in the `crew` plugin, which belongs to no role:
removing a role plugin removes only that role's commands, never the workflow.

Open a session in the project's repository. A GitHub repository with no crew
board gets a question in the session's first reply: create one, and what to call
it? Say yes and the session runs `/crew:create-board`, which creates the
board with the crew's columns and the `skip_approval` label, and follows the
`crew-workflow` skill from then on. Say no and that repository is never asked
about again (the session records it; `crew_context.py --forget` undoes it).
Sessions nobody is watching are never asked: any run with
`CREW_UNATTENDED=1` set, such as a scripted `claude -p`. From
then on, every new session in a repository with a crew board is told to follow
the `crew-workflow` skill, so "do ticket #N" runs `/qa:plan`, `/developer:implement`,
`/developer:ship` and `/code-reviewer:review`, and stops at In approval for you.
Nothing workflow-related is added to the project's repository.

## Docs

- [Handbook (PDF)](docs/handbook.pdf) — every slash command, plugin, agent,
  skill, MCP tool, hook and integration, plus the harness matrix and CLI
  reference. Generated: rebuild with `python -m tools.apkit docs` (needs
  Chrome, Edge or Chromium; `--browser PATH` if it is not found)
- [Architecture](docs/architecture.md) — how source → build → install works
  (diagram: [`docs/architecture.drawio`](docs/architecture.drawio))
- [Authoring guide](docs/authoring-skills.md) — writing portable skills that
  actually trigger
- [Harness matrix](docs/harness-matrix.md) — every path and dialect, per target
- [Plugin format](docs/plugin-format.md) — the `plugin.json` schema
- [Release](docs/release.md) — versioning, marketplace, CI

## License

MIT — see [LICENSE](LICENSE).
