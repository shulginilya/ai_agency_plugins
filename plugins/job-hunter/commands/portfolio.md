---
description: Write a portfolio entry for one project from its codebase or live web app — a case study, a CV bullet and a platform blurb, all built from verifiable facts.
argument_hint: "[a repo path, a git URL, or a web app URL]"
model: sonnet
allowed_tools: Bash Read Write Edit Grep Glob WebFetch
---

Write a portfolio entry for: {{ARGS}}

If that is empty, ask for a repo path, a git URL or a live URL — do not write
about a project from its name alone.

Follow the `portfolio-case-study` skill.

1. Identify the input.
   - **Local path**: use it as is.
   - **Git URL**: clone it read-only into a temporary directory with full
     history (`git clone <url> <tmpdir>`). If it is private and the clone fails,
     ask for a local path instead.
   - **Web app URL**: fetch the landing page and one or two inner pages. Save
     the HTML to a temporary file if you can; ask whether a repo exists too.
2. Collect the countable facts:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/portfolio-case-study/scripts/project_facts.py" <dir> --author "<user>"
   python "{{PLUGIN_ROOT}}/skills/portfolio-case-study/scripts/project_facts.py" --page <saved.html>
   ```

   Take the author name or email from `.jobhunt/profile.json` or `git config
   user.name` in the user's own repo, and say which you used. Exit 3 means
   something decisive is missing; the output says what, so ask about it.
3. Read the code (or the pages) for what the script cannot count. For a large
   codebase, delegate the reading to the `project-analyst` agent.
4. Ask the user, in one message, only what you still lack: role and scope,
   the problem, outcomes, constraints, and whether it is confidential.
5. Write `.jobhunt/portfolio/<project-slug>.md` in the format from
   `references/case-study-format.md`. Create the directory if it is missing;
   if the file exists, show the differences and ask before replacing it.
6. Hand over: where each fact came from (code, history, page, user) and what
   you left out for lack of support. Delete any temporary clone.

Do not publish or post the entry anywhere. The user does that.
