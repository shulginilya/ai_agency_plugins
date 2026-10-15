---
description: Verify a built change against its ticket's acceptance criteria with evidence, and give an accept, reject or blocked verdict.
argument_hint: "[issue number and branch or PR, e.g. \"#42 PR #43\"]"
model: claude-opus-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash Read Grep Glob Write
---

Verify: {{ARGS}}

Follow the `acceptance-testing` skill:

1. Get the criteria with
   `python {{PLUGIN_ROOT}}/skills/test-planning/scripts/criteria.py --issue <n>`, and the
   change and its commit (`gh pr view`, `git rev-parse --short HEAD`). Without a test plan,
   write one first with the `test-planning` skill.
2. Run the repository's checks (`/developer:verify`). If they fail, the verdict is reject.
3. Execute every case against the running result and record status and evidence. Explore
   for about 15 minutes beyond the plan. Hand the main flow to the `acceptance-checker`
   subagent. Never fix what you find: record it.
4. Write `results.json` and run
   `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/qa_report.py results.json`.
5. Report the verdict, the commit tested, and one `bug-reporting` report per failure, for
   developer or scrum-master to file.
