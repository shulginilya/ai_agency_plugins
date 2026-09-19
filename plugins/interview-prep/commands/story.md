---
description: Build, review or check the STAR story bank behavioral and leadership rounds are won from.
argument_hint: "[a competency, a raw experience, or 'check']"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Work on the story bank: {{ARGS}}

Follow the `story-bank` skill.

1. See where the bank stands:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/story-bank/scripts/stories.py" check
   ```

   Exit 2 means there is no bank — run `stories.py init` first. Exit 1 is a
   competency with no story; exit 3 is a story that would not survive a
   follow-up. Report both, and say which is more urgent given the next round.
2. If the user gave a raw experience, interview them for it before writing
   anything: what was at stake, what *they* did, what happened, how they know.
   One situation at a time.
3. Write it in their words, first person, two minutes spoken, with an outcome
   that can be checked. Never invent a fact or a number.
4. Store it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/story-bank/scripts/stories.py" add \
     --title "<short title>" --competencies <a,b> \
     --situation "..." --task "..." --action "..." --result "..." --metric "..."
   ```
5. Rehearse it against the follow-up ladder in `references/star-format.md` —
   ask the five questions and see where it breaks.
6. `stories.py render` when the user wants the readable version.
