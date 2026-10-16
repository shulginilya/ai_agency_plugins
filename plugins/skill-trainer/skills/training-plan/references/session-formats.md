# Session formats

Load only the section for the item being run.

---

## coding

**Goal:** recognize the pattern under time pressure and write code that runs.

1. Pick one real problem for the pattern from the hints, or a close variant.
   The difficulty follows the topic's level: easy for L1, medium for L2,
   medium or hard for L3. For a review, use a different problem than last time.
2. State the problem the way an interviewer would, without naming the pattern.
3. The user restates the problem, asks clarifying questions, and talks through
   an approach before writing code.
4. The user writes the solution in a file in the item's `language`, with a few
   tests. The harness for each language is in the interview-track skill's
   `references/coding-patterns.md` (for Node: `node --test`). Run it.
5. Review it:
   - complexity in time and space;
   - the edge cases missed;
   - a cleaner or faster approach, if one exists, shown only after their
     attempt.
6. Time box: L1 20 min, L2 30 min, L3 40 min.

A `react-ui-*` item is a frontend coding round instead:
- clarify the requirements;
- sketch the component tree and the state shape;
- build it working end to end;
- handle the loading, error and empty states, plus keyboard and ARIA;
- write one test.

Time box: 45 min. The React section of `coding-patterns.md` has the setup.

Score 4 needs a working solution inside the box with the complexity stated.
Score 5 also needs no hints and a clean first structure.

---

## design

**Goal:** turn a vague prompt into a system, and name what it costs.

Run the 7-step framework from the interview-track skill's
`references/system-design-framework.md`. Play the interviewer:
- one question at a time;
- push for numbers;
- probe the bottleneck and a failure.

Time box: 35–45 min daily, 60 min in a weekly session. For
`sd-framework-estimates`, drill estimates: give three quick prompts (for
example "10M DAU photo app: storage per year?") and check the arithmetic.

Score 4 needs requirements first, explicit numbers, one design with its
trade-off, and a failure mode. Score 5 also needs a strong deep dive and
anticipating the probes.

---

## deep-dive

**Goal:** know the technology below the API: why it behaves the way it does.

1. **Retrieval first.** Ask 4–5 questions on the topic before explaining
   anything, for example "what happens to a `setState` call inside a
   `setTimeout`?" Wrong answers show what to teach.
2. **Explain the gaps,** briefly, with a minimal example.
3. **Experiment.** The user writes a 10–20 line snippet that proves or breaks
   the behaviour. Run it.
4. **Explain back.** The user explains the mechanism in 3–4 sentences, as if
   to a junior engineer.

Time box: 30 min. Score from the retrieval answers and the explain-back.

---

## practices

**Goal:** apply one engineering practice to real work, not read about it.

1. Five-minute primer on the topic: the two or three ideas that matter.
2. Apply it to the user's own code. Ask which repository. If there is none,
   use a realistic scenario. Examples:
   - find one N+1 query;
   - write the SLOs for one endpoint;
   - list three OWASP risks in one handler.
3. Write the result down as a concrete next step they could do at work.

Time box: 30 min. Score from how specific and correct the applied result is.

---

## build

**Goal:** ship something small end to end, with tests.

1. Write a one-screen spec: what it does, the interface, and 3–5 acceptance
   criteria.
2. The user builds it in a scratch folder or repository of their choice, in
   the stack the topic names. A build may span two or three sessions. Log
   after each one, with a note on what is left.
3. Check each acceptance criterion by running it. A criterion that wasn't
   checked doesn't pass.

Time box: 45–90 min per session. Score at the final session against the
criteria. Score earlier sessions on progress against the plan.

---

## review

Only due items. Use a different problem or question than last time, run the
item in its own area's format, but shorter. If nothing is due, run the weakest
topic.

---

## mock

A full, graded round. When the interview-prep plugin is installed, hand off to
`/interview-prep:mock live-coding` or `/interview-prep:mock system-design`. Its
interviewer and grader have not seen this plan. Map its grade back:
- strong → 4;
- mixed → 3;
- weak → 2.

Then log with `--kind mock`. Without interview-prep, run the coding or design
format at full length (45–60 min), with no hints, and grade it strictly.
