---
name: bug-reporting
description: Writes a bug report a developer can reproduce on the first try — title, exact steps from a clean start, expected versus actual, environment and commit, severity with its reason, evidence, and what was ruled out — and files it as a GitHub ticket labelled "QA testing". Use when asked to report, write up or log a bug, describe a failure found in testing, or turn a QA failure into a ticket.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Bug reporting

A bug report is useful when someone who wasn't there can make the bug happen
again. Everything in it serves that, or the decision of how soon to fix it.

## Reproduce it first

Make it happen twice from a clean start before writing anything. If it only
happens sometimes, run it ten times and say how often ("fails 3 of 10").
That frequency is part of the report, not a reason to skip it.

Cut the steps down. Remove each step and check whether the bug still
happens. The shortest path that still fails is the report.

## The report

```markdown
**<Where>: <what goes wrong>, <in what situation>**
e.g. "Upload dialog: no error and the upload starts for a file over 10 MB"

Severity: blocker | major | minor | trivial — <the reason, in user terms>
Found by: <ticket and acceptance criterion, e.g. #42 AC2, or exploratory>
Build: <commit sha or deployed version> · <environment: OS, browser, device>

Steps (from a clean start):
1. …
2. …

Expected: <what the ticket or a reasonable user expects, citing the criterion>
Actual: <what happens, quoting exact messages>
Frequency: always | N of M runs

Evidence: <screenshot or recording path, console or server log lines, response body>
Ruled out: <what you checked that does not matter: another browser, a fresh account, cleared cache>
```

## Severity

| Level | Means |
| --- | --- |
| blocker | a user can't finish the task, data is lost or exposed, or there's no workaround |
| major | the task completes wrongly or with real effort; a criterion fails |
| minor | friction or a cosmetic fault with an easy workaround |
| trivial | wording, spacing, an inconsistency nobody is slowed by |

Pick severity by the effect on the user, not by how hard the fix looks.

## File it

QA creates the ticket itself with the `ticket-management` skill. Every ticket
QA creates carries the **QA testing** label, so the team can see what came
out of testing:

```bash
python ../ticket-management/scripts/tickets.py create --title "<title>" --body-file report.md \
    --label "QA testing" --create-missing-labels [--project N --status Backlog]
```

- One bug per ticket, even when several came up in one session. Link a
  related bug in the body ("Related: #N").
- Before creating, check that it isn't already filed
  (`gh issue list --search "<key words>" --state all`). If it is, add your
  findings to that ticket with `edit` or a comment instead.
- In a conversation, show the report first and create the ticket after a yes.
  Under a crew brief, create it and list its link in your report.
- QA creates and edits tickets, but never closes or deletes one. That stays
  with developer and scrum-master.
