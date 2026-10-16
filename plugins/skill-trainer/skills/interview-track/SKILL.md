---
name: interview-track
description: Trains for the technical phases of senior engineering interviews, coding and system design, with the screening round skipped. Works through about twenty coding patterns as timed drills in a configurable language (Node by default) and through staged system-design problems with a fixed seven-step framework, tracks which patterns and designs hold up, and brings the weak ones back. Use when preparing for coding or system design interviews, asking for a coding drill, a LeetCode-style problem or a design question, checking interview readiness, or switching the interview coding language.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Interview track

Interviews test two things that daily work does not: recognizing a pattern in
a problem you have never seen, under a clock, and designing a system out loud
with numbers. This track trains only those two. Screening and behavioral
rounds are out of scope.

The track shares its state and scheduler with the `training-plan` skill. Use
its script:

```bash
python ../training-plan/scripts/trainer.py interview                  # progress per pattern and design
python ../training-plan/scripts/trainer.py topics --track interview
python ../training-plan/scripts/trainer.py config set focus interview # every session is coding or design
python ../training-plan/scripts/trainer.py config set interview-language Node   # or Python, TypeScript...
python ../training-plan/scripts/trainer.py config set interview-date 2026-11-20
python ../training-plan/scripts/trainer.py log --topic graphs-bfs-dfs --score 3 --kind practice
```

## Coding drills

- Load [references/coding-patterns.md](references/coding-patterns.md). It
  covers each pattern's signal, its template, and the language notes for the
  interview language (harness and gotchas).
- Choose a real problem for the pattern. Don't name the pattern: recognizing
  it is half of what is tested.
- Order inside a drill:
  1. restate the problem;
  2. clarify;
  3. state a brute force and its complexity;
  4. the better approach;
  5. code;
  6. test with an empty or degenerate input;
  7. complexity.

  The user talks throughout. Silent coding is a finding.
- Time boxes: easy 20 min, medium 30 min, hard 40 min. When the box runs out,
  stop and grade what exists.
- After a miss, show the intended approach and have the user rewrite it from
  scratch, without looking, before logging. Log the score of the first
  attempt, not the rewrite.

## System design

- Load [references/system-design-framework.md](references/system-design-framework.md)
  and run its seven steps in order, with the times it gives.
- Take the designs in level order: L1 before L3. `sd-framework-estimates`
  comes first if it has never been done.
- Play a senior interviewer:
  - ask one question at a time;
  - make the user choose rather than list options;
  - ask "what breaks first at 10x?" once the design is up.

## Readiness

`interview` shows practised versus total per area. Before a real interview:

- **Coding.** Every L1 and L2 pattern practised at least once, with a last
  score of 3 or more, and the L1 ones at 4 or more.
- **Design.** At least six designs practised, including two L3, and at least
  two full mocks.
- **Mocks.** One full mock per phase in the last week before the interview.
  Use `/interview-prep:mock` when that plugin is installed, so the grader
  hasn't seen this plan. Log the mock with `--kind mock`.

Say plainly which of these does not hold yet, and how many sessions it needs
at the current cadence. When the user has a real job description and dated
rounds, point them to `/interview-prep:prep` for the loop itself. This track
keeps training the skills underneath it.
