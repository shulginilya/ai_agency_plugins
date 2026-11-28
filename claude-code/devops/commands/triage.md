---
description: Say why a GitHub Actions run failed, who owns the fix (developer or devops), and fix it when it is the pipeline's.
argument-hint: "[PR number, run id or run URL; nothing for the current branch's PR]"
model: claude-sonnet-5-5
effort: medium
allowed-tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash(actionlint:*) Bash Read Grep Glob Edit Write
---

Triage: $ARGUMENTS

Follow the `pipeline-triage` skill:

1. Run `python ${CLAUDE_PLUGIN_ROOT}/skills/pipeline-triage/scripts/triage.py --pr <N>` (or `--run <id>`).
   With no argument, use the current branch's PR (`gh pr view --json number`). If the head
   commit has no failed runs, say so: an old red ✗ that a later push fixed isn't a failure.
2. For each failed job, read the category and evidence. Confirm them against
   `gh run view <id> --log-failed` when the category is unknown.
3. A pipeline failure (dependency, workflow, infra) is yours: fix it, push, and watch the
   rerun. Rerun an infra failure once before calling it flaky. A code failure (test, build,
   lint) goes to the developer with the evidence. Never make a check green by weakening it.
4. Report in the skill's format.
