---
description: Diagnose a bug down to its root cause — reproduce it, narrow it, prove the mechanism — without changing code.
argument-hint: "[the symptom: an error, a failing test, wrong behaviour]"
model: claude-opus-5-5
effort: high
allowed-tools: Bash Read Grep Glob
---

Diagnose: $ARGUMENTS

If that is empty, ask for the symptom before doing anything else — observed
behaviour, expected behaviour, scope, and when it started.

Follow the `root-cause-analysis` skill. Do not edit any file in this command;
the deliverable is a proved cause, not a patch.

1. Restate the symptom in the skill's four parts. If onset is "it used to
   work", stop and run `/bisect` instead — the history is faster than the code.
2. Establish a reproduction:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/root-cause-analysis/scripts/repro.py" --discover
   python "${CLAUDE_PLUGIN_ROOT}/skills/root-cause-analysis/scripts/repro.py" --cmd "<repro>" --times 10
   ```

   If it is intermittent, say so and use the rate table in
   `references/reproduction.md` before theorising.
3. Match the signature against `references/bug-classes.md` and run the first
   probe for the one or two classes that fit. State each prediction before you
   test it.
4. Prove causation both ways — make it fail on demand, make it stop. Where
   subagents are available, hand each competing hypothesis to a separate
   `investigator` run rather than testing your favourite first.
5. Report in the skill's format: cause, trigger, evidence, blast radius, fix,
   guard. If causation is not proved, report a leading hypothesis and the next
   probe — do not upgrade a hunch to a cause.
