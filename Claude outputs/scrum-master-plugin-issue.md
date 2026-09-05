## Problem

The repo has one plugin, `code-review`, and it only demonstrates the format on a
task where the agent reads code. Nothing exercises the format on a task where
the agent reads *a tracker* — which is where most of the harness-portability
questions actually live: an external CLI that may not be installed, output that
must never be written back without approval, and logic that has to be reachable
both from a script and from an MCP tool without being written twice.

Separately, backlog refinement is the ceremony where an agent has the clearest
value and gets used the least, because the useful part is boring: checking that
an item has a value statement, two testable acceptance criteria, a size, and no
unresolved TBD before someone commits to it in planning. Doing that by eye
across thirty open issues is exactly the work people skip, and skipping it is
the single most common reason a committed item does not finish.

## Proposal

A second plugin, `plugins/scrum-master/` (0.1.0), covering refinement and sprint
planning against GitHub Issues. Standups and retros are deliberately excluded.

| Component | Name | Responsibility |
| --- | --- | --- |
| Skill | `backlog-refinement` | Definition of Ready, the refinement loop, the issue template |
| Skill | `sprint-planning` | Capacity first, goal second, selection third, then pre-flight checks |
| Command | `/refine` | One item → a ready story, split first if it is too big |
| Command | `/plan-sprint` | A sprint plan from the ready backlog |
| Command | `/backlog-health` | How much of the backlog is plannable, and what is missing |
| Agent | `story-splitter` | Splits one oversized item into vertical slices, fresh context |
| Hook | `SessionStart` | Prints the active milestone and its open issues, once |
| MCP | `scrum-master` | `backlog`, `readiness_check`, `scrum_checklist` |
| Scripts | `ready.py`, `backlog.py`, `capacity.py`, `sprint_context.py` | stdlib only |

Five reference files carry the detail (INVEST, splitting patterns, estimation,
capacity, sprint goal) and load on demand.

## Design decisions worth reviewing

The one fact most of these follow from: **`gh` may not be installed, and the
backlog is not ours to edit.**

- **GitHub Issues is the backlog; there is no local state.** No `.scrum/`
  directory, no cache, no sync. The alternative — files as source of truth with
  a push to GitHub — was rejected as two things to keep consistent. Cost: the
  plugin is useless in a repo that does not use Issues.
- **Every `gh` write is proposed, never executed.** The commands print the
  `gh issue edit` / `gh api` call and stop. This is the decision I would most
  like challenged: it makes `/refine` a two-step interaction forever, and an
  argument for a `--yes` escape hatch is easy to make.
- **Scripts exit 2 with one sentence when `gh` is missing, unauthenticated, or
  outside a repo** — rather than degrading to a guess. `backlog.py --from-json`
  accepts a pasted `gh issue list --json …` payload as the fallback.
- **The readiness rules exist in exactly one module.**
  `skills/backlog-refinement/scripts/ready.py` is both a CLI and the module the
  MCP server imports by putting that directory on `sys.path` — the same trick
  `code-review`'s server uses to reach `skills/*/references/`. This couples the
  server to the skill directory layout; when the import fails the tool returns
  a `RuntimeError` naming the path it looked in, rather than crashing the
  transport. A reviewer may reasonably prefer duplication over that coupling.
- **Scripts live under `skills/<skill>/scripts/`, not `plugins/<name>/scripts/`.**
  Plugin-level scripts only ship with bundle targets; skill-level ones travel
  everywhere, so `ready.py`, `backlog.py` and `capacity.py` work on the generic
  `.agents/skills` target. Only `sprint_context.py` is plugin-level, because the
  hook it serves is Claude Code-only anyway.
- **Readiness gaps block; signals only warn.** Missing value / criteria / size /
  an unresolved TBD mark an item not-ready. Vague wording, an over-long body and
  a title joined by "and" only warn, because each has legitimate false
  positives. The title heuristic in particular is noisy — "Import CSV and XLSX"
  warns, and sometimes that really is one story.
- **Capacity ships opinionated defaults**: 0.5 ceremony-days per person per
  sprint subtracted automatically, focus factor 0.7, and an 80% commitment
  ratio applied to both the person-day and velocity figures. These are
  defensible but they are opinions, and they are baked into the arithmetic
  rather than passed in.
- **`--from-json` is a shipped flag that exists partly for testing.** It is the
  only way to exercise `assess()` without a network. Justifiable as a real
  escape hatch for pasted output, but worth naming.

## Acceptance criteria

- [x] `python -m tools.apkit validate --strict` passes for both plugins
- [x] `python -m tools.apkit build --plugin scrum-master` produces bundles for
      all six targets, with hooks/scripts degradation reported per target
- [x] `python -m tools.apkit test` passes — 7/7 test files, of which
      `plugins/scrum-master/tests/test_scripts.py` contributes 27 tests
- [x] The MCP server answers `initialize`, `tools/list` and `tools/call` over
      stdio, including from the built `dist/claude-code/scrum-master` bundle
- [x] `backlog.py` and `capacity.py` exit 2 with a one-line message — no
      traceback — on missing `gh`, malformed JSON, and impossible inputs
- [x] `sprint_context.py` exits 0 and prints nothing outside a git repository,
      and on a malformed hook event
- [x] `ready.py` accepts a size from either a `size/*` label or an
      `Estimate:` line, and treats `Depends on: none` as resolved
- [x] `.claude-plugin/marketplace.json` regenerated; lists both plugins
- [ ] Anything that actually calls `gh` — see below

## Out of scope / follow-ups

- [ ] **No code path that shells out to `gh` has ever run.** `gh` is not
      installed on the machine this was written on. `backlog.fetch()`, the MCP
      `backlog` tool, and the hook's milestone lookup
      (`gh api repos/:owner/:repo/milestones`) are covered only by their
      failure paths and by `--from-json`. This is the first thing to verify.
- [ ] Never installed into a running harness: no `apkit install`, no
      `SessionStart` hook fired by Claude Code, no MCP server registered by a
      real client. Only direct stdio JSON-RPC.
- [ ] `dist/` in the working tree is stale — the build was verified against a
      scratch directory, so `dist/` still contains only `code-review`. Run
      `python -m tools.apkit build` before relying on it.
- [ ] Ran on Python 3.10 only. The repo targets 3.9+; CI covers 3.9 and 3.12.
- [ ] The `SessionStart` hook prints on every session start in any repo with an
      open milestone, with no opt-out. If that turns out to be noise, it needs
      a config flag or a quiet threshold.
- [ ] GitHub Projects (v2) fields — status, iteration, custom point fields —
      are not read. Only issues, labels and milestones.
- [ ] Sprint review and retrospective are not covered, by choice.

## Notes for the reviewer

New: `plugins/scrum-master/` (24 source files, ~2,100 lines including
references and tests). Modified: `.claude-plugin/marketplace.json`, regenerated
by `apkit marketplace`.

Two real bugs surfaced while writing the tests, both in `ready.py`: a size on a
bullet (`- Estimate: 5`) was not recognised because the pattern anchored to
line start without allowing a list marker, and `Depends on: none` was read as an
unresolved dependency because an optional-separator group backtracked past the
negative lookahead. Both now have tests. A third change came out of the same
pass: `capacity.compute()` defaulted `days` to 0 while the CLI defaulted it to
10, so calling the function directly produced a divide-by-nothing error — the
defaults now match.

Start the review at `skills/backlog-refinement/scripts/ready.py` and
`mcp/server.py`. Everything else is prose or a thin wrapper.
