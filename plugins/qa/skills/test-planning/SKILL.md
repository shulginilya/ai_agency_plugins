---
name: test-planning
description: Turns a ticket's acceptance criteria into a test plan before the work is built — every criterion mapped to happy-path, edge and boundary, negative, regression and (for UI) accessibility cases with the data and the expected result — and flags criteria that cannot be tested as written. Use when asked to write test cases or a test plan, plan QA for a ticket, check whether acceptance criteria are testable, or decide what to test before a change is built.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Test planning

A test plan is the ticket's promises turned into checks someone else could
run. A plan written before the code exists finds the gaps in the ticket while
they are still cheap to fix.

```bash
python scripts/criteria.py --issue 42                 # the criteria, numbered, with problems flagged
python scripts/criteria.py --issue 42 --repo owner/app
python scripts/criteria.py --file ticket.md --json
```

## 1. Read the ticket and its criteria

Run `criteria.py`. It numbers the criteria AC1, AC2, … and flags each one
that can't be tested as written: a vague word ("fast", "intuitive",
"properly") or no observable result. A ticket with no criteria exits 2.
That is a finding: say so and stop. There's nothing to plan against.

For each flagged criterion, propose a testable rewording, such as "fast" →
"the list renders within 1 s for 500 items". Then report it. Don't silently
test your own interpretation.

## 2. Write the cases

For every criterion, cover the kinds that apply. The full checklist is in
[references/case-design.md](references/case-design.md):

| Kind | Asks |
| --- | --- |
| happy | does the promised thing happen with ordinary input? |
| edge / boundary | empty, one, many, max, one past max, long text, unicode, zero, negative |
| negative | wrong input, missing permission, network down, the second click |
| regression | what nearby behaviour must still work after this change? |
| accessibility | for UI: keyboard only, screen-reader names, contrast, focus |

Each case gets an id (`AC2-3`), its kind, the steps, the data, and the
expected result as something you can see or measure. One criterion usually
needs 2–5 cases. Twenty means the criterion is really several.

## 3. Hand the plan over

Put the plan in your reply, or in your report under a crew brief:

```
AC1 — <criterion>
  AC1-1 happy     steps · data → expected
  AC1-2 boundary  …
Untestable as written: AC3 "loads fast" → propose "renders within 1 s for 500 items"
Not covered by any criterion: <behaviour the ticket implies but never states>
```

QA doesn't write tickets. Proposed criterion rewrites go to developer or
scrum-master, who edit the ticket.
