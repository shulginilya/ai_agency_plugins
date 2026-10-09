#!/usr/bin/env python3
"""Stop hook: do not let a plugin build end before its gate has run on the final files.

"Don't call it done until the checks pass" is the one rule the plugin-developer
skills cannot enforce with prose: an agent that has just written twenty files
is exactly the agent that will report success without re-running anything.

Silent unless a build session is open (.plugin-dev/active.json, written by
scaffold.py and removed by `gate.py close`). When one is open it blocks the
stop -- once -- if the gate for that plugin was never run, failed, or ran
before the latest edit. A passing or honestly incomplete run (nothing failed,
the claude CLI was not available) lets the session end.

It blocks at most once per stop attempt: when Claude Code reports that a stop
hook is already active, it lets the stop through, so a build that cannot be
fixed ends with a report instead of a loop.

The freshness rule is not defined here; it is gate.freshness, so the hook and
`gate.py status` cannot disagree. Always exits 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "skills" / "plugin-verification" / "scripts"
ANALYSIS = PLUGIN_ROOT / "skills" / "requirements-analysis" / "scripts"
for directory in (SCRIPTS, ANALYSIS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

try:
    import gate  # type: ignore
except ImportError:  # installed without the verification skill; stay out of the way
    gate = None


def main() -> int:
    if gate is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    if not isinstance(event, dict):
        event = {}
    if event.get("stop_hook_active"):
        return 0

    root = gate.find_root(Path(event.get("cwd") or os.getcwd()))
    if root is None:
        return 0
    session = gate.active(root)
    if not session:
        return 0
    name = str(session["plugin"])
    try:
        state, reason = gate.freshness(root, name)
    except Exception:
        return 0
    if state in ("pass", "incomplete"):
        return 0

    script = "skills/plugin-verification/scripts/gate.py"
    print(json.dumps({
        "decision": "block",
        "reason": (
            "plugin-developer: the build of plugins/%s is not verified -- %s. "
            "Run `python \"%s/%s\" run %s` and fix what it reports. "
            "If it still fails after three fix loops, stop fixing: report the failing step "
            "and its output, then run `gate.py close %s --abandon`."
        ) % (name, reason, PLUGIN_ROOT.as_posix(), script, name, name),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
