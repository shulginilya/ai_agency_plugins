# /log

Log a practice session you did on your own, so the plan schedules the topic again at the right time.

Log: $ARGUMENTS

1. Work out the topic id. If it is not an exact id, run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" topics` and pick the
   closest one; say which. If nothing fits, offer
   `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" add-topic --area <area> --title "<title>"` first.
2. Work out the score from what the user says, with the `training-plan` skill's
   score table. If they gave no score and the account is vague, ask one
   question rather than guess. Give the lower score when it is between two.
3. Run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/skill-trainer/skills/training-plan/scripts/trainer.py" log --topic <id> --score <n> [--minutes <m>] [--notes "<text>"] [--kind mock] [--date YYYY-MM-DD]`.
   A date must be ISO; ask for it rather than interpret "yesterday".
4. Reply in one line: what was logged and when the topic comes back.
