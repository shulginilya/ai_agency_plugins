#!/usr/bin/env python3
"""GitHub Projects (v2) board steps for tickets and shipping, through `gh api graphql`.

    board.py boards                         open boards of the repo's owner, and where recent issues went
    board.py add    --project N --issue 21  put an issue on a board (idempotent), print the item id
    board.py move   --project N --issue 21 [--status "In review"]
                                            set the Status column and confirm it stuck
    board.py branch --issue 21              the branch name for an issue: <number>-<type>-<slug>
    board.py review --pr 42 [--project N]   move every ticket PR 42 closes to In review, on every
                                            board it is on, and confirm each move stuck

`move` re-reads the card after setting it, because board automations fire
asynchronously: the built-in "Pull request linked to issue" workflow moves the
card to In progress *after* the PR is opened and silently undoes an earlier
move to In review. A move is only reported done once the card has held the
column across several reads.

Standard library only; needs an authenticated `gh` (any version with `gh api`).
Exit status: 0 done, 1 GitHub refused or the column would not hold, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

TYPES = ("feat", "fix", "docs", "chore", "refactor", "test", "perf", "ci", "build", "style", "revert")
SLUG_WORDS = 4
SETTLE_READS = 3
SETTLE_SECONDS = 6.0
CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+(?:([\w.-]+/[\w.-]+))?#(\d+)", re.I)


class BoardError(Exception):
    pass


class InputError(BoardError):
    """The request cannot be satisfied as asked (exit 2), as opposed to GitHub refusing it (exit 1)."""


# --- pure helpers (unit-tested) ---------------------------------------------


def branch_name(number: int, title: str) -> str:
    """`feat(firstmate): install every plugin` + 21 -> `21-feat-firstmate-install-every-plugin`."""
    kind = ""
    match = re.match(r"\s*([a-z]+)(?:\(([^)]*)\))?!?:\s*(.*)", title)
    if match and match.group(1) in TYPES:
        kind = match.group(1)
        rest = " ".join(filter(None, [match.group(2), match.group(3)]))
    else:
        rest = title
    words = re.findall(r"[a-z0-9]+", rest.lower())[:SLUG_WORDS]
    return "-".join([str(number)] + ([kind] if kind else []) + words)


def match_option(options: List[Dict[str, str]], wanted: str) -> Dict[str, str]:
    """Pick the Status option for `wanted`: exact (case-insensitive), else the only one containing it."""
    norm = wanted.strip().lower()
    exact = [o for o in options if o["name"].strip().lower() == norm]
    if exact:
        return exact[0]
    partial = [o for o in options if norm in o["name"].lower()]
    if len(partial) == 1:
        return partial[0]
    names = ", ".join(o["name"] for o in options) or "(none)"
    if partial:
        raise InputError("'%s' matches more than one column: %s" % (wanted, names))
    raise InputError("no column matches '%s'; the board has: %s" % (wanted, names))


def linked_issues(body: str, closing: List[Dict[str, Any]], repo: Dict[str, str]) -> List[Tuple[str, str, int]]:
    """The tickets a PR closes, as (owner, name, number): GitHub's closing references first,
    then any `Closes #N` / `Fixes owner/repo#N` in the body that GitHub has not linked (yet)."""
    found: List[Tuple[str, str, int]] = []
    for ref in closing:
        owner, name = ref["repository"]["nameWithOwner"].split("/", 1)
        found.append((owner, name, int(ref["number"])))
    for match in CLOSING.finditer(body or ""):
        owner, name = match.group(1).split("/", 1) if match.group(1) else (repo["owner"], repo["name"])
        found.append((owner, name, int(match.group(2))))
    unique: List[Tuple[str, str, int]] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return unique


# --- gh plumbing -------------------------------------------------------------


def gh(*args: str) -> str:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise BoardError("gh is not installed")
    if result.returncode != 0:
        raise BoardError((result.stderr or result.stdout).strip() or "gh failed")
    return result.stdout


def graphql(query: str, **variables: Any) -> Dict[str, Any]:
    args = ["api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        args += ["-F" if isinstance(value, int) else "-f", "%s=%s" % (key, value)]
    payload = json.loads(gh(*args))
    if payload.get("errors"):
        raise BoardError("; ".join(e.get("message", "?") for e in payload["errors"]))
    return payload["data"]


def current_repo() -> Dict[str, str]:
    """The repo to act on: $GH_REPO when set (as every `gh issue` call already honors), else the cwd's."""
    named = os.environ.get("GH_REPO", "").strip()
    if named:
        parts = named.split("/")
        if len(parts) not in (2, 3) or not all(parts):
            raise InputError("GH_REPO must be OWNER/REPO or HOST/OWNER/REPO, not %r" % named)
        return {"owner": parts[-2], "name": parts[-1]}
    # gh 2.4's `repo view` ignores GH_REPO, which is why it is read above, not left to gh.
    owner, name = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip().split("/", 1)
    return {"owner": owner, "name": name}


OWNER_PROJECT = """
query($owner:String!,$number:Int!){repositoryOwner(login:$owner){
  ... on User{projectV2(number:$number){%s}}
  ... on Organization{projectV2(number:$number){%s}}}}"""

PROJECT_FIELDS = "id title field(name:\"Status\"){... on ProjectV2SingleSelectField{id options{id name}}}"


def project(owner: str, number: int) -> Dict[str, Any]:
    data = graphql(OWNER_PROJECT % (PROJECT_FIELDS, PROJECT_FIELDS), owner=owner, number=number)
    proj = (data.get("repositoryOwner") or {}).get("projectV2")
    if not proj:
        raise BoardError("board #%d not found for %s (does the token have the project scope?)" % (number, owner))
    if not proj.get("field"):
        raise BoardError("board '%s' has no single-select Status field" % proj["title"])
    return proj


def issue_node(repo: Dict[str, str], number: int) -> Dict[str, Any]:
    data = graphql(
        """query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){
          issue(number:$number){id title projectItems(first:20){nodes{id project{id number title}
            fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}""",
        owner=repo["owner"], name=repo["name"], number=number,
    )
    found = (data.get("repository") or {}).get("issue")
    if not found:
        raise BoardError("issue #%d not found in %s/%s" % (number, repo["owner"], repo["name"]))
    return found


def item_on(issue: Dict[str, Any], project_id: str) -> Optional[Dict[str, Any]]:
    for node in issue["projectItems"]["nodes"]:
        if node["project"]["id"] == project_id:
            return node
    return None


# --- commands ----------------------------------------------------------------


def cmd_boards(_: argparse.Namespace) -> Dict[str, Any]:
    repo = current_repo()
    nodes = "projectsV2(first:30){nodes{number title url closed}}"
    data = graphql(
        "query($owner:String!){repositoryOwner(login:$owner){... on User{%s} ... on Organization{%s}}}" % (nodes, nodes),
        owner=repo["owner"],
    )
    boards = [b for b in ((data.get("repositoryOwner") or {}).get("projectsV2") or {}).get("nodes", []) if not b["closed"]]
    recent = graphql(
        """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
          issues(last:10){nodes{number projectItems(first:5){nodes{project{number}}}}}}}""",
        owner=repo["owner"], name=repo["name"],
    )
    used: Dict[int, int] = {}
    for node in recent["repository"]["issues"]["nodes"]:
        for item in node["projectItems"]["nodes"]:
            used[item["project"]["number"]] = used.get(item["project"]["number"], 0) + 1
    for board in boards:
        board["recent_issues"] = used.get(board["number"], 0)
        del board["closed"]
    boards.sort(key=lambda b: -b["recent_issues"])
    return {"repo": "%s/%s" % (repo["owner"], repo["name"]), "boards": boards}


def cmd_add(args: argparse.Namespace) -> Dict[str, Any]:
    repo = current_repo()
    proj = project(repo["owner"], args.project)
    issue = issue_node(repo, args.issue)
    existing = item_on(issue, proj["id"])
    if existing:
        return {"board": proj["title"], "item": existing["id"], "added": False}
    data = graphql(
        "mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}",
        p=proj["id"], c=issue["id"],
    )
    return {"board": proj["title"], "item": data["addProjectV2ItemById"]["item"]["id"], "added": True}


def settle(repo: Dict[str, str], proj: Dict[str, Any], number: int, status: str,
           attempts: int, wait: float) -> Dict[str, Any]:
    """Set the card's Status, then re-read it until it holds against the board's automations."""
    option = match_option(proj["field"]["options"], status)
    history: List[str] = []
    for attempt in range(1, attempts + 1):
        issue = issue_node(repo, number)
        item = item_on(issue, proj["id"])
        if not item:
            raise BoardError("issue #%d is not on '%s'; run `add` first" % (number, proj["title"]))
        graphql(
            """mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{
              projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}""",
            p=proj["id"], i=item["id"], f=proj["field"]["id"], o=option["id"],
        )
        held = True
        for _ in range(SETTLE_READS):
            time.sleep(wait)
            now = (item_on(issue_node(repo, number), proj["id"]) or {}).get("fieldValueByName") or {}
            history.append(now.get("name") or "(none)")
            if now.get("name") != option["name"]:
                held = False  # an automation moved it back; set it again
                break
        if held:
            return {"board": proj["title"], "status": option["name"], "attempts": attempt, "reads": history}
    raise BoardError(
        "'%s' did not hold on '%s' after %d attempts (reads: %s); a board workflow keeps moving it"
        % (option["name"], proj["title"], attempts, ", ".join(history))
    )


def cmd_move(args: argparse.Namespace) -> Dict[str, Any]:
    repo = current_repo()
    return settle(repo, project(repo["owner"], args.project), args.issue, args.status, args.attempts, args.settle)


def cmd_review(args: argparse.Namespace) -> Dict[str, Any]:
    """After a PR opens: every ticket it closes goes to In review, on every board it is on."""
    repo = current_repo()
    data = graphql(
        """query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){
          pullRequest(number:$number){url state body
            closingIssuesReferences(first:20){nodes{number repository{nameWithOwner}}}}}}""",
        owner=repo["owner"], name=repo["name"], number=args.pr,
    )
    pr = (data.get("repository") or {}).get("pullRequest")
    if not pr:
        raise InputError("PR #%d not found in %s/%s" % (args.pr, repo["owner"], repo["name"]))
    tickets = linked_issues(pr["body"], pr["closingIssuesReferences"]["nodes"], repo)
    if not tickets:
        raise BoardError("PR #%d links no ticket: add `Closes #N` to its body, then run review again" % args.pr)
    moved: List[Dict[str, Any]] = []
    not_moved: List[Dict[str, Any]] = []
    for owner, name, number in tickets:
        where = {"owner": owner, "name": name}
        ref = "%s/%s#%d" % (owner, name, number)
        try:
            boards = [n["project"]["number"] for n in issue_node(where, number)["projectItems"]["nodes"]]
            if args.project:
                boards = [b for b in boards if b == args.project]
            if not boards:
                not_moved.append({"ticket": ref, "why": "not on %s" % ("board #%d" % args.project if args.project
                                                                      else "any board")})
            for board_number in boards:
                result = settle(where, project(owner, board_number), number, args.status, args.attempts, args.settle)
                moved.append(dict(result, ticket=ref))
        except BoardError as exc:
            not_moved.append({"ticket": ref, "why": str(exc)})
    result = {"pr": pr["url"], "moved": moved, "not_moved": not_moved}
    if not_moved:
        print(json.dumps(result, indent=2))
        raise BoardError("%d ticket(s) of PR #%d not in %s" % (len(not_moved), args.pr, args.status))
    return result


def cmd_branch(args: argparse.Namespace) -> Dict[str, Any]:
    title = args.title
    if title is None:
        title = issue_node(current_repo(), args.issue)["title"]
    return {"branch": branch_name(args.issue, title)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("boards", help="list open boards, most used by recent issues first")
    p = sub.add_parser("add", help="put an issue on a board")
    p.add_argument("--project", type=int, required=True)
    p.add_argument("--issue", type=int, required=True)
    p = sub.add_parser("move", help="set the Status column and confirm it held")
    p.add_argument("--project", type=int, required=True)
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--status", default="In review")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--settle", type=float, default=SETTLE_SECONDS, help="seconds between confirming reads")
    p = sub.add_parser("review", help="move every ticket a PR closes to In review, and confirm it held")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--project", type=int, help="only this board (default: every board the ticket is on)")
    p.add_argument("--status", default="In review")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--settle", type=float, default=SETTLE_SECONDS, help="seconds between confirming reads")
    p = sub.add_parser("branch", help="branch name for an issue")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--title", help="use this title instead of fetching the issue")
    args = parser.parse_args(argv)

    handlers = {"boards": cmd_boards, "add": cmd_add, "move": cmd_move, "review": cmd_review, "branch": cmd_branch}
    try:
        print(json.dumps(handlers[args.cmd](args), indent=2))
    except BoardError as exc:
        print("board: %s" % exc, file=sys.stderr)
        return 2 if isinstance(exc, InputError) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
