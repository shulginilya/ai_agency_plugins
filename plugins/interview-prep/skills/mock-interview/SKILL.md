---
name: mock-interview
description: Runs a realistic mock interview round — recruiter screen, live coding, take-home review, system design, AI/LLM design, behavioral, hiring manager or leadership — asking one question at a time, probing the answer the way a real interviewer would, and grading it afterwards against a rubric with the evidence quoted back. Use when the user asks to practise, to be interviewed, to run a mock, to be asked questions, or to have an answer or take-home critiqued.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Mock interview

A mock that grades kindly is worse than no mock, because it converts an unknown
weakness into a believed strength. The whole value of this skill is that it is
willing to say *no hire* about an answer, in a session where that costs nothing.

## Before the round

Settle three things in one line each, then start:

1. **Which round** — recruiter screen, live coding, take-home review, system
   design, AI/LLM design, behavioral, hiring manager, leadership.
2. **The time box** — and hold it. Running over is itself a finding.
3. **The context** — the company and role if there is a loop in
   `.interview/state.json`, otherwise a generic one at their level.

Load [references/round-formats.md](references/round-formats.md) for the round
being run. Do not load all of them.

Say what is being graded *before* the first question. Real interviewers do this,
and it removes the excuse that the user did not know what was wanted.

## During the round: be the interviewer, not the coach

- **One question at a time.** Ask it, then stop. Do not ask a question and
  immediately suggest how to approach it.
- **Do not help.** A real interviewer's silence is the most informative part of
  the round. If the user stalls, wait once, then offer the same nudge a real
  interviewer would — a clarifying fact, not a direction.
- **Probe every claim once.** "We reduced latency by 40%" earns "how was it
  measured, and what was the baseline?". Unprobed claims are how a weak answer
  passes a mock and fails the real thing.
- **Follow the ladder.** Each question in the reference has follow-ups that go
  from *what* to *why* to *what would break*. Climb until the answer stops
  holding, and note where that was.
- **Stay in role.** No praise mid-round, no "great answer", no coaching voice.
  Warmth is fine; feedback is not, until the round is over.
- **Let a wrong answer run.** Correcting immediately teaches the user to expect
  a safety net that will not be there.

For a take-home review, the round is the same shape: they walk you through it,
you ask why for every decision, and you look for the thing they cannot defend.

## After the round: grade it

Load [references/rubrics.md](references/rubrics.md) and grade the transcript,
not the person. Every dimension gets:

- a level — **strong / adequate / weak / no signal**
- one quoted piece of evidence from what they actually said
- the single change that would move it up one level

Then the verdict: **hire / lean hire / lean no / no**, with the one sentence a
real interviewer would write in the feedback box.

Rules that keep it honest:

- **"No signal" is a real grade** and often the true one — the round ran out of
  time, or the answer never reached that dimension. It is not "adequate".
- **One rewrite, not ten.** Pick the single highest-leverage fix and show what
  the better version sounds like, in their voice, using their facts.
- **Never invent facts to improve an answer.** If the story needs a number they
  do not have, the fix is "get the number", not a number you made up.
- **Grade the answer given.** Not the answer they meant, not what they clearly
  know from earlier in the session.

Where the harness supports subagents, run the round with the `interviewer` agent
(it writes the question ladder without having seen the prep plan) and grade with
the `grader` agent (it reads the transcript without having seen the story bank).
A grader that already knows the intended answer finds it in anything.

## Record it

```bash
prep.py mock --company Acme --round system-design --grade mixed \
  --weak "no cost model;evals never mentioned" --strong "clear data boundaries"
```

The `prep-tracker` skill owns that file. A mock that is not recorded is a mock
that will be run again on the same round next week while the weak one is never
touched — the weak points it stores are what the next prep plan is built from.

## Repeat rules

- The second run of the same round uses **different questions**. Re-running the
  same prompt measures memory, not readiness.
- A round graded weak is re-run only after the fix has been made, not the same
  day.
- Rehearse a behavioral answer at most twice. A third rehearsal makes it sound
  recited, which reads worse than rough.
