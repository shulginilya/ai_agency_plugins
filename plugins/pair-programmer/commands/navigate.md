---
description: Take a navigator pass over the work in progress — goal, drift, silent decisions, unchecked assumptions.
argument_hint: "[optional: what you want a second opinion on]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Navigator pass{{ARGS}}

Follow the `pair-navigating` skill. You are not writing code in this pass.

1. Read the session — the goal is the thing every observation is measured
   against:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" status
   ```

2. Run the drift check:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-navigating/scripts/drift.py"
   ```

   Exit 3 is not a pass — it means there is no declared scope, or the branch
   moved, and nothing can be checked. Say which, and offer to declare a scope.

3. Read the change itself for the three things the script cannot see:
   the work solving a different problem than the goal states; an assumption
   nobody has checked; a decision made silently — a default, a dropped edge
   case — that will have to be reconstructed later.

4. Report only those. Not naming, not style, not a neater way to write the same
   thing — those belong to review. If nothing meets the bar, say the change is
   on track and stop; a navigator who always finds something stops being read.

5. Put what the pass produced into the journal, in the driver's words rather
   than yours:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" decide "<what>" --because "<why>"
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" ask "<what nobody could answer>"
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" next "<the next concrete step>"
   ```

If the change has grown large enough that you are reading it in pieces, hand it
to the `navigator` agent instead so it gets read in one clean context.
