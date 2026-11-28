# /review

Review UI for usability, accessibility (WCAG 2.2 AA) and design-system consistency, and report findings ranked by severity.

Review the UI: $ARGUMENTS

If that is empty, review the UI files changed against the default branch. If
none changed, ask which flow to review.

Follow the `ux-review` skill:

1. Run `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/designer/skills/ux-review/scripts/ui_inventory.py --root .` to find
   the stack, tokens, components and pages. Then state the scope: which flows or
   screens, for which user.
2. Look at the interface running where possible: desktop and about 375px,
   light and dark, keyboard only, and every state you can force. If it can't
   run, review from the code and say so.
3. Check usability and accessibility with the skill's references. Run
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/designer/skills/ux-review/scripts/contrast.py` on every text and background
   pairing that is in doubt, in both themes.
4. For a whole flow, also hand it to the `first-time-user` subagent.
5. Report findings in the skill's format, blockers first, each with where, who,
   what they see, the fix and the WCAG reference. End with what you could not
   cover.
