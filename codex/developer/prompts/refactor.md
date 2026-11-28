# /refactor

Restructure existing code without changing behaviour — pin it with tests, find every caller, then apply small mechanical moves that stay green.

Refactor: $ARGUMENTS

If that is empty, refactor whatever the conversation was last working on, and
say which target you picked before starting.

Follow the `safe-refactoring` skill:

1. **Name the reason.** What this makes possible or cheaper. If there is no
   reason beyond taste, say so and stop rather than producing churn.
2. **Pin the behaviour.** Run the existing tests; where there are none, write
   characterization tests that assert today's behaviour — including anything
   that looks wrong. Do not fix it in this change.
3. **Size the blast radius** with
   `python /home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/developer/skills/safe-refactoring/scripts/callers.py <symbol>`, then account
   for what search cannot see: dynamic dispatch, config, serialized data,
   external consumers.
4. **One move at a time**, from `references/refactoring-moves.md`, tests green
   between each. On red: revert and take a smaller step — never debug forward.
5. Report in the skill's format, and state explicitly if *any* observable
   behaviour changed.
