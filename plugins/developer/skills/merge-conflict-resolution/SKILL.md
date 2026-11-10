---
name: merge-conflict-resolution
description: Resolves a pull request's merge conflicts, only when the user asked for it or gave permission, by rebasing the PR branch onto its base branch — each conflicted file resolved to keep both sides' intent, generated files taken from the base, a conflict that is really a decision stopped and reported — then re-runs the checks and pushes the rebased branch with --force-with-lease. Use when the user asks to fix, resolve or rebase a PR that has merge conflicts, or to bring a PR branch up to date with main.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Resolve a PR's merge conflicts

A conflict means two changes touched the same lines, and the PR's author is
the one who knows what its side meant. So the developer resolves it. But a
rebase rewrites a branch other people may be reading, so it happens only when
the user says so.

## 0. Permission first

Start only if the user asked for this PR's conflicts to be resolved, or said
yes when you offered. Running `/resolve-conflicts` is asking. A conflict you
noticed yourself, while shipping or reviewing, is not permission: report it
(`PR #N conflicts with <base> in <files>`) and offer to resolve it. Then stop.

A crew brief counts only if it names the PR for conflict resolution. Without
that, put the conflict in your report and stop.

## 1. Read the PR

```bash
gh pr view N --json headRefName,baseRefName,mergeable,isCrossRepository,state
```

- Stop if it is closed or merged, or `isCrossRepository` is true (a fork's
  branch is not yours to rewrite).
- `mergeable` of `MERGEABLE` means there is nothing to resolve. Say so and stop,
  unless the user asked for the branch to be brought up to date anyway.
- The working tree must be clean (`git status`). Never stash someone's work to
  make room.

```bash
git fetch origin
git checkout <head> && git pull --ff-only     # local must match the remote branch
before=$(git rev-parse HEAD)                  # what --force-with-lease will expect
git branch "backup/<head>" "$before"          # local only, for an easy way back
```

If `pull --ff-only` fails, the local branch has commits the remote doesn't, or
the other way round. Stop and report it. Rebasing that would lose someone's work.

## 2. Rebase, never merge

```bash
git rebase origin/<base>
```

The commits are replayed one at a time. At each stop,
`git diff --name-only --diff-filter=U` lists the conflicted files. **During a
rebase the sides are swapped:** `--ours` is the base branch, and `--theirs` is
the PR commit being replayed. Name sides by branch in your notes, not by
ours/theirs.

For each file, read both sides before editing:
`git show origin/<base>:<file>`, the replayed commit (`git log -1 REBASE_HEAD`,
`git show REBASE_HEAD -- <file>`), and what the base changed since the PR
branched (`git log origin/<base> --oneline -- <file>`).

Then resolve it as one of three kinds:

| Kind | Example | Resolution |
| --- | --- | --- |
| **Generated** | a file the repo's docs or CI mark as generated (here: `docs/crew/*.drawio`, `.claude-plugin/marketplace.json`) | `git checkout origin/<base> -- <file>`. Never hand-merge it; whatever regenerates it does so after the merge. |
| **Text clash** | both sides reworded the same paragraph, both bumped a version, both added a row | Keep both intents in one result. A version goes past both sides (0.2.0 and 0.3.0 become 0.4.0). An ordered list keeps the base's order and slots the PR's item where it belongs. |
| **Decision** | the two sides disagree on behaviour: two rules for the same thing, one side removed what the other extends | `git rebase --abort`. Don't choose. Report both sides and the resolution you propose, and wait for the user. |

Look past the markers too. A file that merged cleanly can still contradict a
resolved one, such as a doc that says "never X" when the base now does X. Fix it
in the same commit.

`git add <file>` and `git rebase --continue`. If a replayed commit ends up
empty because the base already contains it, `git rebase --skip` and say so.

## 3. Check before pushing

- Run the repo's checks (`/verify`). A rebase that doesn't pass doesn't get pushed.
- `git range-diff origin/<base> "$before" HEAD` shows each PR commit before
  and after. Every difference should be one you made to resolve a conflict.
- `git diff origin/<base>...HEAD --stat` should be the PR's change and nothing
  else.

## 4. Push the rebased branch

```bash
git push --force-with-lease=<head>:"$before" origin HEAD:<head>
```

This is the only force-push allowed anywhere: to the PR's own branch, after a
rebase you were asked for, and leased on the commit you started from. If
someone pushed in the meantime, it fails. Fetch, and start again from step 1.
Never `--force`, and never push to the base branch.

Then `gh pr view N --json mergeable` should say `MERGEABLE` (it may read
`UNKNOWN` for a few seconds). Delete `backup/<head>` once it does.

If a resolution changed behaviour, not only wording, say that QA has to verify
again. The new head commit means a re-test anyway.

## Reporting

```
PR:       <PR URL> — rebased onto <base> (<old sha> → <new sha>), pushed with --force-with-lease
Resolved: <file> — <generated: took base | text: what was kept from each side>
Stopped:  <file> — <decision: both sides, the proposed resolution> (rebase aborted, nothing pushed)
Checks:   <what ran and the result>
QA:       <re-verify needed, and why | no behaviour change>
```
