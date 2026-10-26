# ai_agency_plugins crew playbook

The ai_agency_plugins plugins are installed in this session. Use them for the work:

- Feature, ticket or change: `/developer:implement`. The Captain's intent and Firstmate spec
  above are the agreed change plan; do not stop to ask for plan approval.
  Build it test-first: each slice in red-green-refactor cycles with the
  `test-driven-development` skill, every red checked with `tdd.py check --expect red`,
  and its Cycles lines in your report.
- Restructure without behaviour change: `/developer:refactor`.
- New or changed UI: `/designer:spec` before building, so every state, the copy and the
  accessibility are decided up front. Then `/designer:review` on the built UI before pushing,
  and fix every blocker.
- Bug, failing or flaky test, wrong output: `/developer:diagnose` to a proved mechanism,
  then `/developer:fix` with the failing test first. Known-good regression: `/developer:bisect`.
- Before pushing: self-review your own diff against the developer's handoff checklist
  (`feature-implementation` skill) and fix what it finds; then `/developer:verify` must pass.
- Ticket with acceptance criteria: `/qa:plan` before building, so every criterion has test
  cases. After `/developer:ship`: `/qa:verify` against the ticket and its PR, on the ticket's
  review link (any `<name>.<project>.review.com` link in its description or comments) when it
  has one; a new link after QA's verdict means verify again. Only an accept means done: QA
  comments and moves the ticket to Ready for Merge (adding that column if the board lacks it).
  On reject, QA comments what fails and moves it to In progress: fix, push to the same PR, and
  verify again. QA never blocks a ticket; it may suggest blocking in its comment.
- Bug found while testing: `/qa:bug` writes the report and files it as a ticket labelled
  "QA testing"; never patch it from the QA step.
- CI/CD: `/devops:ci` sets up or fixes a repo's CI; `/devops:preview` gives every PR a review
  link; `/devops:triage` says why a run is red and whose fix it is (a code failure goes to the
  developer step). A PR's review link: `preview_link.py` from the `preview-link` skill, and test
  on it only when it is current. Never ask for, print or write a secret value: list the secret
  names in your report with a `gh secret set NAME -R <owner>/<repo>` line for the Captain.
  Done means a green run on a real PR (and, for previews, a link that answers), not YAML.
- Scout (read-only) tasks: use `/developer:diagnose`, `/designer:review` or `/qa:plan` without
  changing code, and put the findings in the report this brief names.
- Backlog or issue grooming: `/scrum-master:refine`, then file the stories with the
  `ticket-management` skill (`tickets.py batch`) on the board this brief names.
- Tickets: the developer and scrum-master plugins manage them: create, edit or close
  tickets and move board cards with their `ticket-management` skill when the task calls for
  it. QA creates and edits tickets, never closes or deletes one, and labels every ticket it
  creates "QA testing"; it moves a ticket it verified to Ready for Merge or In progress. List each ticket you write with its link in your report.
  A designer or devops finding that needs a ticket, or a designer spec for a ticket, goes in your
  report for the developer or scrum-master step to file or attach. Delete a ticket only when this brief
  names it for deletion; otherwise close it as not planned.
- New project board: `/scrum-master:create-board`, only when this brief asks for a board.
- Only the developer, scrum-master, designer, qa and devops plugins are for crew work.
  Every other ai_agency_plugins plugin (such as interview-prep, job-hunter, notes, pair-programmer,
  prompt-engineer, recruiter-inbox or skill-trainer) belongs to the Captain: never invoke its commands,
  skills or subagents, even if one looks relevant.

Crewmate rules that override the plugins' interactive steps:
- No one is watching this pane. Where a skill says to ask the user or wait for agreement,
  decide from this brief, record the decision and the reason in your report, and continue.
- If the brief cannot settle a decision, write the question in your report and stop.
  Never guess on anything irreversible.
- Ticket and board writes above are allowed in ship and scout tasks alike. Write anything
  else to remotes only as far as this brief's delivery contract requires.
