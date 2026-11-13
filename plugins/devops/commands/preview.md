---
description: Paused — review links are out of the crew workflow for now, so this sets up no PR previews; it says so and stops.
argument_hint: "[repo path or owner/repo; optionally the host, e.g. \"render\"]"
model: claude-sonnet-5-5
effort: low
allowed_tools: Read Glob
---

PR previews for: {{ARGS}}

The `preview-environments` skill is paused. Review links are paused: they are out of the crew workflow for now, and QA
tests each PR's head commit locally. Don't scan the repo, write a workflow,
set a secret or open a test PR.

Say that review links are paused, so no PR preview was set up, and stop. If
the repository already has a preview workflow, name its file and leave it as
it is: removing it is the Captain's call.
