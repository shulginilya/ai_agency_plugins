#!/usr/bin/env python3
"""Say what a pull request review should cover, and whether its head commit was already reviewed.

    pr_scope.py --pr 43 [--repo owner/name] [--json]

Reads the PR through `gh`: its head commit, base branch, changed files with
added and removed line counts, the tickets it closes with their labels, the
boards they are on and the column an approve moves each one to (In approval,
or QA when it is labelled skip_approval), and every earlier review. A review counts as a verdict when its body
carries the `<!-- code-review:verdict ... -->` marker review_report.py
prints. Then it says what to do:

    review      no earlier verdict on this PR
    re-review   the last verdict reviewed a different commit: review the new
                head in full, since a fix can break what passed before
    up-to-date  the last verdict reviewed this head commit: nothing new

A PR that is closed or merged is reported as such, with action `closed`.

It also prints the review `round` this one would be: 1 plus the request-changes
verdicts given since the last approve or stop. An approve ends a fix loop (a
QA reject after it starts a new one at round 1), and so does a stop
(review_report.py stops the loop on round 4 when issues are left). And the
`captain` to @mention on a stop: the PR's first assignee, else the repository
owner.

Standard library plus the gh CLI. Exit status: 0 done, 1 gh failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_report import MAX_ROUNDS, move_to, verdict_of  # noqa: E402


class ScopeError(Exception):
    exit_code = 1


class InputError(ScopeError):
    exit_code = 2


# --- pure helpers (unit-tested) ---------------------------------------------


def same_commit(a: Optional[str], b: Optional[str]) -> bool:
    """A short and a long form of one commit are the same commit."""
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def round_of(verdicts: List[Dict[str, Any]]) -> int:
    """The next review's round: 1 plus the request-changes verdicts since the last approve or stop,
    either of which ended the previous fix loop."""
    since = 0
    for v in sorted(verdicts, key=lambda v: v["at"]):
        since = 0 if v.get("verdict") in ("approve", "stop") else since + 1
    return since + 1


def captain_of(assignees: List[str], repo: str) -> str:
    """Who a stop @mentions: the PR's first assignee, else the repository owner."""
    return assignees[0] if assignees else repo.split("/")[0]


def decide(head: str, reviews: List[Dict[str, Any]], state: str = "open") -> Dict[str, Any]:
    """`reviews` each {"body", "submitted_at", "url"?}, in any order."""
    if state != "open":
        return {"action": "closed", "reason": "the PR is %s; there is nothing to review" % state, "last": None,
                "round": None}
    verdicts = []
    for r in reviews:
        marker = verdict_of(r.get("body") or "")
        if marker is not None:
            verdicts.append(dict(marker, at=r.get("submitted_at") or "", url=r.get("url") or ""))
    if not verdicts:
        return {"action": "review", "reason": "no earlier code-review verdict on this PR", "last": None, "round": 1}
    last = max(verdicts, key=lambda v: v["at"])
    if same_commit(last.get("commit"), head):
        return {"action": "up-to-date", "last": last, "round": None,
                "reason": "the last verdict (%s) already reviewed head %s" % (last.get("verdict"), head[:7])}
    return {"action": "re-review", "last": last, "round": round_of(verdicts),
            "reason": "the last verdict (%s) reviewed %s; the head is now %s"
                      % (last.get("verdict"), (last.get("commit") or "unknown")[:7], head[:7])}


# --- gh plumbing -------------------------------------------------------------


def gh(*args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise ScopeError("gh is not installed")
    if done.returncode != 0:
        raise ScopeError((done.stderr or done.stdout).strip() or "gh failed")
    return done.stdout


def pages(path: str) -> List[Dict[str, Any]]:
    return concat_pages(gh("api", "--paginate", path))


def concat_pages(out: str) -> List[Dict[str, Any]]:
    """--paginate prints one JSON array per page, back to back; decode them in turn,
    since a patch or a body can itself contain "][" and defeat splitting on it."""
    decoder, items, i = json.JSONDecoder(), [], 0
    while True:
        while i < len(out) and out[i].isspace():
            i += 1
        if i >= len(out):
            return items
        page, i = decoder.raw_decode(out, i)
        items += page


def current_repo(named: Optional[str]) -> str:
    if named:
        if not re.match(r"^[\w.-]+/[\w.-]+$", named):
            raise InputError("--repo is owner/name, not %r" % named)
        return named
    return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()


def closing_tickets(repo: str, number: int) -> List[Dict[str, Any]]:
    owner, name = repo.split("/")
    data = json.loads(gh("api", "graphql", "-f", "query=query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n)"
                         "{pullRequest(number:$i){closingIssuesReferences(first:10){nodes{number title labels(first:50){nodes{name}}"
                         " projectItems(first:20){nodes{project{number title}"
                         " fieldValueByName(name:\"Status\"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}}}",
                         "-f", "o=%s" % owner, "-f", "n=%s" % name, "-F", "i=%d" % number))
    pr = ((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
    tickets = []
    for issue in (pr.get("closingIssuesReferences") or {}).get("nodes", []):
        boards = [{"number": i["project"]["number"], "title": i["project"]["title"],
                   "status": (i.get("fieldValueByName") or {}).get("name")}
                  for i in (issue.get("projectItems") or {}).get("nodes", [])]
        labels = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]
        tickets.append({"number": issue["number"], "title": issue.get("title"), "labels": labels,
                        "approve_to": move_to("approve", labels), "boards": boards})
    return tickets


def fetch(repo: str, number: int) -> Dict[str, Any]:
    pr = json.loads(gh("api", "repos/%s/pulls/%d" % (repo, number)))
    state = "merged" if pr.get("merged_at") else pr.get("state", "open")
    files = [{"file": f["filename"], "status": f.get("status"), "added": f.get("additions", 0),
              "removed": f.get("deletions", 0)} for f in pages("repos/%s/pulls/%d/files?per_page=100" % (repo, number))]
    reviews = [{"body": r.get("body") or "", "submitted_at": r.get("submitted_at") or "", "url": r.get("html_url") or ""}
               for r in pages("repos/%s/pulls/%d/reviews?per_page=100" % (repo, number))]
    return {"url": pr.get("html_url"), "title": pr.get("title"), "state": state,
            "head": pr["head"]["sha"], "head_ref": pr["head"]["ref"], "base": pr["base"]["ref"],
            "files": files, "reviews": reviews, "tickets": closing_tickets(repo, number),
            "captain": captain_of([a["login"] for a in pr.get("assignees") or []], repo)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", help="owner/name; default: the current repository")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo = current_repo(args.repo)
        pr = fetch(repo, args.pr)
    except ScopeError as exc:
        print("pr_scope: %s" % exc, file=sys.stderr)
        return exc.exit_code
    decided = decide(pr["head"], pr["reviews"], pr["state"])
    result = dict(decided, pr="%s#%d" % (repo, args.pr), url=pr["url"], title=pr["title"], head=pr["head"],
                  head_ref=pr["head_ref"], base=pr["base"], files=pr["files"], tickets=pr["tickets"],
                  captain=pr["captain"])
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print("%s: %s — %s" % (result["pr"], result["action"], result["reason"]))
    if result["round"]:
        print("round %d of %d; captain @%s" % (result["round"], MAX_ROUNDS, result["captain"]))
    print("head %s (%s) into %s, %d files:" % (result["head"][:7], result["head_ref"], result["base"], len(result["files"])))
    for f in result["files"]:
        print("  %-9s +%-5d -%-5d %s" % (f["status"], f["added"], f["removed"], f["file"]))
    for t in result["tickets"]:
        print("closes #%d %s (on approve: %s)" % (t["number"], t["title"], t["approve_to"]))
        for b in t["boards"]:
            print("  board #%d %s: %s" % (b["number"], b["title"], b["status"] or "(no column)"))
    if not result["tickets"]:
        print("closes no ticket: there is no card to move")
    return 0


if __name__ == "__main__":
    sys.exit(main())
