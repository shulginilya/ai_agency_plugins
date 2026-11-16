---
description: Verify a built change, on its PR's head commit run locally, against its acceptance criteria with evidence; accept moves it to Ready for Merge, reject back to In progress.
argument_hint: "[issue number and branch or PR, e.g. \"#42 PR #43\"]"
model: claude-sonnet-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash Read Grep Glob Write
---

Verify: {{ARGS}}

Follow the `acceptance-testing` skill:

0. Run `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/pr_base.py --pr <pr>`. Exit 3
   ("base is not <default>": the PR does not target the default branch) means no accept and no
   reject: post no verdict, move no card, say the PR must be retargeted, and stop.
1. Get the criteria with
   `python {{PLUGIN_ROOT}}/skills/test-planning/scripts/criteria.py --issue <n>`, and the
   change and its commit (`gh pr view`, `git rev-parse --short HEAD`). Without a test plan,
   write one first with the `test-planning` skill.
   Then run `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/review_link.py --issue <n> --pr <pr> --local`.
   Review links are paused: never look for, wait on or test a review link or a preview deployment,
   even when the ticket has one.
   It lists the ticket's column on each board. Verify only a ticket whose card is in **QA**: in In
   review it waits for code review, in In approval for the Captain's review. Say where it is and stop.
   Then, by its action:
   `test` or `retest` means check out the PR (`gh pr checkout <pr>`), confirm `git rev-parse HEAD`
   is its head commit, and run every case locally; `up-to-date` means you already verdicted this
   commit, so say so and stop. Before the checkout, note where you start,
   `start=$(git branch --show-current); [ -n "$start" ] || start=$(git rev-parse HEAD)` (the commit on a
   detached HEAD), and if
   `git status --porcelain --untracked-files=no` prints anything, `git stash push -m "qa #<n>: from $start"`
   and say so: those changes are someone's work. If you stop after stashing and before step 5,
   `git checkout "$start" && git stash pop` first, or report the stash and its branch if that fails.
2. Run the repository's checks (`/developer:verify`). If they fail, the verdict is reject.
3. Execute every case against the app running locally from that commit and record
   status and evidence; a check you couldn't make is `unchecked`, with why. Explore
   for about 15 minutes beyond the plan. Hand the main flow to the `acceptance-checker`
   subagent. Never fix what you find: record it.
4. Write `results.json` and run
   `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/qa_report.py results.json --commit <sha> > verdict.md`.
   Only accept or reject. Never block: unchecked criteria reject and are listed as "Suggest blocking".
5. Post it: `gh issue comment <n> --body-file verdict.md`. Then, on every board the ticket is on:
   - accept: `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py move --project <N> --issue <n> --status "Ready for Merge" --create-column --after QA`
     (adds the column, without asking, if the board lacks it);
   - reject: `... board.py move --project <N> --issue <n> --status "In progress"`.

   Then, on accept and on reject, leave the PR branch: check out the default branch, looked up
   and never assumed to be `main`, and fast-forward it:
   `base=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name) && git restore . && git checkout "$base" && git pull --ff-only`
   (`git restore .` drops only what the test run changed: the tree was clean or stashed before). If
   step 1 stashed: started on the default branch, `git stash pop`; started on another branch, leave the
   stash (never pop it onto the default branch) and report its name, its branch and
   `git checkout <start> && git stash pop` to restore it. Keep `results.json` and `verdict.md` outside the working tree. If
   the switch, pull or pop fails, don't force it and never drop the stash: report the branch you are
   on, what is still stashed, and why.
6. Report the verdict, the commit tested, the comment's link, where the card is now, the branch
   you are back on, any stash left with its branch, any column you added, and one bug ticket per failure, filed with the `bug-reporting` skill and
   labelled "QA testing", with each ticket's link.
