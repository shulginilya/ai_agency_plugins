---
name: application-pipeline
description: Tracks every job application or contract bid through its stages in a markdown table, and says what needs chasing today — what is overdue, what has gone quiet, and what has no next action at all. Use when the user asks what is in their pipeline, what to follow up on, wants an application or bid recorded, or wants to move one to a new stage.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Application pipeline

A search fails in the gaps, not in the applications. Something was sent and
never chased, a recruiter went quiet and nobody noticed for three weeks, an
interview was promised and never scheduled. The tracker exists to make those
visible on the day they happen.

The file is a markdown table in the user's own repo — readable, diffable, and
theirs. Never reconstruct it from memory; read it, change it with the script,
and let the script write it.

## The commands

```bash
python scripts/pipeline.py init
python scripts/pipeline.py due                          # what needs action today
python scripts/pipeline.py list --stage applied
python scripts/pipeline.py add --company Acme --role "Senior AI Engineer" \
    --track contract --source freelancermap --link https://... \
    --next "send proposal" --due 2026-09-10
python scripts/pipeline.py move Acme --to screening --next "prep call" --due 2026-09-12
```

`due` exits 1 when something needs action and 0 when nothing does, so it works
as a check rather than something to read every time. Every write backs the file
up to `.bak` first and refuses a table it cannot parse.

## Stages

`sourced → applied → screening → interview → offer → closed`

Move a row the moment reality moves, not at the end of the week. `closed`
covers rejected, withdrawn and accepted alike — the outcome belongs in the next
action column, and a closed row stops appearing in `due`.

## Every open row needs a next action and a date

This is the whole discipline, and the script enforces it: an open row with no
next action is reported under "needs a date" no matter how recently it moved.
"Waiting to hear back" is not a next action — the next action is *what you do
when they still have not replied by Thursday*.

Dates are ISO and only ever come from the user. If they say "chase them next
week", ask for the day or compute it from today and say which date you used.
Never write a due date the user did not agree to.

## What `due` reports

| Bucket | Means | The move |
| --- | --- | --- |
| OVERDUE | the due date has passed | do it now, or re-date it deliberately |
| stale | no movement in 10+ days | chase, or close it honestly |
| needs a date | open with no next action | decide the next action, or close it |
| upcoming | due within 3 days | know it is coming; do not act yet |

Report these grouped, shortest first, and offer the specific action for each —
"send the follow-up to Acme" beats "you have 3 overdue items".

## Rules

- **Read before writing.** Always `list` or `due` first; the user may have
  edited the file by hand since you last saw it.
- **One entry per opportunity, not per contact.** Two recruiters for the same
  role is one row; note it in the next action.
- **Never invent a stage transition.** If the user says "I think they replied",
  ask before moving the row. A tracker that reflects hopes is worse than none.
- **Close things.** A pipeline of forty rows where thirty are dead teaches the
  user to ignore it. Suggest closing anything stale past a month.
- **Do not editorialise in the table.** Feelings about a process go in the
  conversation; the row holds facts.
