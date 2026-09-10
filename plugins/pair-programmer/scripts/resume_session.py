#!/usr/bin/env python3
"""SessionStart hook: pick the pairing session back up where it stopped.

Silent unless there is an open session in this directory. A hook that speaks on
every session start in every repository is ignored within a day, and an ignored
hook is worse than none.

The rule for what counts as needing attention is not defined here — it is
imported from the pair-session skill's `session.py`, which owns it, so the hook
cannot drift from what `/pair` and the MCP server say.

Never blocks: the exit status is always 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "skills" / "pair-session" / "scripts"
)
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

try:
    import session  # type: ignore
except ImportError:  # installed without the bundle; stay silent
    session = None

MAX_QUESTIONS = 3


def main() -> int:
    if session is None:
        return 0
    try:
        json.load(sys.stdin)  # drain the event; its contents are not needed
    except Exception:
        pass

    path = Path(session.DEFAULT_PATH)
    if not path.is_file():
        return 0
    try:
        state = session.read(path)
    except session.SessionError as exc:
        print("pair: %s" % exc)
        return 0
    if state.get("status") != "open":
        return 0

    report = session.status_report(state)
    lines = ["goal: %s" % (report["goal"] or "(none stated)")]
    if report["turn"]:
        lines.append("turn: %s" % report["turn"])
    lines.append("next: %s" % (report["next_step"] or "(not recorded)"))
    for question in report["open_questions"][:MAX_QUESTIONS]:
        lines.append("open: [%d] %s" % (question["n"], question["text"]))
    extra = len(report["open_questions"]) - MAX_QUESTIONS
    if extra > 0:
        lines.append("open: and %d more" % extra)
    for line in report["suspect"]:
        lines.append("STALE: %s" % line)

    print("pair: session open — " + lines[0])
    for line in lines[1:]:
        print("      " + line)
    if report["suspect"]:
        print("      This journal may not describe the work in front of you.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
