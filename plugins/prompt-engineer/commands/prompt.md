---
description: Turn some text — a task, rough notes, an example — into a tailored prompt ready to paste or ship.
argument_hint: "[what the prompt should do, or a file with notes]"
model: sonnet
allowed_tools: Bash Read Grep Glob Write
---

Build a prompt from: {{ARGS}}

If that is empty, ask what the prompt should make a model do, and for any
material it will run on — nothing else yet. If it names a file, read it.

Follow the `prompt-crafting` skill.

1. Scan the text:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prompt-crafting/scripts/brief.py" --text "<the text>"
   ```

   Settle the job, the target, the consumer and the bar.
2. Ask the scan's `Ask` questions — at most three, in one message — unless the
   user said to just write it. Everything else is an assumption you state.
3. Take the pattern for the task type from `references/prompt-patterns.md`
   and tailor it with `references/target-tailoring.md`.
4. Lint the draft and fix every error:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prompt-crafting/scripts/prompt_lint.py" --text "<the prompt>"
   ```

5. Deliver the prompt in one fenced block, followed by the skill's short
   `Target / Variables / Assumed / Lint / Test it with` lines. Offer `/prompt-test`
   if the prompt is going into a pipeline or a system prompt.
