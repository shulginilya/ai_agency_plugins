# memory

Facts that survive across sessions. An agent saves one when you ask, and the
next session in the same project starts with the list.

Phase 1 of persistent memory: one machine, one user, explicit saves.

## Setup

Needs Docker, git, and a Python that can create environments (on Debian or
Ubuntu: `sudo apt install python3-venv`).

```
/memory:setup              # --port N to use another port than 27027
/memory:status
```

Setup installs the pinned MongoDB driver into
`~/.local/share/ai-agency/memory/venv`, starts the container
`ai-agency-memory` (`mongo:8.0.38`) on `127.0.0.1` with authentication on, keeps
the data in the volume `ai-agency-memory-data`, and writes the connection string
to `~/.config/ai-agency/memory.json`, readable by you only. It is safe to run
again and never deletes the volume. `AI_AGENCY_MEMORY_URI`, when set, is used
instead of the file, and Docker is then left alone.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `memory-keeping` | When to save, what never to save, how to treat what is recalled |
| MCP | `remember`, `recall`, `get`, `forget` | The four actions, on the session's project only |
| Hook | `SessionStart` | Lists the project's memories, at most 8,000 characters (Claude Code only) |
| Command | `/memory:setup` | Create or repair the database |
| Command | `/memory:status` | Does it answer, and how many memories this project has |

A project is its git `origin` remote (HTTPS and SSH forms are the same
project), or its root directory when it has no remote.

## Limits

- Separating projects keeps memories organised. It is not a security boundary:
  whoever has the connection string reads everything.
- `remember` refuses common shapes of keys, tokens and passwords. It cannot
  recognise every secret.
- `forget` deletes permanently.
- There are no backups yet: the volume is the only copy.
- Sharing between roles, expiry, cleanup and export are later phases.

## Tests

`python -m tools.apkit test` runs the tests that need no database. The database
tests run when `AI_AGENCY_MEMORY_TEST_URI` points at a **throwaway** MongoDB and
`pymongo` is installed; each run uses a new database and drops it. The setup tests
run against your Docker when `AI_AGENCY_MEMORY_TEST_DOCKER` is set, in a container
of their own that they remove.
