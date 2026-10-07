---
project: apkit / ai_agency_plugins
slug: apkit
links: {}
period: 2026-09 – 2026-10
role: Solo — design, build, CI, plugins
confidential: false
sources: [/home/ilya-shulgin/web_projects/ai_agency_plugins, user]
---

# apkit — one plugin source for every AI coding agent

**A build tool and plugin library that let me write an AI agent workflow once and install it into Claude Code, Codex CLI, Cursor, OpenCode and Gemini CLI.**

## The problem
Every AI coding agent can be extended with skills, slash commands, subagents,
hooks and MCP servers, but each one reads them from a different place and in a
different format: Markdown commands here, TOML there, subagents as first-class
files in one tool and absent in the next. Keeping the same workflows in sync by
hand across several agents meant copying files and fixing paths each time
something changed. Copies drifted, and features one agent couldn't support
went missing without any warning.

## What I did
A solo personal project: I designed and built the build tool, the plugins and the CI.
I worked with AI coding agents (Claude Code) throughout, and ran the plugins on
this repo while building them.
- Designed a single portable plugin format built on the open Agent Skills spec,
  with one source directory per plugin as the only source of truth.
- Built `apkit`, a standard-library Python CLI with no runtime dependencies
  that validates, builds, packs, installs and diagnoses plugins across 6 build
  targets.
- Made the per-agent adapters declarative: paths, formats and argument
  placeholders live in `targets/*.json`, and Python code exists only where an
  output format genuinely differs (TOML commands, MCP config for Codex).
- Made degradation explicit: when an agent cannot express a component, the
  adapter declares it `unsupported` and the build reports it instead of
  dropping it silently.
- Wrote 9 working plugins (developer, debugger, code-review, scrum-master,
  pair-programmer, prompt-engineer, job-hunter, interview-prep,
  recruiter-inbox), and integrated them with the firstmate multi-agent crew
  tool so its agents use them automatically.

## How it works
A plugin is a folder of skills, commands, subagents, hooks and an MCP server.
`apkit build` validates it against the spec, then each target manifest
projects it into that agent's dialect under `dist/<target>/<plugin>/`.
Subagents become skills on agents that lack them, and MCP servers are merged
into each agent's own config file. `apkit install` places a bundle at user or
project scope and records what it put where, so an uninstall can remove exactly
that. The hard part was that the five agents agree only on skills. The fix was
to treat each agent's quirks as data in its manifest, so when an agent changes
a path or a placeholder, I edit JSON, not code.

## Results
- 9 plugins, containing 25 skills, 31 slash commands, 11 subagents, 9 MCP
  servers and hook sets, ship from one source to 6 build targets.
- CI validates, builds and tests every change on Ubuntu and Windows under
  Python 3.9 and 3.12, then regenerates a Claude Code marketplace index and
  publishes the built bundles automatically.
- 19 test files run under `apkit test`.
- Built over one month (September–October 2026, 42 commits).

## Stack
Python 3.9+ (standard library only) · JSON target manifests · Markdown/TOML/JSON
renderers · MCP servers (Python) · Agent Skills spec · Claude Code, Codex CLI,
Cursor, OpenCode, Gemini CLI · GitHub Actions (Ubuntu + Windows matrix) ·
AI-assisted development with Claude Code

---

## CV bullet
Built apkit, a standard-library Python build tool that ships one plugin source
to 5 AI coding agents; wrote 9 agent plugins (25 skills, 11 subagents, 9 MCP
servers) using AI-assisted development, with cross-platform CI.

## Platform blurb
I build AI agent tooling that works across Claude Code, Codex CLI, Cursor,
OpenCode and Gemini CLI. apkit is my own build tool. I write a plugin once
(skills, slash commands, subagents, hooks, MCP servers) and it produces a
correct bundle for each agent, and reports explicitly anything an agent cannot
support. On top of it I wrote 9 working plugins, from code review and debugging
to sprint planning, and wired them into a multi-agent crew workflow. Built solo
with AI coding agents, tested on Windows and Linux in CI.
Python · MCP · Agent Skills · Claude Code · GitHub Actions
