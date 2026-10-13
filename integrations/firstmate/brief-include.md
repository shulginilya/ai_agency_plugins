# ai_agency_plugins crew playbook

The ai_agency_plugins plugins are installed in this session. Use them for the work:

- Feature, ticket or change: `/developer:implement`. The Captain's intent and Firstmate spec
  above are the agreed change plan; do not stop to ask for plan approval.
- Restructure without behaviour change: `/developer:refactor`.
- Bug, failing or flaky test, wrong output: `/debugger:diagnose` to a proved mechanism,
  then `/debugger:fix` with the failing test first. Known-good regression: `/debugger:bisect`.
- Before pushing: `/code-review:review` on your own diff and fix every high-severity finding;
  then `/developer:verify` must pass.
- Scout (read-only) tasks: use `/debugger:diagnose` or `/code-review:review-pr` without
  changing code, and put the findings in the report this brief names.
- Backlog or issue grooming: `/scrum-master:refine`, then file the stories with the
  `ticket-management` skill (`tickets.py batch`) on the board this brief names.
- Tickets during any task: create, edit or close them and move board cards with the
  `ticket-management` skill when the task calls for it, and list each one with its link in
  your report. Delete a ticket only when this brief names it for deletion; otherwise close
  it as not planned.
- New project board: `/scrum-master:create-board`, only when this brief asks for a board.
- Only the developer, debugger, code-review and scrum-master plugins are for crew work.
  Every other ai_agency_plugins plugin (such as interview-prep, job-hunter, pair-programmer,
  prompt-engineer or recruiter-inbox) belongs to the Captain: never invoke its commands,
  skills or subagents, even if one looks relevant.

Crewmate rules that override the plugins' interactive steps:
- No one is watching this pane. Where a skill says to ask the user or wait for agreement,
  decide from this brief, record the decision and the reason in your report, and continue.
- If the brief cannot settle a decision, write the question in your report and stop.
  Never guess on anything irreversible.
- Ticket and board writes above are allowed in ship and scout tasks alike. Write anything
  else to remotes only as far as this brief's delivery contract requires.
