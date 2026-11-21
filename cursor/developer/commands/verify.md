---
description: Run the checks this repository actually declares — types, lint, tests, build — and report what failed and why.
---

Verify the working tree. Scope: $ARGUMENTS

If that is empty, verify the whole repository from its root.

1. Discover the checks rather than guessing at them:

   ```bash
   python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/developer/skills/feature-implementation/scripts/verify.py
   python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/developer/skills/feature-implementation/scripts/verify.py --run
   ```

   The script reads `package.json` scripts, `pyproject.toml` tooling, Makefile
   targets, `go.mod` and `Cargo.toml`, and reports the package manager the
   lockfile implies. It exits 2 when the repository declares no checks at all —
   say that plainly instead of inventing a command.

2. For each failure, report: the check, the first real error (not the last line
   of output), the file and line, and whether your recent changes caused it or
   it was already failing on the base commit. Verify that claim with
   `git stash` or by checking out the base — do not assume.

3. Fix only what the user asked you to fix. Otherwise report and stop.

4. Finish with a one-line verdict: **green**, **green with pre-existing
   failures**, or **red** — and for red, the smallest next step.
