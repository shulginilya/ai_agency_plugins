# plugin-maintainer

Keeps the installed plugins honest against this repo.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `plugin-freshness` | Compares every installed plugin with the source: version, and file-for-file against a fresh build |
| Command | `/plugin-maintainer:check` | Runs the check, reports it as a table, then updates the stale plugins, installs new ones and checks again |

## Example

```text
Source: main @ b52090f; main is in sync with origin/main.

| Plugin | Crew | Installed | Source | Files | Status |
| --- | --- | --- | --- | --- | --- |
| code-reviewer | yes: Code Reviewer | 0.4.0 | 0.4.0 | identical | up to date |
| crew | yes: Crew workflow | 0.5.0 | 0.5.0 | identical | up to date |
| notes | no | 0.4.4 | 0.4.4 | identical | up to date |

All 3 up to date.
Crew: 2 (code-reviewer, crew); not crew: 1 (notes).

Notes:
- developer@synced 0.1.1 is older than the source (0.7.1).
```

The Crew column comes from the crew roster, `integrations/crew/team.json`
(the keys of `crew`): `yes: <role>` for a crew member, `no` for any other
plugin, `?` with a note when the roster cannot be read.

`check.py` alone is read-only: it builds into a temporary directory and never
installs, pulls or commits. The command passes `--update`, which then
fast-forwards a default branch that is behind origin, builds and installs each
stale plugin and each plugin in the source that is not installed yet, and prints the report again. It does so only from the default
branch with no uncommitted changes under `plugins/` and nothing ahead of
origin; otherwise it prints `Not updating: <why>` and changes nothing. Run it
from the plugins repo, then `/reload-plugins`.
