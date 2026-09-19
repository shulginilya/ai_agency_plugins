---
description: Turn a job description, Notion page or notes about a role into the interview loop it implies and a dated, risk-ranked prep plan.
argument_hint: "[a description file, a URL, or paste the text]"
model: sonnet
allowed_tools: Bash Read Grep Glob WebFetch
---

Map the loop for this role: {{ARGS}}

If that is empty, ask for the description, a link or the user's notes from the
recruiter call. Do not map a loop from a job title.

Follow the `loop-mapping` skill.

1. Get the text in full. Fetch a URL if you can; otherwise ask for a paste. Save
   it to `.interview/jd/<company>.txt` so every later session reads the same
   text.
2. Scan what is countable:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/loop-mapping/scripts/jd_scan.py" .interview/jd/<company>.txt
   ```

   Exit 1 (thin) or 2 (unusable) means ask for a real description before
   planning. Exit 3 (unclear) means the loop you draft is inferred and the first
   deliverable is the question to the recruiter.
3. Read the description yourself for what the scan cannot see —
   `references/jd-signals.md`.
4. Draft the loop from `references/loop-patterns.md`, tagging every round
   **stated**, **inferred** or **unknown**.
5. Record it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" init
   python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" add \
     --company <name> --role <role> --source .interview/jd/<company>.txt \
     --archetype <type> --rounds <comma-separated>
   ```
6. Rank the gaps by risk and write the top three to five as prep items, each
   with a date the user agreed to:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/prep-tracker/scripts/prep.py" item \
     --company <name> --add "<the specific thing>" --risk high \
     --round <round> --due <YYYY-MM-DD>
   ```
7. Finish with the loop table, the three items, and — if anything is unknown —
   the message to send the recruiter today.
