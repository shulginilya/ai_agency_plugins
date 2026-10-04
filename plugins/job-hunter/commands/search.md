---
description: Search one platform — Upwork, Arc, Contra or all of them — for postings that fit the profile, and list the best without applying to anything.
argument_hint: "<upwork|arc|contra|all> [a query in quotes] [--limit N]"
model: sonnet
---

Search: {{ARGS}}

If no platform is named, use the profile's `search.platforms` and say so. If a
platform is named that the skill has no reference for, say which ones it knows
and stop.

Follow the `platform-search` skill. For `all`, run steps 1–5 for each platform
in the profile, then give one combined list.

1. Plan:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/platform-search/scripts/search_log.py" plan <platform> [--query "<query>"]
   ```

   Exit 2 means no profile: stop and set one up with the user. A `--limit` in
   the arguments overrides the plan's limit for this run only.
2. Load `references/<platform>.md` and search the way it says. Check
   for a blocker first (on Upwork: the Connects balance). Never sign in for the
   user, and never ask for a password.
3. Write the candidates to a JSON file and filter:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/platform-search/scripts/search_log.py" filter <platform> <candidates.json> > <filtered.json>
   ```

4. Open the top survivors in full, then screen each one — the `screener` agent
   per posting where available, otherwise the `opportunity-triage` skill. Put
   `verdict` and `note` on each posting in the filtered file.
5. Record and report:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/platform-search/scripts/search_log.py" record <platform> <filtered.json>
   ```

   Then show the list in the skill's format, blocker first.

Do not apply, draft, message or save jobs on the platform. If the user wants a
proposal for one of the results, that is `/tailor`.
