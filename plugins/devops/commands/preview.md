---
description: Give every PR of a repository a review link (a preview deployment of its head commit) on Cloudflare Pages or Render, and prove it on a real PR.
argument_hint: "[repo path or owner/repo; optionally the host, e.g. \"render\"]"
model: claude-opus-5-5
effort: high
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash(actionlint:*) Bash(curl:*) Bash Read Grep Glob Edit Write
---

PR previews for: {{ARGS}}

Follow the `preview-environments` skill:

1. Scan the repo with `python {{PLUGIN_ROOT}}/skills/ci-setup/scripts/stack_scan.py <root>` and
   pick the host from its `kind` (static: Cloudflare Pages, server: Render), unless the
   arguments name one.
2. List the repository owner's one-time steps (account, Pages project or Blueprint, and
   `gh secret set` for each secret name). Never ask for, print or write a secret's value.
   Check what already exists with `gh secret list`, which shows names only, and stop with the
   list if anything is missing.
3. Write the files with `python {{PLUGIN_ROOT}}/skills/ci-setup/scripts/scaffold.py preview --root <root> ...`,
   then run `actionlint` if it is installed.
4. Prove it on a test PR: a green run, then
   `python {{PLUGIN_ROOT}}/skills/preview-link/scripts/preview_link.py --pr <N> --wait 600 --check`
   returns current with HTTP 2xx. After one more push the link follows the new commit, and there
   is still only one comment.
5. Report in the skill's format.
