#!/usr/bin/env python3
"""Who changed these lines, when, and what else landed near them.

Usage:
    python scripts/history.py src/cart/total.ts
    python scripts/history.py src/cart/total.ts --lines 40-90
    python scripts/history.py src/cart/total.ts --since 2026-06-01 --limit 30
    python scripts/history.py src/cart/total.ts --lines 40-90 --json

Two views of the same file, because a regression needs both: `git blame` says
who last touched each line, and the commit log says what else moved through the
file around the same time — which is how you catch the case bisect cannot see,
where the culprit commit only exposed a fault an older commit introduced.

Exits 2 when the path is not tracked in a git repository.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

FIELD = "\x1f"
RECORD = "\x1e"


def git(args: List[str], cwd: str) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False
    )
    if result.returncode != 0:
        sys.stderr.write((result.stderr or result.stdout).strip() + "\n")
        raise SystemExit(2)
    return result.stdout


def ensure_tracked(path: str, cwd: str) -> None:
    """Raise ValueError unless path is a file tracked by git in cwd."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", path],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if result.returncode != 0:
        raise ValueError("not tracked in a git repository: %s" % path)


def parse_range(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not value:
        return None
    match = re.match(r"^(\d+)\s*[-:,]\s*(\d+)$", value.strip())
    if not match:
        raise SystemExit("--lines expects a range like 40-90")
    start, end = int(match.group(1)), int(match.group(2))
    if start < 1 or end < start:
        raise SystemExit("--lines range must be increasing and start at 1 or more")
    return start, end


def commits(path: str, cwd: str, since: Optional[str], limit: int) -> List[Dict[str, Any]]:
    # The record separator leads each entry so that the --numstat lines which
    # follow a commit header stay inside that commit's chunk, not the next one.
    fmt = RECORD + FIELD.join(["%h", "%an", "%ad", "%s"])
    args = ["log", "--no-merges", "--date=short", "--format=%s" % fmt, "-n", str(limit)]
    if since:
        args += ["--since", since]
    args += ["--numstat", "--", path]
    raw = git(args, cwd)

    entries: List[Dict[str, Any]] = []
    for chunk in raw.split(RECORD):
        if not chunk.strip():
            continue
        head, _, tail = chunk.lstrip("\n").partition("\n")
        parts = head.split(FIELD)
        if len(parts) < 4:
            continue
        added = removed = 0
        for line in tail.splitlines():
            cells = line.split("\t")
            if len(cells) == 3 and cells[0].isdigit() and cells[1].isdigit():
                added += int(cells[0])
                removed += int(cells[1])
        entries.append({
            "sha": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3],
            "added": added, "removed": removed,
        })
    return entries


def blame(path: str, cwd: str, span: Tuple[int, int]) -> List[Dict[str, Any]]:
    raw = git(["blame", "--line-porcelain", "-L", "%d,%d" % span, "--", path], cwd)
    groups: Dict[str, Dict[str, Any]] = {}
    current: Optional[str] = None
    for line in raw.splitlines():
        if re.match(r"^[0-9a-f]{7,40} \d+ \d+", line):
            current = line.split()[0][:12]
            groups.setdefault(current, {"sha": current, "lines": 0, "author": "", "date": "", "subject": ""})
            groups[current]["lines"] += 1
        elif current is None:
            continue
        elif line.startswith("author "):
            groups[current]["author"] = line[len("author "):]
        elif line.startswith("author-time "):
            groups[current]["time"] = int(line[len("author-time "):])
        elif line.startswith("summary "):
            groups[current]["subject"] = line[len("summary "):]
    for entry in groups.values():
        if entry.get("time"):
            entry["date"] = git(["show", "-s", "--date=short", "--format=%ad", entry["sha"]], cwd).strip()
        entry.pop("time", None)
    return sorted(groups.values(), key=lambda item: item["lines"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="file to investigate")
    parser.add_argument("--cwd", default=".", help="repository directory (default: .)")
    parser.add_argument("--lines", help="line range to blame, e.g. 40-90")
    parser.add_argument("--since", help="only commits after this date, e.g. 2026-06-01")
    parser.add_argument("--limit", type=int, default=20, help="how many commits to list (default: 20)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    span = parse_range(args.lines)
    try:
        ensure_tracked(args.path, args.cwd)
    except ValueError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2

    report: Dict[str, Any] = {
        "path": args.path,
        "commits": commits(args.path, args.cwd, args.since, args.limit),
        "blame": blame(args.path, args.cwd, span) if span else [],
        "lines": args.lines,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if span:
        print("blame %s:%s — who owns these lines" % (args.path, args.lines))
        if not report["blame"]:
            print("  (no lines in range)")
        for entry in report["blame"]:
            print("  %4d lines  %s  %-10s  %-12s  %s" % (
                entry["lines"], entry["sha"], entry.get("date", ""),
                entry.get("author", "")[:12], entry.get("subject", "")[:60],
            ))
        print("")

    print("recent commits touching %s" % args.path)
    if not report["commits"]:
        print("  (none in range)")
    for entry in report["commits"]:
        print("  %s  %s  %+5d/%-5d  %-12s  %s" % (
            entry["sha"], entry["date"], entry["added"], -entry["removed"],
            entry["author"][:12], entry["subject"][:60],
        ))

    if span and report["blame"]:
        top = report["blame"][0]
        print(
            "\nMost of this range was last touched by %s (%s)."
            % (top["sha"], (top.get("subject") or "")[:60])
        )
        print("That is a suspect, not a verdict: check whether an older commit in the list")
        print("above set up the assumption it broke.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
