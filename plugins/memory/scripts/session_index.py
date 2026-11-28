#!/usr/bin/env python3
"""SessionStart hook: list this project's memories (ids and titles only).

Never blocks: whatever goes wrong, it says memory is unavailable and exits 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "memory-keeping" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    import memory  # type: ignore
except Exception:  # installed without the bundle, or a broken install
    memory = None


def directory(event: Any, env: Mapping[str, str] = os.environ) -> Path:
    """The project directory, resolved as the MCP server resolves it, so both see one project."""
    cwd = event.get("cwd") if isinstance(event, dict) else None
    chosen = env.get("CLAUDE_PROJECT_DIR") or (cwd if isinstance(cwd, str) else None)
    return Path(chosen) if chosen else Path.cwd()


def message(project_dir: Path, env: Mapping[str, str] = os.environ) -> str:
    try:
        if memory is None:
            raise RuntimeError("its scripts are missing")
        return memory.open_memory(project_dir, env).index()
    except Exception as exc:  # a hook must never break a session
        known = memory is not None and isinstance(exc, memory.store_module.Unavailable)
        reason = str(exc) if known else "unexpected %s" % type(exc).__name__
        return "memory: memory is unavailable (%s). The session is otherwise unaffected." % reason


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    try:
        print(message(directory(event)))
    except Exception:
        print("memory: memory is unavailable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
