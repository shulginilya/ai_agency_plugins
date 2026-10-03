---
description: Audit a pull request or branch as a whole — scope, blast radius, reversibility, deploy ordering — and give a ship / ship-with-changes / hold verdict.
argument_hint: "[PR number or branch name]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(git:*) Bash(gh:*) Read Grep Glob
---

Audit this pull request or branch: {{ARGS}}

If that is empty, audit the current branch against its merge base with the
default branch.

Follow the `pr-audit` skill:

1. Gather the commit history, the diff stat, and the PR metadata if `gh` is
   available.
2. Work the audit checklist, skipping sections with a stated reason.
3. Answer the five questions: scope, blast radius, reversibility, deploy
   ordering, observability.
4. End with an explicit verdict — **ship**, **ship with changes**, or **hold** —
   and the reason for it.
