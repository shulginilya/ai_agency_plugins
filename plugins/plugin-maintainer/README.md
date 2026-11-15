# plugin-maintainer

Keeps the installed plugins honest against this repo.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `plugin-freshness` | Compares every installed plugin with the source: version, and file-for-file against a fresh build |
| Command | `/plugin-maintainer:check` | Runs the check and reports it as a table |

## Example

```text
Source: main @ b52090f; main is in sync with origin/main.

| Plugin | Installed | Source | Files | Status |
| --- | --- | --- | --- | --- |
| code-reviewer | 0.4.0 | 0.4.0 | identical | up to date |
| crew | 0.5.0 | 0.5.0 | identical | up to date |

All 2 up to date.

Notes:
- developer@synced 0.1.1 is older than the source (0.7.1).
```

The check is read-only: it builds into a temporary directory and never
installs, pulls or commits. Run it from the plugins repo.
