#!/usr/bin/env python3
"""Say whether a pull request targets the repository's default branch, the only base QA accepts.

    pr_base.py --pr 38 [--repo owner/name]

A PR into any other branch (a stacked PR) would merge into a dead branch and
never reach the default one, so QA must not accept it or move its card. Exit 0
and `PR #38 targets main` when the base is the default branch. Otherwise it
prints "base is not <default>" on stderr, nothing on stdout, and exits 3: give
no accept or reject, post no verdict, leave the card where it is, and tell the
Captain the PR must be retargeted. Exit 1 when gh failed, 2 on bad input.

Standard library plus the gh CLI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


class BaseError(Exception):
    exit_code = 1


class InputError(BaseError):
    exit_code = 2


def base_problem(base: str, default: str) -> Optional[str]:
    """Why a PR into `base` cannot be accepted, or None when it targets the default branch."""
    if base == default:
        return None
    return ("base is not %s: the PR targets %s, so a merge would not reach %s. Give no verdict, move no card, "
            "and tell the Captain to retarget the PR to %s." % (default, base, default, default))


def gh(*args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise BaseError("gh is not installed")
    if done.returncode != 0:
        raise BaseError((done.stderr or done.stdout).strip() or "gh failed")
    return done.stdout


def current_repo(named: Optional[str]) -> str:
    if named:
        if not re.match(r"^[\w.-]+/[\w.-]+$", named):
            raise InputError("--repo is owner/name, not %r" % named)
        return named
    return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()


def default_branch(repo: str) -> str:
    return gh("api", "repos/%s" % repo, "-q", ".default_branch").strip()


def pr_info(repo: str, number: int) -> Dict[str, Any]:
    pr = json.loads(gh("api", "repos/%s/pulls/%d" % (repo, number)))
    return {"base": pr["base"]["ref"], "state": "merged" if pr.get("merged_at") else pr.get("state", "open")}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", help="owner/name; default: the current repository")
    args = parser.parse_args(argv)
    try:
        repo = current_repo(args.repo)
        info = pr_info(repo, args.pr)
        default = default_branch(repo)
    except (BaseError, KeyError, ValueError) as exc:
        print("pr_base: %s" % exc, file=sys.stderr)
        return exc.exit_code if isinstance(exc, BaseError) else 1
    problem = base_problem(info["base"], default)
    if problem:
        print("pr_base: %s#%d: %s" % (repo, args.pr, problem), file=sys.stderr)
        return 3
    print("PR #%d targets %s" % (args.pr, default))
    return 0


if __name__ == "__main__":
    sys.exit(main())
