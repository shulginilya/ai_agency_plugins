#!/usr/bin/env python3
"""List open GitHub issues with a readiness verdict for each.

Wraps `gh issue list --json ...` and runs every issue through ready.py, so a
refinement session starts from "these four are not ready and here is why"
rather than from a wall of titles.

    python backlog.py                          # every open issue
    python backlog.py --not-ready              # only the ones blocking planning
    python backlog.py --milestone "Sprint 12"
    python backlog.py --label ready --limit 50 --json

Exit codes: 0 fine (including an empty backlog), 2 gh is missing,
unauthenticated, or not pointed at a repository.

`--from-json FILE` reads a payload captured earlier with
`gh issue list --json number,title,body,labels,milestone,assignees`, which is
also how this script is tested without a network.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ready  # noqa: E402  (path is set immediately above)

GH_FIELDS = "number,title,body,labels,milestone,assignees,url"
GH_TIMEOUT = 30


class BacklogError(Exception):
    """gh could not answer; the message is meant for a human."""


def fetch(
    milestone: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 100,
    cwd: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if shutil.which("gh") is None:
        raise BacklogError(
            "the GitHub CLI (gh) is not installed. Install it, or paste "
            "`gh issue list --json %s` output and use --from-json." % GH_FIELDS
        )
    command = ["gh", "issue", "list", "--state", "open", "--limit", str(limit),
               "--json", GH_FIELDS]
    if milestone:
        command += ["--milestone", milestone]
    if label:
        command += ["--label", label]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, cwd=cwd, check=False,
            timeout=GH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise BacklogError("gh timed out after %d seconds" % GH_TIMEOUT)
    if result.returncode != 0:
        raise BacklogError(result.stderr.strip() or "gh issue list failed")
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise BacklogError("gh returned output that is not JSON (%s)" % exc)
    if not isinstance(payload, list):
        raise BacklogError("gh returned %s, expected a list of issues" % type(payload).__name__)
    return payload


def _label_names(issue: Dict[str, Any]) -> List[str]:
    names = []
    for label in issue.get("labels") or []:
        if isinstance(label, dict):
            name = label.get("name")
        else:
            name = label
        if name:
            names.append(str(name))
    return names


def assess(issues: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    assessed = []
    for issue in issues:
        labels = _label_names(issue)
        report = ready.evaluate(
            issue.get("body") or "",
            title=str(issue.get("title") or ""),
            labels=labels,
        )
        milestone = issue.get("milestone") or {}
        assessed.append(
            {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "url": issue.get("url"),
                "labels": labels,
                "milestone": milestone.get("title") if isinstance(milestone, dict) else milestone,
                "assignees": [
                    a.get("login") if isinstance(a, dict) else a
                    for a in (issue.get("assignees") or [])
                ],
                "ready": report["ready"],
                "gaps": report["gaps"],
                "warnings": report["warnings"],
            }
        )
    return assessed


def format_table(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "No open issues."
    lines: List[str] = []
    ready_count = sum(1 for row in rows if row["ready"])
    lines.append("%d open, %d ready, %d not ready" % (len(rows), ready_count, len(rows) - ready_count))
    lines.append("")
    for row in rows:
        mark = "ready    " if row["ready"] else "NOT READY"
        milestone = " [%s]" % row["milestone"] if row["milestone"] else ""
        lines.append("%s #%-5s %s%s" % (mark, row["number"], row["title"], milestone))
        for gap in row["gaps"]:
            lines.append("            gap  %s" % gap["message"])
        for warning in row["warnings"]:
            lines.append("            warn %s" % warning["message"])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--milestone", help="restrict to one milestone")
    parser.add_argument("--label", help="restrict to one label")
    parser.add_argument("--limit", type=int, default=100, help="max issues to fetch (default 100)")
    parser.add_argument("--cwd", help="repository directory (default: here)")
    parser.add_argument("--not-ready", action="store_true", dest="not_ready",
                        help="show only issues that fail the Definition of Ready")
    parser.add_argument("--from-json", dest="from_json",
                        help="read a saved `gh issue list --json ...` payload instead of calling gh")
    parser.add_argument("--json", action="store_true", help="emit the assessment as JSON")
    args = parser.parse_args(argv)

    try:
        if args.from_json:
            with open(args.from_json, "r", encoding="utf-8") as handle:
                issues = json.load(handle)
            if not isinstance(issues, list):
                raise BacklogError("%s does not contain a list of issues" % args.from_json)
        else:
            issues = fetch(args.milestone, args.label, args.limit, args.cwd)
    except BacklogError as exc:
        sys.stderr.write("backlog: %s\n" % exc)
        return 2
    except OSError as exc:
        sys.stderr.write("backlog: %s\n" % exc)
        return 2
    except json.JSONDecodeError as exc:
        sys.stderr.write("backlog: %s is not valid JSON (%s)\n" % (args.from_json, exc))
        return 2

    rows = assess(issues)
    if args.not_ready:
        rows = [row for row in rows if not row["ready"]]
        if not rows:
            print("Every open issue meets the Definition of Ready.")
            return 0

    print(json.dumps(rows, indent=2) if args.json else format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
