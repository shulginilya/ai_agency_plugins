---
description: Diagnose an existing prompt that underperforms and rewrite only what its defects need.
argument_hint: "[the prompt, or a path to it]"
model: sonnet
allowed_tools: Bash Read Grep Glob Edit Write
---

Review and improve this prompt: {{ARGS}}

If that is empty, ask for the prompt and for one or two outputs it produced
that were wrong. If it names a file, read it; if the user wants it fixed in
place, edit that file.

Follow the `prompt-crafting` skill, section "Improving an existing prompt".

1. Lint it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prompt-crafting/scripts/prompt_lint.py" "<file>"
   ```

2. Ask for a bad output if none was given — it points at the missing sentence
   faster than reading does. Do not block on it if the user has none.
3. List each defect with the output it causes, most damaging first.
4. Rewrite with the smallest change that fixes them. Keep the structure,
   variables and wording that work.
5. Deliver the improved prompt in one fenced block, then `Changed:` — one line
   per defect and what it fixes — and the skill's `Lint` and `Test it with` lines.
