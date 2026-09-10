---
description: Write the pairing handoff — goal, next step, decisions and their reasons, what was rejected, what is still open.
argument_hint: "[optional: anything to add before closing]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Write the handoff. Anything to add first: {{ARGS}}

Follow the `pair-session` skill.

1. Check what the session is missing before rendering anything:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" status
   ```

   Exit 1 lists what is missing — usually no next step, or questions still open.
   Fix the next step with the user now; it is the single most useful line in the
   document and the one that cannot be reconstructed cold.

2. Record anything from {{ARGS}} or from the last stretch of work that has not
   been written down yet — decisions with their reasons, alternatives that were
   rejected, and anything expensive that was learned. Ask for the reason if you
   do not have it. Do not supply a plausible one.

3. Render it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" handoff
   ```

4. Read the result back in three lines: where the work stands, what the next
   step is, and what is still open. Name the open questions rather than
   summarising them away — they are the part the next session needs most.

5. Close the session only if the work is actually stopping:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" close
   ```

   A handoff mid-session is normal and does not need a close.
