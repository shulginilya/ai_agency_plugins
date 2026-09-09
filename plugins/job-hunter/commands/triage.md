---
description: Score a job ad, gig or RFP against the profile and return pursue, skip or unclear with the reason.
argument_hint: "[a posting file, a URL, or paste the text]"
model: sonnet
allowed_tools: Bash Read Grep Glob WebFetch
---

Triage this opportunity: {{ARGS}}

If that is empty, ask for the posting text or a file — do not triage from a job
title alone.

Follow the `opportunity-triage` skill.

1. Get the posting in full. Save pasted text to a file so the script can read it.
2. Score what is countable:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/opportunity-triage/scripts/fit.py" <posting file>
   ```

   If it exits 2 because no profile exists, run `fit.py --init`, then work
   through the template with the user before scoring anything. Do not invent
   their must-haves.
3. Read the posting yourself for the signals the script cannot see —
   `references/posting-signals.md`.
4. Report in the skill's format: verdict, fit, against, unknown, effort, next.
   Skip and unclear are real answers; do not talk yourself into pursue.
5. If the verdict is pursue and the user agrees, record it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/application-pipeline/scripts/pipeline.py" add \
     --company <name> --role <role> --track <contract|permanent> --link <url> \
     --next "<the actual next step>" --due <YYYY-MM-DD>
   ```
