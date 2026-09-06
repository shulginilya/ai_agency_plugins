---
name: opportunity-triage
description: Decides whether a job ad, contract gig or RFP is worth pursuing — scores it against a declared profile, names the must-haves it is missing and the deal-breakers it trips, and returns pursue, skip or unclear with the reason. Use when the user pastes or links a posting and asks whether to apply or bid, whether a role is a fit, or wants a shortlist cut down.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Opportunity triage

Most of a job search is spent on postings that were never going to work. The
job here is to spend ninety seconds killing those, so the remaining time goes
into applications that are actually tailored.

The failure mode to avoid is agreeableness. A model asked "is this a fit?"
will find a way to say yes, because every posting contains *something*
encouraging. Skip is the more valuable verdict, and it needs to be reachable.

## 1. Score what is countable

```bash
python scripts/fit.py posting.txt
python scripts/fit.py - --json          # paste the posting on stdin
python scripts/fit.py --init            # first run: write .jobhunt/profile.json
```

The script is a rule engine, not a judgement. It reports must-have coverage,
deal-breakers, track (contract vs permanent), location or remote policy, and
whether money is named at all. Its exit codes are four different answers:
0 pursue, 1 skip, 3 unclear, 2 unusable — a posting that does not say whether
it is remote is *unclear*, which is not the same as a bad fit, and the two lead
to different next actions.

If there is no profile yet, stop and build one with the user before triaging.
Guessing at their must-haves and then scoring against the guess produces
confident nonsense.

## 2. Read what is not countable

The script cannot see the things that actually predict a bad engagement. Read
the posting yourself for the signals in
[references/posting-signals.md](references/posting-signals.md) — load it on the
first posting of a session and work from it.

The short version: who wrote it, how specific the work is, how many
responsibilities are stacked into one role, whether the process is described,
and whether the money is stated. A posting that hides the rate is a posting
that intends to negotiate from your number.

## 3. Decide, and say why

Report in this shape, whatever the verdict:

```
<PURSUE|SKIP|UNCLEAR> — <company>, <role>
Fit: <the must-haves present, and the ones missing>
Against: <deal-breakers, gaps, or signals from the posting>
Unknown: <what the posting does not say and you would have to ask>
Effort: <what a real application here costs — a tailored proposal, a take-home>
Next: <apply / ask X first / skip>
```

Rules that keep triage useful:

- **A gap is a fact, not a disqualifier.** "Missing Kubernetes" is worth
  reporting; whether it matters depends on whether the role is built on it or
  merely lists it. Say which.
- **Skip needs a reason the user could disagree with.** "Not a great fit" is
  not one. "Wants five years of Rust; the profile has none" is.
- **Unclear is a real verdict.** When the posting does not say the thing that
  decides it, the output is the question to ask, not a guess dressed as a
  score.
- **Do not inflate a match by counting the same skill twice.** Three mentions
  of TypeScript is one must-have, not three.
- **Effort belongs in the decision.** A 70% fit with a one-paragraph
  application beats a 90% fit behind a four-hour take-home, when the pipeline
  is thin and time is the constraint.

## 4. Put it in the pipeline

A pursued posting that stays in a chat window is a lost posting. Hand it to the
`application-pipeline` skill to record, and to `application-tailoring` to write.

Where the harness supports subagents, give each posting in a batch to its own
`screener` run so a long shortlist does not get progressively more agreeable as
one context fills up.
