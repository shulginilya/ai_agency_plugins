#!/usr/bin/env python3
"""SessionStart hook: say what the interview prep needs today, if anything.

Silent unless there is an interview state file in this directory and something
in it needs action. A hook that prints in every session in every repository gets
ignored within a day, and an ignored hook is worse than none.

The buckets are not defined here -- `status_report` is imported from the
prep-tracker skill, which owns that rule.

Never blocks: the exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "skills" / "prep-tracker" / "scripts"
)
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    from prep import DEFAULT_PATH, read, status_report  # type: ignore
except ImportError:  # installed without the bundle; stay silent
    read = None


def main() -> int:
    if read is None:
        return 0
    try:
        json.load(sys.stdin)  # drain the event; its contents are not needed
    except Exception:
        pass

    path = Path(DEFAULT_PATH)
    if not path.is_file():
        return 0
    try:
        report = status_report(read(path), dt.date.today())
    except (OSError, ValueError) as exc:
        print("interview-prep: %s is unreadable (%s)" % (path, exc))
        return 0

    if report["verdict"] == "clear":
        return 0

    for loop in report["loops"]:
        lines = []
        for entry in loop["unprepped_rounds"]:
            lines.append("%s is scheduled with nothing prepared and no mock" % entry)
        for entry in loop["passed_rounds"]:
            lines.append(entry)
        for entry in loop["imminent_rounds"]:
            lines.append(entry)
        for entry in loop["overdue_prep"]:
            lines.append("overdue: %s" % entry)
        if not lines:
            continue
        print("interview-prep: %s -- %s" % (loop["company"], loop["role"]))
        for line in lines[:3]:
            print("  %s" % line)
        if len(lines) > 3:
            print("  ...and %d more" % (len(lines) - 3))
    print("  Run /readiness for the full picture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
