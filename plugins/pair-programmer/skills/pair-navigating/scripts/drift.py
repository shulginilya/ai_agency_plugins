#!/usr/bin/env python3
"""Navigator drift check: what the change has actually touched, against what the session said it would.

Usage:
    python scripts/drift.py [--json] [--base REF] [--budget 400] [--scope src/auth ...]

The navigator's one mechanical job. Everything else a navigator does is
judgement; this part is arithmetic, and doing it by eye is how a two-file change
becomes an eleven-file change without anyone deciding it should.

It compares the working tree — staged, unstaged and untracked — against the
commit the session started from, and sorts the files into the scope the session
declared and everything else.

Exit codes are four answers:
    0   on scope, and inside the churn budget
    1   drift: files outside the declared scope, or churn past the budget
    2   unusable: no session, or this is not a git repository
    3   cannot tell: the session declares no scope, the base commit is gone, or
        the branch changed underneath it. That is a question for the pair, not
        a pass — an undeclared scope means nothing has been promised, and
        nothing can be broken.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SESSION_SCRIPTS = Path(__file__).resolve().parents[2] / "pair-session" / "scripts"
if str(SESSION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SESSION_SCRIPTS))

try:
    import session  # type: ignore
except ImportError:  # pragma: no cover - exercised only by a broken install
    session = None

ON_SCOPE, DRIFT, UNUSABLE, UNCLEAR = "on-scope", "drift", "unusable", "unclear"
EXIT = {ON_SCOPE: 0, DRIFT: 1, UNUSABLE: 2, UNCLEAR: 3}


def git(args: List[str], cwd: Optional[str] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def matches(path: str, patterns: List[str]) -> bool:
    """A pattern with no glob character is a prefix: `src/auth` covers everything under it."""
    normalised = path.replace("\\", "/")
    for pattern in patterns:
        pattern = pattern.replace("\\", "/").rstrip("/")
        if not any(ch in pattern for ch in "*?["):
            if normalised == pattern or normalised.startswith(pattern + "/"):
                return True
            continue
        if fnmatch.fnmatch(normalised, pattern) or fnmatch.fnmatch(normalised, pattern.rstrip("*") + "*"):
            return True
    return False


def changed_files(base: str, cwd: Optional[str] = None) -> Dict[str, int]:
    """Every file the change touches, with its churn (added + deleted lines).

    Untracked files count their whole length: a new 300-line file is not a
    zero-line change just because git has not been told about it yet.
    """
    churn: Dict[str, int] = {}
    numstat = git(["diff", "--numstat", base, "--"], cwd) or ""
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":  # binary
            churn[path] = churn.get(path, 0)
            continue
        churn[path] = churn.get(path, 0) + int(added) + int(deleted)

    untracked = git(["ls-files", "--others", "--exclude-standard"], cwd) or ""
    root = (git(["rev-parse", "--show-toplevel"], cwd) or "").strip()
    for path in untracked.splitlines():
        if not path.strip():
            continue
        lines = 0
        candidate = Path(root) / path if root else Path(path)
        try:
            if candidate.is_file() and candidate.stat().st_size < 2_000_000:
                lines = len(candidate.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        churn[path] = churn.get(path, 0) + lines
    return churn


def assess(scope: List[str], base: str, budget: int, cwd: Optional[str] = None,
           declared_branch: str = "") -> Dict[str, Any]:
    if git(["rev-parse", "--show-toplevel"], cwd) is None:
        return {"verdict": UNUSABLE, "reason": "not a git repository", "files": {},
                "in_scope": [], "out_of_scope": [], "churn": 0, "budget": budget}

    unclear: List[str] = []
    if not base or git(["rev-parse", "--verify", "--quiet", base + "^{commit}"], cwd) is None:
        unclear.append("the base commit %s does not resolve" % (base[:12] or "(none)"))
    branch_now = (git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "").strip()
    if declared_branch and branch_now and branch_now != declared_branch:
        unclear.append("the session started on %s and HEAD is now %s" % (declared_branch, branch_now))
    if not scope:
        unclear.append("the session declares no scope, so nothing has been promised")

    if unclear:
        return {"verdict": UNCLEAR, "reason": "; ".join(unclear), "files": {},
                "in_scope": [], "out_of_scope": [], "churn": 0, "budget": budget}

    churn = changed_files(base, cwd)
    in_scope = sorted(p for p in churn if matches(p, scope))
    out_of_scope = sorted(p for p in churn if p not in in_scope)
    total = sum(churn.values())

    reasons = []
    if out_of_scope:
        reasons.append("%d file(s) outside the declared scope" % len(out_of_scope))
    if budget and total > budget:
        reasons.append("%d changed lines against a budget of %d" % (total, budget))

    return {
        "verdict": DRIFT if reasons else ON_SCOPE,
        "reason": "; ".join(reasons) or "everything touched is inside the declared scope",
        "base": base, "branch": branch_now, "scope": scope, "budget": budget,
        "churn": total, "files": churn, "in_scope": in_scope, "out_of_scope": out_of_scope,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare the change against the session's declared scope.")
    parser.add_argument("--file", help="session file (default: .pair/session.json)")
    parser.add_argument("--base", help="override the session's base commit")
    parser.add_argument("--budget", type=int, help="override the session's churn budget")
    parser.add_argument("--scope", action="append", help="override the session's scope")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    scope = list(args.scope or [])
    base = args.base or ""
    budget = args.budget
    branch = ""
    if not (scope and base and budget is not None):
        if session is None:
            sys.stderr.write("the pair-session skill is not installed alongside this one\n")
            return EXIT[UNUSABLE]
        try:
            state = session.read(Path(args.file) if args.file else session.DEFAULT_PATH)
        except session.SessionError as exc:
            sys.stderr.write("%s\n" % exc)
            return EXIT[UNUSABLE]
        scope = scope or list(state.get("scope") or [])
        base = base or str(state.get("base_ref") or "")
        budget = budget if budget is not None else int(state.get("diff_budget") or 0)
        branch = str(state.get("branch") or "")

    report = assess(scope, base, budget or 0, declared_branch=branch)

    if args.json:
        print(json.dumps(report, indent=2))
        return EXIT[report["verdict"]]

    print("%s — %s" % (report["verdict"], report["reason"]))
    for path in report["out_of_scope"]:
        print("  outside  %-50s %d lines" % (path, report["files"][path]))
    for path in report["in_scope"]:
        print("  in       %-50s %d lines" % (path, report["files"][path]))
    if report["verdict"] == DRIFT:
        print("Either widen the scope on purpose, or move the extra work to its own change.")
    return EXIT[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
