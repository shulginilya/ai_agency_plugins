#!/usr/bin/env python3
"""Drive `git bisect run` against a scripted reproduction.

Usage:
    # plan only — no checkout, no repo state touched (the default)
    python scripts/bisect.py --good v1.4.0 --cmd "npm test -- cart.total"

    # actually bisect
    python scripts/bisect.py --good v1.4.0 --cmd "npm test -- cart.total" --run

    # repeat the verdict to survive a slightly flaky test, and reinstall per commit
    python scripts/bisect.py --good abc123 --cmd "pytest -x -q tests/test_cart.py" \
        --setup "pip install -q -e ." --times 3 --run

Bisecting rewrites the working tree, so this script refuses to start on a dirty
tree and always runs `git bisect reset`, including on interrupt. The verdict is
executed by re-invoking this script (`--verdict`), which keeps it working on
Windows where `sh -c` may not be on PATH: a failing `--setup` exits 125, which
tells git to skip an unbuildable commit rather than call it bad.

Exit codes:
    0   plan printed, or a first bad commit was found
    1   the bisect ran but did not identify a commit
    2   preconditions not met (not a repo, dirty tree, bad refs, usage)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from typing import Dict, List, Optional

LOCKFILES = [
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "poetry.lock", "Pipfile.lock", "requirements.txt", "go.sum", "Cargo.lock",
]


def git(args: List[str], cwd: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False
    )
    if result.returncode != 0 and check:
        raise RuntimeError((result.stderr or result.stdout).strip() or "git %s failed" % args[0])
    return result.stdout


def verdict(command: str, setup: Optional[str], times: int, cwd: str) -> int:
    """Run the reproduction; 0 good, 1 bad, 125 untestable."""
    if setup:
        if subprocess.run(setup, shell=True, cwd=cwd, check=False).returncode != 0:
            sys.stderr.write("bisect: setup failed, skipping this commit\n")
            return 125
    for _ in range(times):
        if subprocess.run(command, shell=True, cwd=cwd, check=False).returncode != 0:
            return 1
    return 0


def plan(cwd: str, good: str, bad: str, command: str, setup: Optional[str], times: int) -> Dict[str, object]:
    good_sha = git(["rev-parse", "--verify", "%s^{commit}" % good], cwd).strip()
    bad_sha = git(["rev-parse", "--verify", "%s^{commit}" % bad], cwd).strip()

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", good_sha, bad_sha],
        cwd=cwd, capture_output=True, text=True, check=False,
    ).returncode == 0

    revs = git(["rev-list", "--count", "%s..%s" % (good_sha, bad_sha)], cwd).strip()
    count = int(revs or 0)
    merges = int(git(["rev-list", "--count", "--merges", "%s..%s" % (good_sha, bad_sha)], cwd).strip() or 0)
    touched = [
        name for name in LOCKFILES
        if git(["log", "--oneline", "%s..%s" % (good_sha, bad_sha), "--", name], cwd, check=False).strip()
    ]
    dirty = bool(git(["status", "--porcelain"], cwd).strip())
    # --git-dir is relative to the repository, and isfile() would resolve it
    # against this process's cwd instead. Ask for the absolute path.
    git_dir = git(["rev-parse", "--absolute-git-dir"], cwd).strip()
    shallow = os.path.isfile(os.path.join(git_dir, "shallow"))

    warnings: List[str] = []
    if not ancestor:
        warnings.append(
            "%s is not an ancestor of %s — bisect needs the good ref to be reachable from the bad one."
            % (good, bad)
        )
    if count == 0:
        warnings.append("the range is empty: nothing to bisect between these refs.")
    if dirty:
        warnings.append("the working tree is dirty; commit or stash before running with --run.")
    if shallow:
        warnings.append("this is a shallow clone; run `git fetch --unshallow` first.")
    if merges:
        warnings.append(
            "%d merge commits in range; consider --first-parent to bisect releases rather than branch internals."
            % merges
        )
    if touched and not setup:
        warnings.append(
            "dependencies changed in this range (%s); pass --setup with the install command, "
            "or you will test today's dependencies against old code." % ", ".join(touched)
        )

    return {
        "good": good_sha,
        "bad": bad_sha,
        "commits": count,
        "steps": int(math.ceil(math.log(count, 2))) if count > 1 else count,
        "merges": merges,
        "verdict_command": command,
        "setup_command": setup,
        "times": times,
        "warnings": warnings,
        "blocking": bool(dirty or not ancestor or count == 0),
    }


def run(cwd: str, good: str, bad: str, command: str, setup: Optional[str], times: int,
        first_parent: bool) -> Dict[str, object]:
    args = ["bisect", "start"]
    if first_parent:
        args.append("--first-parent")
    args += [bad, good]
    git(args, cwd)
    try:
        verdict_argv = [sys.executable, os.path.abspath(__file__), "--verdict", "--cmd", command,
                        "--times", str(times)]
        if setup:
            verdict_argv += ["--setup", setup]
        result = subprocess.run(
            ["git", "bisect", "run"] + verdict_argv,
            cwd=cwd, capture_output=True, text=True, check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        culprit = ""
        for line in output.splitlines():
            if "is the first bad commit" in line:
                culprit = line.split()[0]
                break
        report: Dict[str, object] = {"culprit": culprit, "log": output.strip()[-6000:]}
        if culprit:
            report["details"] = git(
                ["show", "--stat", "--no-color",
                 "--format=%H%n%an <%ae>%n%ad%n%n%s%n%n%b", culprit], cwd, check=False
            )
        return report
    finally:
        git(["bisect", "reset"], cwd, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="repository directory (default: .)")
    parser.add_argument("--good", help="a ref where the reproduction passes")
    parser.add_argument("--bad", default="HEAD", help="a ref where it fails (default: HEAD)")
    parser.add_argument("--cmd", help="the verdict command: exit 0 when good, non-zero when bad")
    parser.add_argument("--setup", help="build/install command run before each verdict; failure means skip")
    parser.add_argument("--times", type=int, default=1, help="repeat the verdict N times (bad if any run fails)")
    parser.add_argument("--first-parent", action="store_true", help="bisect merges only, not branch internals")
    parser.add_argument("--run", action="store_true", help="actually bisect; without it only the plan is printed")
    parser.add_argument("--verdict", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.verdict:
        if not args.cmd:
            return 2
        return verdict(args.cmd, args.setup, max(1, args.times), args.cwd)

    if not args.good or not args.cmd:
        parser.error("--good and --cmd are required")
    if args.times < 1:
        parser.error("--times must be at least 1")

    cwd = os.path.abspath(args.cwd)
    try:
        git(["rev-parse", "--git-dir"], cwd)
        proposal = plan(cwd, args.good, args.bad, args.cmd, args.setup, args.times)
    except RuntimeError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2

    if not args.run:
        if args.json:
            print(json.dumps(proposal, indent=2))
        else:
            print("bisect plan")
            print("  good:    %s" % proposal["good"])
            print("  bad:     %s" % proposal["bad"])
            print("  range:   %s commits, about %s steps" % (proposal["commits"], proposal["steps"]))
            print("  verdict: %s (x%s)" % (proposal["verdict_command"], proposal["times"]))
            if proposal["setup_command"]:
                print("  setup:   %s" % proposal["setup_command"])
            for warning in proposal["warnings"]:
                print("  ! %s" % warning)
            print("\nVerify the verdict on both ends before trusting the result, then re-run with --run.")
        return 0

    if proposal["blocking"]:
        for warning in proposal["warnings"]:
            sys.stderr.write("%s\n" % warning)
        return 2

    report = run(cwd, args.good, args.bad, args.cmd, args.setup, args.times, args.first_parent)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["culprit"] else 1
    if report["culprit"]:
        print("first bad commit: %s\n" % report["culprit"])
        print(report.get("details", ""))
        print("The commit is a lead, not a cause. Read the hunk that touches the failing path,")
        print("name the assumption it broke, then prove it with the root-cause-analysis skill.")
        return 0
    print(report["log"])
    sys.stderr.write("\nbisect did not identify a commit; see the log above.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
