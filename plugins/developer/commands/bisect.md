---
description: Find the commit that introduced a regression by bisecting a scripted reproduction, then read the culprit.
argument_hint: "[last known good ref] [and/or the verdict command]"
model: sonnet
allowed_tools: Bash(git:*) Bash Read Grep Glob
---

Find what broke: {{ARGS}}

Follow the `regression-triage` skill.

1. Reduce the failure to one verdict command that exits 0 when good and
   non-zero when bad, and check it is deterministic on the current (bad) code:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/root-cause-analysis/scripts/repro.py" --cmd "<verdict>" --times 5
   ```

2. Bracket the range. If the user did not give a good ref, propose one from
   `git log --oneline --first-parent -30` or `git tag --sort=-creatordate` and
   confirm it before bisecting.
3. Print the plan first and read its warnings — a dirty tree, a lockfile change
   in range, a shallow clone or many merges each change the invocation:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/regression-triage/scripts/git_bisect.py" --good <ref> --cmd "<verdict>"
   ```

4. Then run it, adding `--setup` when dependencies changed in the range and
   `--times` when the verdict is not perfectly stable:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/regression-triage/scripts/git_bisect.py" --good <ref> --cmd "<verdict>" --run
   ```

5. Read the culprit commit and the file's history, then report in the skill's
   format with a fix direction of revert or forward-fix:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/regression-triage/scripts/history.py" <file> --lines <range>
   ```

If bisection is not possible — no repro, squashed or shallow history, a flaky
verdict — say so, fall back to history and blame, and label the culprit as
inferred rather than bisected.
