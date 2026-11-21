---
description: Implement a fix for a bug whose root cause is already proved, with the failing test written first.
---

Fix: $ARGUMENTS

Before editing anything, state the cause you are fixing in one sentence and the
evidence that proved it. If neither this conversation nor the argument contains
a proved cause, stop and run `/diagnose` first — a fix without a cause is a
guess that makes the next diagnosis harder.

Follow steps 5 and 6 of the `root-cause-analysis` skill.

1. Write the regression test first, per the `test-driven-development` skill's
   bug-fix cycle. Confirm it fails for the reported reason, on its assertion:
   `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/developer/skills/test-driven-development/scripts/tdd.py" check --cmd "<the test>" --expect red`.
   A test that passes against the broken code tests nothing, and an import
   error is not a red.
2. Make the smallest change that removes the mechanism. Nothing else travels in
   this change — no rename, no refactor, no drive-by cleanup.
3. Confirm the two-way proof with the same command: revert the fix and
   `--expect red` holds, reapply it and `--expect green` holds.
4. Run the repo's own checks:

   ```bash
   python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/developer/skills/root-cause-analysis/scripts/repro.py" --discover
   ```

5. Sweep for the same mechanism elsewhere and list every other site, per
   `references/verification.md`.
6. Remove your instrumentation, then summarise: the cause, the change, the
   guard, the other sites, and what would now be visible in production if it
   recurred.

If the only fix available is a stopgap — a retry, a guard, a suppression —
label it as one, say what the real fix is, and do not describe the cause as
resolved.
