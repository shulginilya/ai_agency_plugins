#!/usr/bin/env python3
"""SessionStart hook: put the active sprint in front of the model, once.

Asks gh for the nearest open milestone and its open issues, then prints a few
lines. Everything about it is best effort: no repository, no gh, no
authentication, no milestone, or a slow network all mean it prints nothing.
Exit status is always 0 — a hook that fails a session start is worse than a
hook that says nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime

TIMEOUT = 6
MAX_ISSUES = 8


def _run(args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _json(args):
    raw = _run(args)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _due_in_days(due_on):
    if not due_on:
        return None
    try:
        stamp = datetime.strptime(str(due_on)[:10], "%Y-%m-%d")
    except ValueError:
        return None
    return (stamp.date() - datetime.utcnow().date()).days


def pick_milestone(milestones):
    """The open milestone due soonest; failing that, the first one."""
    if not isinstance(milestones, list) or not milestones:
        return None
    dated = [m for m in milestones if isinstance(m, dict) and m.get("due_on")]
    if dated:
        return sorted(dated, key=lambda m: str(m.get("due_on")))[0]
    first = milestones[0]
    return first if isinstance(first, dict) else None


def main() -> int:
    try:
        sys.stdin.read()
    except Exception:
        pass

    if _run(["git", "rev-parse", "--git-dir"]) is None:
        return 0

    milestones = _json(
        ["gh", "api", "repos/:owner/:repo/milestones?state=open&per_page=20"]
    )
    milestone = pick_milestone(milestones)
    if not milestone:
        return 0

    title = str(milestone.get("title") or "").strip()
    if not title:
        return 0

    issues = _json(
        [
            "gh", "issue", "list", "--state", "open", "--milestone", title,
            "--limit", "100", "--json", "number,title,assignees",
        ]
    )
    if not isinstance(issues, list):
        return 0

    unassigned = sum(1 for i in issues if not (i.get("assignees") or []))
    due = _due_in_days(milestone.get("due_on"))
    if due is None:
        when = ""
    elif due < 0:
        when = ", %d day(s) overdue" % abs(due)
    else:
        when = ", %d day(s) left" % due

    print(
        'scrum-master: active sprint "%s" — %d open, %d unassigned%s.'
        % (title, len(issues), unassigned, when)
    )
    for issue in issues[:MAX_ISSUES]:
        print("  #%s  %s" % (issue.get("number"), issue.get("title")))
    if len(issues) > MAX_ISSUES:
        print("  ... and %d more" % (len(issues) - MAX_ISSUES))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
