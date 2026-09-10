---
description: Start or resume a pairing session — set the goal, the scope and the test command, and agree who is driving.
argument_hint: "[what you want to be true at the end]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Start or resume pairing on: {{ARGS}}

Follow the `pair-session` skill.

1. Check for a session already open:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" status
   ```

   Exit 0 or 1 means one is open — report the goal, the next step and any open
   questions, and ask whether to resume it or close it and start a new one.
   Exit 3 means the branch or the base commit moved: say so plainly and do not
   resume a journal that describes different work.

2. If there is nothing open, settle the goal before starting. If {{ARGS}} names
   a place rather than an outcome ("look at the webhook code"), ask what would
   be true at the end that is not true now, and use the answer. Do not invent
   one.

3. Agree the rest in one exchange — do not guess any of it:
   - **scope**: which paths the change is allowed to touch;
   - **test command**: how the suite is run, scoped to the work;
   - **mode**: `navigate` (they drive, you navigate) or `pingpong` (turns
     alternate, the suite gates the handover);
   - **who drives first**.

4. Open it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/pair-session/scripts/session.py" start \
     --goal "<the outcome>" --scope <path> [--scope <path>] \
     --test-command "<command>" --mode <navigate|pingpong>
   ```

   Ping-pong without a test command is refused — the turn gate has nothing to
   check. Get the command rather than switching them to navigate mode.

5. Say back the goal, the scope, whose turn it is, and the first step. Then
   follow `pair-navigating` or `tdd-ping-pong` for the mode that was chosen.
