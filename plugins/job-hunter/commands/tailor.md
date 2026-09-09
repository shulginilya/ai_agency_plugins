---
description: Write a proposal, cover letter or CV variant for one specific posting from the profile and the user's own template.
argument_hint: "[the company or posting, and which document]"
model: sonnet
allowed_tools: Bash Read Write Edit Grep Glob
---

Write the application for: {{ARGS}}

Follow the `application-tailoring` skill.

1. Confirm the posting has been triaged. If not, run `/triage` first — writing
   for a posting nobody scored is how a bad fit gets a good proposal.
2. Gather what the draft needs: the full posting, `.jobhunt/profile.json`, the
   user's own template if they have one, and concrete evidence — projects,
   systems, numbers. **Ask for evidence you do not have. Never invent it, and
   never leave a placeholder in a draft.**
3. Identify the channel (platform bid, cover letter, cold email, CV variant)
   and load `references/channels.md` for that one.
4. Draft: hook, evidence tied to their stated requirements, the gap in one
   honest clause, one clear ask.
5. Hand it over with the mapping — which requirement each piece of evidence
   answers, which requirement you could not match, and what you had to ask
   about. Then offer to record the send:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/application-pipeline/scripts/pipeline.py" \
     move <company> --to applied --next "<follow-up>" --due <YYYY-MM-DD>
   ```

Do not send anything. Drafts go to the user; the user sends them.
