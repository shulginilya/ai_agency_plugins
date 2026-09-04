---
name: pr-audit
description: Audits a whole pull request or branch as a unit — scope, commit hygiene, migration and rollback safety, blast radius, and whether the change is shippable — rather than reviewing individual lines. Use when asked to audit a PR, assess whether a branch is ready to merge or deploy, review a release, or judge the risk of a change set.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# PR audit

Line-level review asks "is this code correct". This asks "should this ship".
They are different questions and the second one is the one that causes
incidents.

Run the `code-review` skill first if the lines have not been reviewed; this
skill assumes they have. (Skills are referenced by name, never by relative
path — on most harnesses they install as independent directories.)

## Gather

```bash
git log --oneline --no-merges $(git merge-base HEAD main)..HEAD
git diff --stat $(git merge-base HEAD main)..HEAD
```

With the GitHub CLI available:

```bash
gh pr view --json title,body,files,additions,deletions,reviews,checks
gh pr diff
```

## The audit

Work through [references/audit-checklist.md](references/audit-checklist.md).
The five questions that matter most:

1. **Is the scope one thing?** A branch that renames a module *and* changes
   behaviour *and* bumps a dependency cannot be reverted cleanly. Say which
   commits should have been their own PR.
2. **What is the blast radius?** Which services, routes, jobs and consumers
   touch the changed code. A shared utility with forty call sites is a
   different risk from a leaf component, at identical diff size.
3. **Is it reversible?** For every change, ask what `git revert` alone would
   fail to undo: a migration that drops a column, a queue message whose shape
   changed, a feature flag that was removed, a cache key that was reused with
   a new shape.
4. **Does it deploy in one step or several?** Expand-contract violations are
   the classic: a migration and the code that requires it in one deploy means
   a window where old pods hit a new schema. Name the ordering.
5. **What is unobservable?** New failure modes with no log, metric or alert.
   If it can break silently in production, that is a finding.

## Verdict

End with one of three, and the reason:

- **Ship** — risks understood and acceptable; list anything to watch after deploy
- **Ship with changes** — the specific, minimal changes required first
- **Hold** — what has to be answered or split before this can be assessed

Never end an audit without a verdict. A list of observations is not an audit.
