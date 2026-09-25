# Grading a mock round

Four levels, and the fourth is the one that keeps the rest honest.

| Level | Means |
| --- | --- |
| **strong** | would be cited in a hire recommendation; specific, owned, survived probing |
| **adequate** | the bar is met; nothing memorable either way |
| **weak** | a real interviewer would write this down as a concern |
| **no signal** | the round never reached it, or the answer did not contain it |

**No signal is not adequate.** Collapsing them is how a mock comes back clean
after a round that never tested half of what it should have. If the time box ran
out before the failure modes came up, the failure-modes dimension has no signal,
and the fix is to run the round again with better pacing — not to assume it
would have been fine.

## Verdict

**hire / lean hire / lean no / no** — one per round, plus the single sentence a
real interviewer would type into the feedback box. Write that sentence as they
would write it, not as encouragement.

A useful calibration: in most loops, *lean no* is the modal outcome for a
candidate who is not yet prepared, and it is the grade that produces work. If
every mock comes back *lean hire*, the mock is broken.

## Dimensions per round

### Recruiter screen
- Narrative: 90 seconds, coherent, lands on this role
- Reason for leaving: honest, forward-looking, not a complaint
- Compensation: a range, with a justification, asked back
- Logistics: notice period, availability, location, stated without hedging

### Live coding
- Communication: thinking audible, assumptions stated
- Problem solving: progress made, approach chosen for a reason
- Correctness: it runs; edge cases found unprompted
- Code quality: names, structure, no dead cleverness
- Pace: got to a working answer with time to extend it
- Response to hints: heard, incorporated, not fought

### Take-home review
- Ownership: every decision defensible
- Trade-offs: omissions named before being asked
- Testing: tests exist and test behaviour
- Judgement: effort spent where the brief pointed

### System design (both kinds)
- Requirements: clarified before designing; numbers stated
- Decomposition: components with clear responsibilities and data flow
- Data: model, access patterns, consistency
- Trade-offs: one design chosen and defended, alternatives named
- Failure: what breaks, what happens then, what is monitored
- Cost and scale: an actual number, and the bottleneck at 10×
- *AI rounds also:* evaluation (what "good" means, the eval set, and who wrote
  it), guardrails, latency budget, and the plan for the model being wrong in
  production

### Behavioral
- Specificity: one real situation, dated, with a stake
- Ownership: first person; their contribution separable from the team's
- Outcome: a measurable or concrete result
- Reflection: what they would do differently, without self-flagellation
- Survival: held up under three levels of "and what did you do?"

### Hiring manager / leadership
- Fit to the problem: a view about their actual work
- Working style: concrete, with an example
- Influence: changed something without authority to order it
- Questions asked: specific, about constraints, not perks

## Writing the feedback

1. **Quote before you judge.** Every level cites something they said. "Weak: no
   edge cases" is an assertion; "Weak: when asked about an empty input you said
   'that would not happen in practice'" is feedback.
2. **One rewrite.** Show the better version of the single weakest answer, in
   their voice, using only facts they gave you. Three rewrites get skimmed.
3. **Name the pattern once.** If the same problem appeared in four answers, say
   it once as a pattern, not four times as four findings.
4. **End with the next action**, and make it small enough to do today: "write
   the number down for the checkout story" beats "work on metrics".

## What not to do

- Do not grade the person. "You are not ready for senior" is not a finding; "the
  design round had no numbers in it" is.
- Do not soften a weak grade with a compliment sandwich. State the level, cite
  the evidence, give the fix.
- Do not credit an answer for something the user said earlier in the session or
  wrote in their story bank. The interviewer did not hear it.
- Do not let a strong personality carry a weak answer. Fluency is not signal.
