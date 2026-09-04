# Release

## Versioning

Each plugin versions itself in its own `plugin.json`, semver:

- **patch** — wording, a fixed reference link, a bug in a bundled script
- **minor** — a new skill, command or agent; a new reference file
- **major** — a renamed or removed skill, a changed command name, a hook that
  now blocks something it did not block before

Rename a skill and every install that resolved it by name breaks. Treat skill
names as public API.

The toolkit versions separately in `pyproject.toml`.

## Cutting a release

```bash
python -m tools.apkit validate --strict
python -m tools.apkit build --clean
python -m tools.apkit test
python -m tools.apkit marketplace

git commit -am "feat(code-review): <what changed>"
git tag code-review-v0.2.0
git push --follow-tags
```

CI runs the same first three commands on Linux and Windows, on Python 3.9 and
3.12, and fails if `marketplace.json` is stale.

## Distributing to Claude Code

`.claude-plugin/marketplace.json` points at `./dist/claude-code/<plugin>`, and
`dist/` is gitignored on `main` — built output does not belong in source
history. So a marketplace consumer needs the built bundles published somewhere.
Two ways, pick one:

**A release branch.** CI builds and force-pushes `dist/` to a `release` branch;
consumers add that branch as the marketplace:

```bash
/plugin marketplace add shulginilya/ai_agency_plugins@release
/plugin install code-review@ai-agency
```

**A release tarball.** CI attaches `dist/` to a GitHub release; consumers
download and add the local path. Simpler to reason about, worse to keep current.

For a single machine, skip the marketplace entirely:

```bash
python -m tools.apkit install code-review --target claude-code --scope user
```

That drops the bundle into `~/.claude/skills/code-review/`, which Claude Code
loads as a personal-scope plugin with no marketplace and no install step.

## Distributing to everything else

There is no registry. Installation is `apkit install`, or a checked-in
`.agents/skills/` directory in the repo people are already working in:

```bash
python -m tools.apkit install code-review --target agents --scope project --into .
git add .agents/skills && git commit -m "chore: vendor the code-review skill"
```

Committed skills are the most reliable distribution there is — everyone on the
repo gets them, in the version the repo is on, with no install step and no
per-machine drift. The cost is that updates need a commit.

## When a harness changes

1. Fix the path or dialect in `targets/<harness>.json`.
2. Set `"verified": true` on any mapping you confirmed against live docs, and
   update the verification list in [harness-matrix.md](harness-matrix.md).
3. `python -m tools.apkit build && python -m tools.apkit test`.
4. Patch-bump the toolkit, not the plugins — their sources did not change.
