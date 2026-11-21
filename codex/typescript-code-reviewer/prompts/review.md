# /review

Review a TypeScript change (React, Node.js or both) — the current branch, a base ref or a pull request — with the TypeScript Code Reviewer, and report findings with an approve or request-changes verdict; --post also posts it on the PR.

Review: $ARGUMENTS

Follow the `typescript-review` skill:

1. Pick the target:
   - nothing: the current branch against the default branch, uncommitted and untracked changes included.
   - a base ref (`origin/develop`, a commit): the current branch against that ref.
   - a PR number: `gh pr view <N> --json number,url,state,headRefOid,baseRefName,isCrossRepository,author`.
     Closed or merged: say so and stop. The PR is **trusted** only when `isCrossRepository` is false and
     `author.login` is the current user (`gh api user --jq .login`), or the user said it is trusted. Note the branch you are on (`git branch --show-current`, else `git rev-parse HEAD`).
     If `git status --porcelain` shows changes, stop and say so: never check out over uncommitted
     work. Otherwise `git fetch origin <baseRefName>`, `gh pr checkout <N>`, confirm `git rev-parse HEAD`
     is `headRefOid`, and use `origin/<baseRefName>` as the base.
   `--post` only applies to a PR number; without one, say it was ignored.
2. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/typescript-code-reviewer/skills/typescript-review/scripts/ts_scope.py --base <base>`. "nothing to review":
   say so and stop (after returning to your branch).
3. Run the checks it printed (install first if it says so). For a PR that is not trusted, ask before
   installing or running anything, naming the author and whether it comes from a fork: install and the
   repo's scripts run the PR's code on this machine. Without a yes, record each check as `not run`.
   A red check is a blocker finding.
4. Read every changed file in full and the users of anything whose contract changed. Run the types,
   correctness and tests passes always, react and node when the scope lists them. Never read a file the
   scope tags `symlink`: report the link and its target instead. Give each pass to a
   `typescript-reviewer` subagent run with the pass name, the changed files and tags, the strictness
   and the escape hatches. Never fix what you find.
5. Write `findings.json` in a temporary directory, outside the repository, and run
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/typescript-code-reviewer/skills/typescript-review/scripts/review_report.py <findings.json> --commit <sha> > <review.md>`.
6. With a PR number and `--post`: `gh pr review <N> --comment --body-file <review.md>`. Otherwise post nothing.
   Never edit, commit or push code, never create or edit a ticket, and never move a board card.
7. After a PR checkout, return to the branch you started on (`git checkout <branch>`).
8. Report the verdict, the target and commit reviewed, the passes run, each check and its result, the
   review's link if posted, and the findings, most severe first. On request changes, say what would turn
   it into an approve.
