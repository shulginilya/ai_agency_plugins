---
description: Capture what a real interview round actually asked, while it is still verbatim, and feed it back into the plan.
argument_hint: "[company] [round] — then what happened"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Debrief this round: {{ARGS}}

Follow the `prep-tracker` skill. Do this before anything else in the session —
the questions decay within hours.

1. Get the facts, one question at a time, and write down their words rather than
   a summary:
   - What were you actually asked? Verbatim where you can.
   - Where did you stall, or answer something you were not asked?
   - What did they seem to be probing for?
   - What did they say about the next round or the timeline?
2. Record it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" debrief \
     --company <name> --round <round> \
     --asked "<question>;<question>" --gap "<what went badly>" \
     --outcome advanced|rejected|waiting
   ```

   The script refuses a debrief with no questions recorded. That is the point.
3. Correct the loop: if the round differed from what was mapped, update the
   remaining rounds and say what changed.
4. Turn each gap into a prep item for the next round, with a date — or, if the
   loop is over, into a note for the next company with this archetype.
5. Do not rate their performance from their own account of it. Report what was
   asked and what they said was hard; they were there and you were not.
