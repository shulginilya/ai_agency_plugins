#!/usr/bin/env python3
"""SessionStart hook: say what the job search needs today, if anything.

Silent unless there is a pipeline file in this directory and something in it
needs action. A hook that prints on every session start in every repository
gets ignored within a day, and an ignored hook is worse than none.

The buckets are not defined here — `due_report` is imported from the
application-pipeline skill, which owns that rule.

Never blocks: the exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "skills" / "application-pipeline" / "scripts"
)
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    from pipeline import DEFAULT_PATH, due_report, read  # type: ignore
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
        report = due_report(read(path), dt.date.today())
    except (OSError, ValueError) as exc:
        print("job-hunter: %s is unreadable (%s)" % (path, exc))
        return 0

    if not report["action_needed"]:
        return 0

    counts = []
    for label, key in (("overdue", "overdue"), ("stale", "stale"), ("without a next action", "needs_attention")):
        if report[key]:
            counts.append("%d %s" % (len(report[key]), label))
    print("job-hunter: %s in the pipeline." % ", ".join(counts))
    for row in (report["overdue"] + report["needs_attention"])[:3]:
        print("  %s — %s (%s)" % (row["Company"], row["Next action"] or "no next action", row["Why"]))
    print("  Run /pipeline for the full list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
