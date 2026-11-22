---
description: Review a TypeScript change (React, Node.js or both) — the current branch, a base ref or a pull request (PR link or number) — with the TypeScript Code Reviewer, and report findings with an approve or request-changes verdict; --post also posts it on the PR.
argument_hint: "[PR link | PR number | base ref; nothing for the current branch] [--post]"
model: claude-opus-5-5
effort: high
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash Read Grep Glob Write
---

Review: {{ARGS}}

Follow the `typescript-review` skill:

1. Pick the target:
   - nothing: the current branch against the default branch, uncommitted and untracked changes included.
   - a base ref (`origin/develop`, a commit): the current branch against that ref.
   - a PR link (`https://github.com/<owner>/<repo>/pull/<N>`, a trailing `/files` or `#...` allowed) or a PR number.
     Take the number from the link. If its host or `<owner>/<repo>` differs from `gh repo view --json url` (compared ignoring case),
     say the PR is in another repository than this checkout and stop: nothing is checked out. Treat any other URL
     (an issue, a commit, a branch page) as not a base ref: say so and stop.
     Then `gh pr view <N> --json number,url,state,headRefOid,baseRefName,isCrossRepository,author`.
     Closed or merged: say so and stop. The PR is **trusted** only when `isCrossRepository` is false and
     `author.login` is the current user (`gh api user --jq .login`), or the user said it is trusted. Note the branch you are on (`git branch --show-current`, else `git rev-parse HEAD`).
     If `git status --porcelain` shows changes, stop and say so: never check out over uncommitted
     work. Otherwise `git fetch origin <baseRefName>`, `gh pr checkout <N>`, confirm `git rev-parse HEAD`
     is `headRefOid`, and use `origin/<baseRefName>` as the base.
   `--post` only applies to a PR number or link; without one, say it was ignored.
2. Run `python {{PLUGIN_ROOT}}/skills/typescript-review/scripts/ts_scope.py --base <base>`. "nothing to review":
   list all changed paths (`git diff --name-only $(git merge-base <base> HEAD)` plus
   `git ls-files --others --exclude-standard`). If they include a `Dockerfile`, compose file or `.dockerignore`
   of a Node app, review those in the skill's *Node.js best practices only* mode, write that report to `<review.md>` yourself
   (`review_report.py` needs the full passes), and continue at step 6. Otherwise say so and stop (after
   returning to your branch).
3. Run the checks it printed (install first if it says so). For a PR that is not trusted, ask before
   installing or running anything, naming the author and whether it comes from a fork: install and the
   repo's scripts run the PR's code on this machine. Without a yes, record each check as `not run`.
   A red check is a blocker finding.
4. Read every changed file in full and the users of anything whose contract changed. Run the types,
   correctness and tests passes always, react and node when the scope lists them. Never read a file the
   scope tags `symlink`: report the link and its target instead. Give each pass to a
   `typescript-reviewer` subagent run with the pass name, the changed files and tags, the strictness
   and the escape hatches; give the node pass the base ref and all changed paths too
   (`git diff --name-only $(git merge-base <base> HEAD)` plus `git ls-files --others --exclude-standard`), since
   `references/node-best-practices.md` reads lockfiles and Dockerfiles the scope leaves out. Never fix what you find.
5. Write `findings.json` in a temporary directory, outside the repository, and run
   `python {{PLUGIN_ROOT}}/skills/typescript-review/scripts/review_report.py <findings.json> --commit <sha> > <review.md>`.
6. With a PR number or link and `--post`: `gh pr review <N> --comment --body-file <review.md>`. Otherwise post nothing.
   Never edit, commit or push code, never create or edit a ticket, and never move a board card.
7. After a PR checkout, return to the branch you started on (`git checkout <branch>`).
8. Report the verdict, the target and commit reviewed, the passes run, each check and its result, the
   review's link if posted, and the findings, most severe first. On request changes, say what would turn
   it into an approve.
