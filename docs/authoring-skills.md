# Authoring skills that actually get used

A skill fails in one of two ways: it never triggers, or it triggers and gives
advice the model would have produced anyway. Both are avoidable.

## The description is the product

At startup a harness loads only each skill's `name` and `description` — a few
hundred tokens across your whole library. That sentence is the entire basis on
which the model decides whether to open your skill. Everything else you write
is downstream of it.

Say what it does **and** when to reach for it, in the words a user would type:

```yaml
# triggers
description: Reviews a diff, branch or pull request and reports defects ranked
  by severity, each with a concrete failure scenario. Use when the user asks to
  review code, check a diff or branch, look over a PR before merging, or find
  bugs in changes that were just made.

# does not trigger
description: Helps with code review.
```

`apkit validate` warns on descriptions under 40 characters and on ones with no
explicit trigger clause. Those warnings are the single highest-value thing the
validator does.

## Structure for progressive disclosure

Three tiers, and the split matters more as your library grows:

1. **Metadata** (~100 tokens, always loaded) — `name` and `description`
2. **Body** (loaded on activation) — keep `SKILL.md` under 500 lines
3. **References** (loaded only when the body sends the model there) —
   `references/*.md`, one level deep

The `backlog-refinement` skill in this repo does this: the body carries the
refinement loop and sends the model to `estimation.md`, `invest.md` or
`splitting.md` only at the step that needs it. Refining a small, clear item
never pays for the splitting reference.

Scripts get the same treatment. A deterministic script is cheaper and more
reliable than asking a model to compute the same thing — `changed_files.py`
costs one tool call and never miscounts a diff.

## Writing the body

- **Imperative, not descriptive.** "Read every changed file in full" beats
  "it is important to read the files".
- **Order matters.** Numbered steps get followed in order; bullet lists get
  sampled.
- **Say what not to do.** Most of the value in a review skill is the list of
  things it must *not* report. Models default to being agreeable and
  exhaustive; a skill earns its place by narrowing that.
- **Specify the output shape exactly.** Good work in an unexpected format gets
  ignored.
- **Say what "nothing" looks like.** Without an explicit empty-result path, a
  model will invent findings to justify the pass.

## Portability rules

- **Only spec frontmatter.** `name`, `description`, `license`, `compatibility`,
  `metadata`, `allowed-tools`. A `model:` key in a `SKILL.md` is a Claude Code
  idea; some harnesses ignore it, some reject the file. Put harness-specific
  settings in `plugin.json` or `targets/`.
- **`name` must equal the directory name.** Every harness resolves skills by
  directory; a mismatch means it loads under a name you did not intend.
- **Never link across skills by relative path.** On most harnesses skills
  install as independent directories with no fixed relationship. Refer to a
  sibling skill by name.
- **Colocate scripts with the skill that calls them.** `skills/<name>/scripts/`
  travels everywhere; the plugin-level `scripts/` only ships in bundles.
- **Assume nothing about the environment.** Declare what you need in
  `compatibility` and check for it in the script rather than in prose.

## Before you ship one

```bash
python -m tools.apkit validate --plugin my-plugin --strict
python -m tools.apkit build --plugin my-plugin
```

Then read `dist/agents/my-plugin/skills/<name>/SKILL.md` — the generic target —
and ask whether that file alone, with no plugin around it, would do the job.
That is what most harnesses will actually see.
