#!/usr/bin/env python3
"""List the files a review should cover.

Usage:
    python scripts/changed_files.py                 # working tree + index vs HEAD
    python scripts/changed_files.py --base main     # merge-base diff against a branch
    python scripts/changed_files.py --base origin/main --json
    python scripts/changed_files.py --stat          # include added/removed line counts

Exits 0 with an empty list when nothing changed, so a caller can distinguish
"no changes" from "not a git repository" (exit 2).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Dict, List

SKIP_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".snap",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".pdf",
)
SKIP_PARTS = ("node_modules", "dist", "build", "__pycache__", ".venv", "vendor")


def git(args: List[str]) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(2)
    return result.stdout


def interesting(path: str) -> bool:
    if path.endswith(SKIP_SUFFIXES):
        return False
    parts = path.split("/")
    return not any(part in SKIP_PARTS for part in parts)


def collect(base: str = None) -> List[Dict[str, object]]:
    if base:
        merge_base = git(["merge-base", "HEAD", base]).strip()
        raw = git(["diff", "--numstat", merge_base, "--"])
    else:
        raw = git(["diff", "--numstat", "HEAD", "--"])
        raw += git(["diff", "--numstat", "--cached", "--"])
        # Untracked files are part of the change under review even though no
        # diff command reports them; a new file is exactly where defects hide.
        for path in git(["ls-files", "--others", "--exclude-standard"]).splitlines():
            if path.strip():
                raw += "0\t0\t%s\n" % path.strip()

    files: Dict[str, Dict[str, object]] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        added, removed, path = (line.split("\t", 2) + ["", "", ""])[:3]
        if not path or not interesting(path):
            continue
        entry = files.setdefault(path, {"path": path, "added": 0, "removed": 0, "binary": False})
        if added == "-" or removed == "-":
            entry["binary"] = True
            continue
        entry["added"] = int(entry["added"]) + int(added or 0)
        entry["removed"] = int(entry["removed"]) + int(removed or 0)
    return sorted(files.values(), key=lambda item: str(item["path"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="branch or ref to diff against via merge-base")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--stat", action="store_true", help="show added/removed counts")
    args = parser.parse_args()

    files = collect(args.base)

    if args.json:
        print(json.dumps(files, indent=2))
        return 0
    if not files:
        print("no reviewable changes")
        return 0
    for entry in files:
        if args.stat:
            print("%+5d %-5d %s" % (entry["added"], -int(entry["removed"]), entry["path"]))
        else:
            print(entry["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
