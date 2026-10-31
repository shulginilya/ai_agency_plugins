---
description: Verify a built change, on the ticket's review link when there is one, against its acceptance criteria with evidence; accept moves it to Ready for Merge, reject back to In progress.
argument_hint: "[issue number and branch or PR, e.g. \"#42 PR #43\"]"
model: claude-sonnet-5-5
effort: medium
allowed_tools: Bash(gh:*) Bash(git:*) Bash(python:*) Bash Read Grep Glob Write
---

Verify: {{ARGS}}

Follow the `acceptance-testing` skill:

1. Get the criteria with
   `python {{PLUGIN_ROOT}}/skills/test-planning/scripts/criteria.py --issue <n>`, and the
   change and its commit (`gh pr view`, `git rev-parse --short HEAD`). Without a test plan,
   write one first with the `test-planning` skill.
   Then run `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/review_link.py --issue <n> --pr <pr> --wait 600`
   (the newest link wins; the devops comment's marker says which commit it serves).
   It lists the ticket's column on each board. Verify only a ticket whose card is in **QA**: in In
   review it waits for code review, in In approval for the Captain's review. Say where it is and stop.
   Then, by its action:
   `wait` means the link still serves an older build, so never test it (exit 3: the build never
   landed, so report that); `test` or `retest` means every case runs on that review link; `up-to-date`
   means you already verdicted this link and commit, so say so and stop; `none` means
   look for the PR's preview with
   `python {{PLUGIN_ROOT}}/skills/preview-link/scripts/preview_link.py --pr <n> --wait 600 --check`
   and test on it only when it's current (deployed from the head commit); with no preview, test locally.
2. Run the repository's checks (`/developer:verify`). If they fail, the verdict is reject.
3. Execute every case against the running result (the review link when there is one) and record
   status and evidence; a check you couldn't make is `unchecked`, with why. Explore
   for about 15 minutes beyond the plan. Hand the main flow to the `acceptance-checker`
   subagent. Never fix what you find: record it.
4. Write `results.json` and run
   `python {{PLUGIN_ROOT}}/skills/acceptance-testing/scripts/qa_report.py results.json --link <url> --commit <sha> > verdict.md`.
   Only accept or reject. Never block: unchecked criteria reject and are listed as "Suggest blocking".
5. Post it: `gh issue comment <n> --body-file verdict.md`. Then, on every board the ticket is on:
   - accept: `python {{PLUGIN_ROOT}}/skills/ticket-management/scripts/board.py move --project <N> --issue <n> --status "Ready for Merge" --create-column --after QA`
     (adds the column, without asking, if the board lacks it);
   - reject: `... board.py move --project <N> --issue <n> --status "In progress"`.
6. Report the verdict, the link and commit tested, the comment's link, where the card is now, any
   column you added, and one bug ticket per failure, filed with the `bug-reporting` skill and
   labelled "QA testing", with each ticket's link.
