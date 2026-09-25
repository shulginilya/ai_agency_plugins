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
3.12. It does **not** check `marketplace.json` on pull requests: the index is
generated from every `plugin.json`, so enforcing it per-branch makes every
plugin PR edit the same array and conflict by construction. It is regenerated
once, on `main`, after the merge.

## Distributing to Claude Code

Built output does not belong in source history, so `dist/` stays gitignored and
the index cannot point at it -- a consumer cloning `main` would get paths that
are not there. Instead each entry in `.claude-plugin/marketplace.json` is a
`git-subdir` source naming this repository, the directory inside it, and the
branch the bundles are published on:

```json
{
  "name": "code-review",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/shulginilya/ai_agency_plugins.git",
    "path": "claude-code/code-review",
    "ref": "dist"
  }
}
```

The `dist` branch is build output: CI's `publish` job rebuilds it on every push
to `main` and force-pushes a single commit mirroring `dist/`. Never work on that
branch -- the next green build overwrites it.

That keeps the index on the default branch, which is what consumers sync:

```bash
/plugin marketplace add shulginilya/ai_agency_plugins
/plugin install code-review@ai-agency
```

In the Claude desktop app and Cowork it is Customize -> Plugins -> Personal
plugins -> + -> Add marketplace -> from a repository, then Install per plugin.
There is no branch picker there, which is exactly why the index lives on `main`
and reaches across to `dist` rather than living on a release branch itself.

To pin consumers to an exact build, regenerate with a commit instead of a
branch -- `sha` wins over `ref`:

```bash
python -m tools.apkit marketplace --ref "$(git rev-parse origin/dist)"
```

For local work, generate the path form instead. It resolves against your own
`dist/`, and is the one form that must never be committed:

```bash
python -m tools.apkit build
python -m tools.apkit marketplace --publish path
/plugin marketplace add .
```

### Handing over one file

A marketplace is for consumers who will keep getting updates. For a one-off --
the Claude desktop app, a colleague, a machine with no git -- pack the built
bundle into a single archive instead:

```bash
tools/pack.sh job-hunter                  # dist/pack/claude-code/job-hunter-0.2.0.plugin
tools/pack.sh --all -T                    # every plugin, every harness
tools/pack.sh job-hunter -o ~/Desktop
```

`claude-code` archives come out as `.plugin` files, which the Claude desktop app
and Cowork accept under Customize -> Plugins -> upload a custom plugin file;
every other harness gets a `.zip` to unpack where its `INSTALL.md` says. The
extension and the note are declared per target in `targets/*.json` under
`archive`, not decided in code.

The archive's contents sit at its root. A wrapper directory is the difference
between a plugin that installs and one the host app ignores without a word,
which is why `apkit pack` refuses a bundle whose manifest is missing rather
than writing an archive that will fail quietly.

For a single machine, skip the marketplace entirely:

```bash
python -m tools.apkit install code-review --target claude-code --scope user
```

That drops the bundle into `~/.claude/skills/code-review/`, which Claude Code
loads as a personal-scope plugin (`code-review@skills-dir`) with no marketplace
and no install step. Personal skills do not sync to Cowork or cloud sessions,
so the marketplace above is the route for anything but your own terminal.

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
