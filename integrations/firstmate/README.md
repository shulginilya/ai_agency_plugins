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
- `--with-plugins` installs every plugin under `plugins/` (each `plugins/<name>/plugin.json`,
  skipping `_`-prefixed dirs such as `_template`) into `~/.claude` at user scope, after
  rebuilding their `claude-code` bundles. The list is found at run time, so a new plugin needs
  no script change: just rerun it after adding or changing a plugin.
  - Crew plugins: `developer`, `debugger`, `code-review` and `scrum-master`, listed in
    `crew_plugins` in `deploy.sh`. Claude crewmates use the normal `~/.claude`, and
    `brief-include.md` routes their work to these.
  - Every other plugin is a Captain plugin, for your own sessions. Crewmates share `~/.claude`,
    so they can see these too, and `brief-include.md` tells crewmates not to use them.
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
