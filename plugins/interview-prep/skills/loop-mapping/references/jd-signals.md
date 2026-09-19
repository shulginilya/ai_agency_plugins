# Reading a description for what the interview will test

A keyword scan tells you which technologies appear. It does not tell you what
the rounds are about. These are the things to read for by hand.

## Which requirements are load-bearing

- **What the role is built on** appears in the responsibilities, not only in the
  bullet list of technologies. "You will own our event-driven ingestion
  pipeline" makes Kafka load-bearing; "Kafka, RabbitMQ or similar" in a list of
  nine tools does not.
- **Repetition across sections** is the strongest signal. A skill named in the
  intro, the responsibilities and the requirements is the one the technical
  round is built on.
- **The wishlist tell**: a requirements list longer than eight items was written
  by committee. Interviewers test three or four of them. Pick the ones that
  match the responsibilities.
- **Years of experience are almost never scored directly.** "5+ years of React"
  is filtering; the round tests judgement about React.

## What "you will own X" means for the design round

Ownership language changes what the design round is about. Compare:

| The description says | The design round will be about |
| --- | --- |
| "build features in our platform" | can you decompose a feature and reason about the edges |
| "own the architecture of X" | trade-offs, migration paths, what you would do differently |
| "scale X from A to B" | bottlenecks, measurement, cost, the failure mode at B |
| "introduce X to the team" | adoption, convincing people, what you do when they resist |

For an AI or LLM role, the same reading applies: "build RAG pipelines" is a
components-and-dataflow round; "make our agent reliable" is an evaluation,
guardrails, cost and latency round, and the interviewer wants to hear the word
*evals* without prompting.

## Seniority calibration

Read the title against the verbs. A "Senior" title attached to "execute on a
defined roadmap", "work closely with the tech lead" and no mention of mentoring,
architecture or stakeholders is a mid-level role with a senior label — there
will be no leadership round, and leadership answers will land as overreach.

The reverse — a "Mid-level" title asking for architecture ownership, mentoring
and on-call leadership — is a senior role priced low. That is a compensation
conversation, and it belongs in the first call.

## Signals about the process itself

- **A stated process** ("our interview process is…") is the best paragraph in
  any ad. Take it literally and prepare exactly it.
- **"Culture fit" or "values interview"** named explicitly means a scored
  behavioural round against a published list. Find the list on their site.
- **A named tool** (HackerRank, Codility, CoderPad) tells you the format of the
  coding round: timed, browser-based, and usually algorithmic rather than
  practical.
- **"Take-home" plus a stated time box** is usually honest about the time box.
  "Small take-home" with no number is not.
- **No process, no salary, no team size** in a long ad means the ad was written
  to attract, not to inform. Ask before preparing.

## Warning signs worth naming to the user

- Three roles in one description (build the platform, manage the team, talk to
  customers) — the loop will test all three and the job will be all three.
- "Fast-paced" plus "wear many hats" plus no mention of process or testing.
- A senior title with a junior salary band, where the band is stated.
- A description that has clearly been reposted for months — the bar is either
  impossible or the team is churning.

None of these are reasons not to interview. They are reasons to ask a specific
question in the first call, and the answer is usually more informative than the
whole description.
