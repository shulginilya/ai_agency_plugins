---
description: Set up or fix CI for a repository on GitHub Actions, running the repo's own checks on every PR, and prove it with a green run.
argument_hint: "[repo path or owner/repo, and what to add — e.g. \"lint and tests on PRs\" or \"a deploy on main\"]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash(actionlint:*) Bash Read Grep Glob Edit Write
---

CI for: {{ARGS}}

Follow the `ci-setup` skill:

1. Scan the repo: `python {{PLUGIN_ROOT}}/skills/ci-setup/scripts/stack_scan.py <root>`.
   Settle every UNKNOWN line from the repo itself. An existing workflow is fixed or
   extended, never duplicated.
2. Write the workflow: `python {{PLUGIN_ROOT}}/skills/ci-setup/scripts/scaffold.py ci --root <root>`,
   with overrides for whatever the scan couldn't tell. Run `actionlint` if it is installed.
3. List every secret the workflow needs by name, with the `gh secret set` line for the
   repository owner. Never ask for, print or write a secret's value.
4. Prove it on a PR: a green run, or `pipeline-triage` on the red one until it is green.
5. Report in the skill's format, with the PR and run links.
