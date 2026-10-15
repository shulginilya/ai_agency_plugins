---
name: bug-reporting
description: Writes a bug report a developer can reproduce on the first try — title, exact steps from a clean start, expected versus actual, environment and commit, severity with its reason, evidence, and what was ruled out — ready for developer or scrum-master to file as a ticket. Use when asked to report, write up or log a bug, describe a failure found in testing, or turn a QA failure into a ticket.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
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

## Hand it over

QA doesn't file tickets. Give the report in your reply, or in your report
under a crew brief. Developer or scrum-master files it with their
`ticket-management` skill. One bug per report, even when several came up in
one session. Say if it's related to another bug.
