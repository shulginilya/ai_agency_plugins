#!/usr/bin/env python3
"""Refuse to ship a branch that would open a PR the crew cannot land on the default branch.

    ship_check.py [--expected-branch NAME] [--default BRANCH] [--remote origin]

Run it on the checked-out branch, before the commit and the push. It stops, with
every reason on stderr and nothing on stdout, when:

* the branch is the default branch: branch first;
* --expected-branch (the name `board.py branch --issue N` gives) is given and the
  branch is called something else;
* the branch descends from another branch that is not merged into the default
  branch (a local branch or one on the remote): a PR from it would stack on
  that branch, and a merge of the stack lands in a dead branch.

Otherwise it prints the `gh pr create --base <default>` flag to use. The default
branch is --default, else `gh repo view --json defaultBranchRef`. Exit status:
0 shippable, 1 refused, 2 it could not run.

Standard library plus git and gh.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Optional


class CheckError(Exception):
    pass


def git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise CheckError("git is not installed")


def default_branch() -> str:
    try:
        done = subprocess.run(["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"],
                              capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise CheckError("gh is not installed; pass --default")
    if done.returncode != 0 or not done.stdout.strip():
        raise CheckError("could not read the default branch: %s" % (done.stderr or done.stdout).strip())
    return done.stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    return git("merge-base", "--is-ancestor", a, b).returncode == 0


def problems(default: str, expected: Optional[str], remote: str = "origin") -> List[str]:
    current = git("branch", "--show-current").stdout.strip()
    if not current:
        return ["HEAD is detached: check out the ticket's branch first"]
    if current == default:
        return ["the current branch is the default branch %s: branch from it first, never ship from it" % default]
    found: List[str] = []
    if expected and current != expected:
        found.append("the branch is %s, but the ticket's branch is %s: rename it (git branch -m %s) and run again"
                     % (current, expected, expected))
    base = "%s/%s" % (remote, default)
    if git("rev-parse", "--verify", "-q", base).returncode != 0:
        base = default
    head = git("rev-parse", "HEAD").stdout.strip()
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/%s" % remote).stdout.split()
    skip = {current, default, base, "%s/%s" % (remote, current), "%s/HEAD" % remote, remote}
    named = set()
    for ref in refs:
        short = ref[len(remote) + 1:] if ref.startswith(remote + "/") else ref
        if ref in skip or short in named or git("rev-parse", ref).stdout.strip() == head:
            continue
        if not is_ancestor(ref, base) and is_ancestor(ref, "HEAD"):
            named.add(short)
            found.append("the branch is based on the unmerged branch %s, which is not in %s: a PR from it stacks "
                         "on that branch and a merge lands in a dead branch. Ship %s first and let the Captain "
                         "merge it, then branch this ticket from an up-to-date %s"
                         % (short, default, short, default))
    return found


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--expected-branch", help="the name `board.py branch --issue N` printed")
    parser.add_argument("--default", help="the default branch; default: asked of gh")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    try:
        default = args.default or default_branch()
        found = problems(default, args.expected_branch, args.remote)
    except CheckError as exc:
        print("ship_check: %s" % exc, file=sys.stderr)
        return 2
    if found:
        for line in found:
            print("ship_check: %s" % line, file=sys.stderr)
        print("ship_check: not shipping: no PR is opened.", file=sys.stderr)
        return 1
    print("shippable: open the PR with --base %s" % default)
    return 0


if __name__ == "__main__":
    sys.exit(main())
