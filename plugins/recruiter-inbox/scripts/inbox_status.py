#!/usr/bin/env python3
"""SessionStart hook: say which recruiter threads are waiting on the user, if any.

Silent unless there is a reply ledger in this directory and something in it
needs the user: a reply owed, a draft waiting for approval, an approved reply
not yet sent, or a follow-up that has come due. A hook that speaks at every
session start gets ignored within a day, and an ignored hook is worse than none.

The buckets are not defined here -- `status_report` is imported from the
reply-ledger skill, which owns that rule.

Never blocks: the exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "reply-ledger" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    import threads  # type: ignore
except ImportError:  # installed without the bundle; stay silent
    threads = None

ORDER = (
    ("approved_unsent", "approved but not sent"),
    ("owe_reply", "waiting for your reply"),
    ("awaiting_approval", "drafted, waiting for your approval"),
    ("follow_up_due", "due a follow-up"),
)


def main() -> int:
    if threads is None:
        return 0
    cwd = os.getcwd()
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict) and event.get("cwd"):
            cwd = str(event["cwd"])
    except Exception:
        pass

    path = Path(cwd) / threads.DEFAULT_PATH
    if not path.is_file():
        return 0
    try:
        report = threads.status_report(threads.read(path), dt.date.today())
    except Exception as exc:
        print("recruiter-inbox: %s is unreadable (%s)" % (threads.DEFAULT_PATH, exc))
        return 0

    counts = ["%d %s" % (len(report[key]), label) for key, label in ORDER if report[key]]
    if not counts:
        return 0  # only "quiet" threads, or nothing at all: not worth a line at startup
    print("recruiter-inbox: %s." % "; ".join(counts))
    for key, _ in ORDER:
        for row in report[key][:2]:
            company = " (%s)" % row["company"] if row["company"] else ""
            print("  %s%s -- %s" % (row["contact"] or row["thread"], company, row["why"]))
    print("  Run /inbox to deal with them, or /threads for the full list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
