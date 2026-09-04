# Architecture

Diagram: [`architecture.drawio`](architecture.drawio) — three pages: the pipeline,
the support matrix, and the `apkit` lifecycle. Open with draw.io / diagrams.net or
the VS Code Draw.io Integration extension.

Three stages, one direction. Nothing downstream ever writes back upstream.

```
plugins/<name>/            targets/<harness>.json            dist/<harness>/<name>/
  plugin.json                 paths + dialects        →        the harness's own layout
  skills/<s>/SKILL.md    ─────────────────────────────→        ↓
  commands/<c>.md              tools/apkit/build.py            tools/apkit/install.py
  agents/<a>.md                                                        ↓
  hooks/hooks.json                                        ~/.claude/skills, .agents/skills,
  mcp/servers.json                                        .cursor/, .opencode/, .gemini/
```

## Stage 1 — source

`plugins/<name>/` holds the plugin in its portable form. Skills are already
written to the [Agent Skills spec](https://agentskills.io/specification), so
they need no translation at all; everything else is written once in a neutral
dialect and translated on the way out.

The neutral dialects:

| Component | Source form | Portable bits |
| --- | --- | --- |
| Skill | `skills/<name>/SKILL.md` | spec frontmatter only |
| Command | `commands/<name>.md` | frontmatter + `{{ARGS}}`, `{{ARG1}}`, `{{ARG2}}` |
| Agent | `agents/<name>.md` | frontmatter + prose body |
| Hook | `hooks/hooks.json` | Claude Code's schema (nothing else has one) |
| MCP | `mcp/servers.json` | standard server objects, `{{PLUGIN_ROOT}}` for paths |

## Stage 2 — build

`apkit build` reads a target manifest and projects the source onto it. Each
component gets one of four fates, declared by the manifest, never guessed:

- **native** — the harness has this concept; render it in that harness's dialect
- **emulated** — the harness lacks it, but something close exists. Today that
  means subagents rendered as skills, with a preamble explaining the
  substitution so the prompt still reads correctly inline.
- **manual** — the config belongs in a file this tool refuses to rewrite (Codex's
  `config.toml`). A snippet is emitted, and the build says so.
- **unsupported** — nothing sensible exists. The component is dropped, the
  reason is printed at build time and written into `dist/.../INSTALL.md`.

The last point is the design's whole argument. A cross-harness build that
quietly drops your hooks is worse than no build at all, because you will not
find out until the thing you thought was enforced was not.

## Stage 3 — install

`apkit install` copies (or symlinks) a built bundle into the directories a
harness actually reads, per the `install` block of the target manifest. Two
scopes: `user` (a home-directory path) and `project` (relative to `--into`, or
the current directory).

Three placement modes:

- `bundle` — the whole built directory becomes one installed plugin. Claude
  Code's `~/.claude/skills/<plugin>/` works this way.
- `children` — each child of a component directory is placed individually.
  This is how skills reach `.agents/skills/`.
- `merge-json` — the emitted config is merged into an existing file under one
  key, the previous file is backed up as `*.apkit.bak`, and a file that is not
  valid JSON is refused rather than overwritten.

Every install is recorded in `.apkit.local.json` (gitignored) so `apkit
uninstall` can undo exactly what was done. Merged config entries are reported
rather than removed — unpicking someone's hand-edited config is not a thing a
tool should do unasked.

## Why the adapters are data

Harness conventions drift: a path moves, a placeholder changes spelling, a new
tool adopts `.agents/skills`. If those live in Python, every drift is a code
change, a review and a release. In `targets/*.json` they are a one-line edit
that `apkit doctor` can check against the machine in front of you.

Python only appears where an output *format* differs — Gemini's TOML commands,
OpenCode's MCP shape, Codex's config snippet. There are five such renderers in
`tools/apkit/render.py`, and a new harness usually needs none of them.

## Trust and drift

Each component mapping carries a `verified` flag. `true` means it was checked
against that harness's own documentation; `false` means it is a best-effort
guess. `apkit targets` and `apkit doctor` surface the unverified ones, and the
build writes them into `INSTALL.md`. When you confirm a mapping against a live
harness, flip the flag — that is the repo's record of what is actually known.
