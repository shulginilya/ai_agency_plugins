# firstmate integration

Files that make [firstmate](https://github.com/kunchenguid/firstmate) crewmates work
with the plugins in this repo. They are deployed into firstmate's `config/` folder,
which firstmate gitignores and `/updatefirstmate` never touches, so firstmate itself
stays an unmodified upstream clone.

| File | Lands at | What it does |
| --- | --- | --- |
| `brief-include.md` | `~/firstmate/config/brief-include.md` | Appended to every ship and scout brief: which plugin command a crewmate uses for which kind of task, and how it behaves with nobody watching. |

## Deploy

From the repo root, inside WSL/Linux:

```bash
integrations/firstmate/deploy.sh --with-plugins   # first time: plugins + config
integrations/firstmate/deploy.sh                  # after editing a file here
```

- The firstmate home defaults to `$FM_HOME`, then `~/firstmate`; pass a path to override.
- `--with-plugins` installs only the crew plugins, `developer`, `scrum-master`, `designer`, `qa` and `devops` (the `crew_plugins` list in `deploy.sh`), into `~/.claude` at
  user scope.
  It rebuilds their `claude-code` bundles first, so rerun it after a crew plugin changes.
  - Claude crewmates run from that same `~/.claude`, so nothing else is installed there: every
    plugin there loads its hooks into every crew session. A new plugin stays out until it is
    added to `crew_plugins` and routed in `brief-include.md`. Install Captain plugins for your
    own sessions some other way (your synced plugins already cover them).
  - **It refuses while any crewmate is live**, meaning any `state/<id>.meta` exists in the
    firstmate home. The install deletes and recopies each plugin folder under running
    crewmates, which breaks them. Let the crew finish or tear it down, then rerun. A refused
    run changes nothing. The check covers this home only: if a secondmate home on this
    machine runs Claude crewmates, check it too.
- Files are copied, never symlinked: firstmate refuses a `brief-include.md` that is
  not a readable regular file.
- A deployed file you edited by hand is backed up to `<name>.bak` before it is replaced.
- If the firstmate clone does not gitignore `config/`, the script hides the deployed
  files from `git status` without editing any tracked file: untracked ones go into the
  clone-local `.git/info/exclude`, tracked ones get `git update-index --skip-worktree`.
- `crew-dispatch.json` is deployed too once it exists here (checked with `jq` if installed).
- New briefs pick up the change on the next dispatch; running crewmates keep their brief.

## Rules for editing `brief-include.md`

- Never include a `Delivery contract: mode=` line; firstmate refuses the brief.
- It is not inherited by secondmate homes; deploy it into each home that needs it.
- Keep it to the routing table, the captain-plugin exclusion and the unattended-crewmate rules.
  Task-specific instructions belong in the brief firstmate writes, not here.
- To add a plugin to the crew, add it to `crew_plugins` in `deploy.sh` and give it routing
  lines and a place in the crew-plugin sentence here.
