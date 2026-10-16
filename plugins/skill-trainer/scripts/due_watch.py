#!/usr/bin/env python3
"""SessionStart hook: one line about today's training, at most once a day.

The training state is global (it lives in the user's home, not in a repository),
so a hook that spoke in every session would be ignored within a day. This one
speaks only when there is a state file, today's session is not logged yet, and
it has not already spoken today. The rules for what is due come from the
training-plan skill's trainer.py, which owns them.

Never blocks: the exit status is always 0.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "training-plan" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    import trainer  # type: ignore
except ImportError:  # installed without the bundle; stay silent
    trainer = None


def message(state, day: dt.date):
    report = trainer.status_report(state, day)
    if report["done_today"]:
        return None
    settings = state["settings"]
    parts = []
    if settings["cadence"] == "daily":
        parts.append("today's %d-minute session is not done" % settings["daily_minutes"])
    else:
        left = report["sessions_left_this_week"]
        days_left = 7 - day.weekday()
        if left == 0 or days_left > left * 2:
            return None  # the week still has room; do not nag
        parts.append("%d weekly session%s left and %d day%s to do them"
                     % (left, "" if left == 1 else "s", days_left, "" if days_left == 1 else "s"))
    if report["due"]:
        parts.append("%d review%s due (%s)" % (len(report["due"]), "" if len(report["due"]) == 1 else "s",
                                              ", ".join(d["id"] for d in report["due"][:3])))
    if 0 <= report.get("interview_days_left", -1) <= 14:
        parts.append("interview in %d days" % report["interview_days_left"])
    return "skill-trainer: %s. /skill-trainer:today" % "; ".join(parts)


def main() -> int:
    if trainer is None:
        return 0
    try:
        json.load(sys.stdin)  # drain the event; its contents are not needed
    except Exception:
        pass
    try:
        home, _ = trainer.resolve_home(None)
        if not trainer.state_path(home).is_file():
            return 0
        day = dt.date.today()
        stamp = home / ".nudged"
        if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == day.isoformat():
            return 0
        text = message(trainer.read_state(home), day)
        if text:
            print(text)
            stamp.write_text(day.isoformat(), encoding="utf-8")
    except Exception as exc:  # a hook must never break a session
        print("skill-trainer: training state is unreadable (%s)" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
