---
name: backlog-refinement
description: Turns raw requests, bug reports and one-line ideas into GitHub issues a team can actually start — a user-value statement, testable acceptance criteria, a size, and a slice small enough to finish inside one sprint. Use when the user asks to refine or groom the backlog, write or rewrite a user story, add acceptance criteria, split a ticket that is too big, estimate work, or check whether the backlog is ready for planning.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Backlog refinement

Refinement has one job: make the next few items startable. An item is startable
when a developer who was not in the conversation can pick it up and know when
they are done.

## Read the backlog first

```bash
python scripts/backlog.py                       # open issues, with readiness
python scripts/backlog.py --not-ready           # only the ones that block planning
python scripts/backlog.py --milestone "Sprint 12" --json
```

The script shells out to `gh`. If `gh` is missing or unauthenticated it exits 2
and says so — fall back to `gh issue list` output the user pastes, or to the
issue text in the conversation. Never invent issue numbers or titles.

Refine the top of the backlog, not all of it. Two sprints of ready work is
enough; refining further ahead is work that gets thrown away when priorities
move.

## The Definition of Ready

Check every item against these five. `scripts/ready.py` applies the mechanical
subset of them, but the judgement calls are yours.

1. **Value.** Who wants this and what do they get? "As a `<role>` I want
   `<capability>` so that `<outcome>`" is one way; a plain sentence naming the
   user and the outcome is just as good. A ticket whose value line is "the code
   should be cleaner" is a task, not a story — say so and let the team decide
   whether it belongs in a sprint at all.
2. **Acceptance criteria.** At least two, each observable. "Given / When /
   Then" or a checklist both work. The test: could QA mark it pass or fail
   without asking the author a question?
3. **Size.** Fits in one sprint with room to spare, and has an estimate the
   team agreed on. If it needs the whole sprint, it is too big — see
   [references/splitting.md](references/splitting.md).
4. **Dependencies known.** Anything it waits on — an API, a design, a decision,
   another team — is named and either resolved or tracked. "TBD" in the body
   means not ready.
5. **No open questions.** Questions belong in refinement, not in the sprint.
   One unanswered question is the most common reason a committed item does not
   finish.

Load [references/invest.md](references/invest.md) when an item passes the
checklist mechanically but still feels wrong — INVEST names the failure.

## The refinement loop

For each item, in order:

1. **Read it whole**, including comments. Half of "vague" tickets have the
   missing detail three comments down.
2. **Restate the value in one sentence.** If you cannot, the item needs a
   conversation, not an edit — say what you would ask and stop.
3. **Write acceptance criteria** covering the happy path, one failure path, and
   one boundary. Three is usually right; ten means the item is two items.
4. **Check the size.** Apply [references/estimation.md](references/estimation.md).
   If it is too big, split it before estimating — never estimate an item you
   already know you will split.
5. **Name what is missing.** Design, data, a decision, an owner. Missing things
   go in the body as a checklist, not in your head.

## Writing it back

Propose the rewritten body, then apply it only when the user says to:

```bash
gh issue edit 42 --body-file /tmp/issue-42.md
gh issue edit 42 --add-label "size/M" --milestone "Sprint 12"
```

Keep the original title unless it misdescribes the work. Renaming tickets
breaks the links people have already pasted into chat.

## The shape to write

```markdown
As a <role>, I want <capability> so that <outcome>.

## Acceptance criteria
- [ ] Given <state>, when <action>, then <observable result>
- [ ] Given <failure state>, when <action>, then <what the user sees>
- [ ] <boundary: empty, maximum, unauthorised>

## Out of scope
- <the thing a reader will otherwise assume is included>

## Notes
- Depends on: <issue, design, decision — or "none">
- Open questions: <none, or this item is not ready>
```

`## Out of scope` is the highest-value line in the template. Most sprint
overruns are scope a reader assumed, not scope anyone wrote down.

## Rules that keep refinement honest

- **Do not estimate to make the number look good.** If the team does not know
  how long something takes, the answer is a spike with a time box, not a 5.
- **Split before you shrink.** Cutting acceptance criteria to make an item fit
  produces an item that ships nothing. Cut a vertical slice instead.
- **A bug is ready when it has reproduction steps and expected behaviour.**
  Value statements on bugs are theatre; skip them.
- **Refuse to refine what is not prioritised.** If nobody can say why this is
  above the item below it, refinement is premature.
- **Leave items not-ready when they are not ready.** A backlog that reports 12
  ready items and has 4 is worse than one that reports 4.
