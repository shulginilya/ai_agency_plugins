---
name: prep-tracker
description: Keeps the state of every interview loop the user is in — the rounds and their dates, the prep items ranked by risk, mock results with their weak points, and debriefs of real rounds — and reports what needs doing today. Use when the user asks what is coming up, how ready they are, wants a round or prep item recorded, or has just finished a real interview and wants to capture what was asked.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Prep tracker

Interview preparation fails in the gaps: a round nobody prepared for because it
was never written down, a weak point found in a mock and never fixed, a real
round whose questions were forgotten within a day. This skill owns the file that
makes those visible.

`.interview/state.json` is the source of truth. `.interview/brief.md` is
rendered from it, one way only. Never reconstruct the state from memory or from
the rendered markdown — read it, change it with the script, let the script
write.

## The commands

```bash
python scripts/prep.py init
python scripts/prep.py add --company Acme --role "Senior AI Engineer" \
    --source .interview/jd/acme.txt --archetype scale-up \
    --rounds recruiter-screen,live-coding,system-design,behavioral
python scripts/prep.py round --company Acme --round system-design --date 2026-09-29
python scripts/prep.py item --company Acme --add "RAG eval story with numbers" \
    --risk high --round system-design --due 2026-09-25
python scripts/prep.py item --company Acme --done "RAG eval"
python scripts/prep.py mock --company Acme --round system-design --grade mixed \
    --weak "no cost model;evals never mentioned" --strong "clear data boundaries"
python scripts/prep.py debrief --company Acme --round live-coding \
    --asked "LRU cache;debounce hook" --gap "froze on the follow-up" --outcome advanced
python scripts/prep.py status
python scripts/prep.py render
```

Round names are fixed: `recruiter-screen`, `hiring-manager`, `live-coding`,
`take-home`, `system-design`, `behavioral`, `panel`, `leadership`.

## What `status` answers

| Exit | Verdict | Means | The move |
| --- | --- | --- | --- |
| 0 | clear | nothing needs action today | say so and stop |
| 1 | action | something is due, overdue, or a round happened undebriefed | do the named thing |
| 2 | unusable | no state file, or a file that is not one | `init`, or ask which file |
| 3 | undeclared | a scheduled round has no prep and no mock | readiness cannot be judged — fix that first |

Exit 3 outranks exit 1 deliberately. "Two prep items are overdue" is a smaller
problem than "there is a round on Thursday that nothing has been done for", and
the second is invisible unless it is reported as its own answer.

The buckets `status` reports, in the order they matter:

| Bucket | Means |
| --- | --- |
| happened, not debriefed | the date passed and nothing was captured |
| overdue prep | an open item whose date has passed |
| rounds within 3 days | the ones that set this week's work |
| scheduled with nothing prepared | no prep item, no mock — the exit-3 case |
| rounds with no date | a round is coming and nobody asked when |
| prep with no date | an item that will never be done |
| open weak points | what the mocks found and nobody fixed |

Report these grouped, and turn each into a specific action — "write the cost
model for the Acme design round" beats "you have 3 open items".

## Rules

- **Dates come from the user.** The script rejects "next week". Convert it, say
  which date you used, and get agreement before writing it.
- **Read before writing.** Run `status` first; the user may have edited the file
  or sat a round since the last session.
- **Never invent a stage change.** If the user says "I think it went well", that
  is not a debrief and not an outcome. Ask.
- **A mock that is not recorded did not happen.** Its weak points are what the
  next prep plan is built from.
- **Close things.** A loop that ended goes to `--outcome rejected` on its last
  debrief and stops appearing. A tracker full of dead loops teaches the user to
  ignore it.
- **Keep the plan to three to five open items per loop.** More than that is a
  list, not a plan, and lists do not get done.

## Debriefs are the highest-value entry in the file

Within a day of a real round — ideally within the hour — capture what was
actually asked, verbatim where possible, and what went badly. This is worth more
than any prediction:

- it corrects the inferred loop for the remaining rounds at that company
- it tells the `loop-mapping` skill what this archetype really does
- it turns "I think I flunked the design round" into a named weakness the next
  mock can target

```bash
python scripts/prep.py debrief --company Acme --round system-design \
    --asked "design multi-tenant RAG;how would you evaluate it" \
    --gap "no answer on per-tenant isolation" --outcome waiting
```

The script refuses a debrief with no questions recorded, because a debrief
without them teaches nothing.

See [references/prep-cadence.md](references/prep-cadence.md) for what to do in
the three weeks, one week, 48 hours and two hours around a round.
