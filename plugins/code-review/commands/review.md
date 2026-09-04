---
description: Review the current diff and report defects ranked by severity, each with a concrete failure scenario.
argument_hint: "[base branch, path, or nothing for the working tree]"
model: sonnet
allowed_tools: Bash(git:*) Read Grep Glob
---

Review the code changes described by: {{ARGS}}

If that is empty, review the working tree against HEAD.

Follow the `code-review` skill. Specifically:

1. Establish scope with `changed_files.py` (or `git diff` directly) and read
   every changed file in full — not just the hunks.
2. Run the correctness pass, then load only the reference passes the change
   actually touches (security, performance, accessibility).
3. Report findings most severe first, in the skill's four-line format:
   claim, why, failure scenario, fix.
4. If nothing would break, say so plainly rather than padding with nits.
