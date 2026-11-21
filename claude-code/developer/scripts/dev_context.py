#!/usr/bin/env python3
"""SessionStart hook: state the working context once, so it is not guessed at.

Prints the branch, how far it has diverged from its upstream, how much is
uncommitted, and the checks this repository declares — the three things a
session otherwise discovers by trial and error.

It never blocks and never fails: exit status is always 0, and anything it
cannot determine is simply left out. Outside a git repository it prints
nothing at all.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
# One home for a rule: the check discovery lives in the skill, and is imported
# here rather than restated.
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "feature-implementation" / "scripts"))

try:
    from verify import discover  # type: ignore
except Exception:  # the hook is advisory; never let an import break a session
    discover = None

MAX_CHECKS = 4


def git(args, cwd):
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = (event or {}).get("cwd") or None

    root = git(["rev-parse", "--show-toplevel"], cwd)
    if not root:
        return 0

    lines = []
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "detached"
    state = branch

    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
    if upstream:
        counts = git(["rev-list", "--left-right", "--count", "%s...HEAD" % upstream], cwd)
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                behind, ahead = parts
                if ahead != "0" or behind != "0":
                    state += "  (%s ahead, %s behind %s)" % (ahead, behind, upstream)
    else:
        state += "  (no upstream)"

    porcelain = git(["status", "--porcelain"], cwd)
    if porcelain:
        dirty = len([line for line in porcelain.splitlines() if line.strip()])
        state += "  — %d uncommitted file(s)" % dirty

    lines.append("branch: %s" % state)

    if discover is not None:
        try:
            checks = discover(Path(root))
        except Exception:
            checks = []
        if checks:
            shown = ", ".join(check["command"] for check in checks[:MAX_CHECKS])
            lines.append("checks: %s" % shown)
        else:
            lines.append("checks: none declared — verify by hand and say what you ran")

    if lines:
        print("developer: " + lines[0])
        for line in lines[1:]:
            print("           " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
