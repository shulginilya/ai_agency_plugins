# ai_agency_plugins crew playbook

The ai_agency_plugins plugins are installed in this session. Use them for the work:

- Feature, ticket or change: `/developer:implement`. The Captain's intent and Firstmate spec
  above are the agreed change plan; do not stop to ask for plan approval.
- Restructure without behaviour change: `/developer:refactor`.
- New or changed UI: `/designer:spec` before building, so every state, the copy and the
  accessibility are decided up front. Then `/designer:review` on the built UI before pushing,
  and fix every blocker.
- Bug, failing or flaky test, wrong output: `/developer:diagnose` to a proved mechanism,
  then `/developer:fix` with the failing test first. Known-good regression: `/developer:bisect`.
- Before pushing: self-review your own diff against the developer's handoff checklist
  (`feature-implementation` skill) and fix what it finds; then `/developer:verify` must pass.
- Ticket with acceptance criteria: `/qa:plan` before building, so every criterion has test
  cases. Before reporting a ship task done: `/qa:verify` against the ticket. Only an accept
  verdict means done; on reject or blocked, fix and verify again, or report what blocks it.
- Bug found while testing: `/qa:bug` writes the report and files it as a ticket labelled
  "QA testing"; never patch it from the QA step.
- Scout (read-only) tasks: use `/developer:diagnose`, `/designer:review` or `/qa:plan` without
  changing code, and put the findings in the report this brief names.
- Backlog or issue grooming: `/scrum-master:refine`, then file the stories with the
  `ticket-management` skill (`tickets.py batch`) on the board this brief names.
- Tickets: the developer and scrum-master plugins manage them: create, edit or close
  tickets and move board cards with their `ticket-management` skill when the task calls for
  it. QA creates and edits tickets only, never closes or deletes one, and labels every
  ticket it creates "QA testing". List each ticket you write with its link in your report.
  A designer finding that needs a ticket, or a designer spec for a ticket, goes in your
  report for the developer or scrum-master step to file or attach. Delete a ticket only when this brief
  names it for deletion; otherwise close it as not planned.
- New project board: `/scrum-master:create-board`, only when this brief asks for a board.
- Only the developer, scrum-master, designer and qa plugins are for crew work.
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
