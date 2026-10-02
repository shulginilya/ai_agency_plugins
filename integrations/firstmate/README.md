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
- `--with-plugins` installs `developer`, `debugger`, `code-review` and `scrum-master`
  into `~/.claude` at user scope. Claude crewmates use the normal `~/.claude`, so that
  is what makes the plugins available to them.
- Files are copied, never symlinked: firstmate refuses a `brief-include.md` that is
  not a readable regular file.
- A deployed file you edited by hand is backed up to `<name>.bak` before it is replaced.
- `crew-dispatch.json` is deployed too once it exists here (checked with `jq` if installed).
- New briefs pick up the change on the next dispatch; running crewmates keep their brief.

## Rules for editing `brief-include.md`

- Never include a `Delivery contract: mode=` line; firstmate refuses the brief.
- It is not inherited by secondmate homes; deploy it into each home that needs it.
- Keep it to the routing table and the unattended-crewmate rules. Task-specific
  instructions belong in the brief firstmate writes, not here.
