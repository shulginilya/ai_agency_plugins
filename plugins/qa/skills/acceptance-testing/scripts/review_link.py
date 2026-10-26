#!/usr/bin/env python3
"""Find the review link on a ticket and decide whether QA tests, re-tests or has nothing new.

    review_link.py --issue 42 [--repo owner/name] [--commit SHA] [--json]

A review link is any link shaped `<name>.<project_slug>.review.com`, with or
without `https://` and a path. `<name>` is usually the branch, but anything
goes. The ticket's description and every comment are read; the newest link
wins (comments are newer than the description, later comments newer than
earlier ones). QA's own verdict comments, which carry a `<!-- qa:verdict ... -->`
marker, are never read as a new link.

The decision:

    none        no review link: test locally or on a preview the PR names
    test        a review link and no QA verdict yet
    retest      a verdict exists, but a link came after it, the newest link is not
                the one it tested, or --commit differs from the commit it tested
    up-to-date  the newest link was already verdicted on this commit; nothing new

The ticket's boards are listed too, for the move that follows the verdict.

Standard library only; needs an authenticated `gh`.
Exit status: 0 decided, 1 GitHub refused, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

LINK_RE = re.compile(
    r"(?<![\w.-])(?:https?://)?([A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?)\.([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)"
    r"\.review\.com(?::\d+)?(/[^\s<>()\[\]\"'`]*)?(?![\w-])", re.I)
VERDICT_RE = re.compile(r"<!--\s*qa:verdict\b([^>]*)-->")
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


class LinkError(Exception):
    exit_code = 1


class InputError(LinkError):
    exit_code = 2


# --- pure helpers (unit-tested) ---------------------------------------------


def links_in(text: str) -> List[str]:
    """Every review link in a text, normalized to https:// with no trailing punctuation."""
    found = []
    for m in LINK_RE.finditer(text or ""):
        path = (m.group(3) or "").rstrip(".,;:!?")
        found.append("https://%s.%s.review.com%s" % (m.group(1).lower(), m.group(2).lower(), path))
    return found


def verdict_of(body: str) -> Optional[Dict[str, str]]:
    """The attributes of a QA verdict marker, e.g. verdict=accept link=https://... commit=abc1234."""
    m = VERDICT_RE.search(body or "")
    if not m:
        return None
    return {k: v.strip('"') for k, v in ATTR_RE.findall(m.group(1))}


def decide(body: str, comments: List[Dict[str, Any]], commit: Optional[str] = None) -> Dict[str, Any]:
    """`comments` oldest first, each {"body", "created_at", "url"}."""
    sources = [{"where": "description", "at": "", "links": links_in(body)}]
    last_verdict, verdict_index = None, None
    for n, c in enumerate(comments, 1):
        verdict = verdict_of(c.get("body", ""))
        if verdict is not None:
            last_verdict, verdict_index = dict(verdict, at=c.get("created_at", ""), url=c.get("url", "")), n
            sources.append({"where": c.get("url", ""), "at": c.get("created_at", ""), "links": []})
            continue
        sources.append({"where": c.get("url", ""), "at": c.get("created_at", ""), "links": links_in(c.get("body", ""))})
    with_links = [(n, s) for n, s in enumerate(sources) if s["links"]]
    result: Dict[str, Any] = {"link": None, "source": None, "all_links": [l for _, s in with_links for l in s["links"]],
                              "last_verdict": last_verdict}
    if not with_links:
        result.update(action="none", reason="no review link in the description or comments")
        return result
    n, newest = with_links[-1]
    result.update(link=newest["links"][-1], source=newest["where"])
    if last_verdict is None:
        result.update(action="test", reason="a review link and no QA verdict yet")
    elif n > verdict_index:
        result.update(action="retest", reason="a review link was posted after the last QA verdict")
    elif last_verdict.get("link") != result["link"]:
        result.update(action="retest", reason="the last verdict tested %s, not the newest link"
                      % (last_verdict.get("link") or "no review link"))
    elif commit and last_verdict.get("commit") and not (
            commit.startswith(last_verdict["commit"]) or last_verdict["commit"].startswith(commit)):
        result.update(action="retest", reason="the last verdict tested commit %s, not %s"
                      % (last_verdict["commit"], commit))
    else:
        result.update(action="up-to-date", reason="the newest link was already verdicted (%s); nothing new"
                      % last_verdict.get("verdict", "?"))
    return result


# --- gh plumbing -------------------------------------------------------------


def gh(*args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise LinkError("gh is not installed")
    if done.returncode != 0:
        raise LinkError((done.stderr or done.stdout).strip() or "gh failed")
    return done.stdout


def current_repo(named: Optional[str]) -> str:
    if named:
        if not re.match(r"^[\w.-]+/[\w.-]+$", named):
            raise InputError("--repo is owner/name, not %r" % named)
        return named
    return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()


def fetch(repo: str, number: int) -> Dict[str, Any]:
    issue = json.loads(gh("api", "repos/%s/issues/%d" % (repo, number)))
    pages = gh("api", "--paginate", "repos/%s/issues/%d/comments?per_page=100" % (repo, number))
    comments: List[Dict[str, Any]] = []
    for chunk in re.split(r"(?<=\])\s*(?=\[)", pages.strip()) if pages.strip() else []:
        comments += json.loads(chunk)  # --paginate prints one JSON array per page
    owner, name = repo.split("/")
    data = json.loads(gh("api", "graphql", "-f", "query=query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n)"
                         "{issue(number:$i){projectItems(first:20){nodes{project{number title}"
                         " fieldValueByName(name:\"Status\"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}",
                         "-f", "o=%s" % owner, "-f", "n=%s" % name, "-F", "i=%d" % number))
    items = (((data.get("data") or {}).get("repository") or {}).get("issue") or {}).get("projectItems") or {}
    boards = [{"number": i["project"]["number"], "title": i["project"]["title"],
               "status": (i.get("fieldValueByName") or {}).get("name")} for i in items.get("nodes", [])]
    comments.sort(key=lambda c: c.get("created_at", ""))
    return {"title": issue.get("title"), "body": issue.get("body") or "", "url": issue.get("html_url"),
            "comments": [{"body": c.get("body") or "", "created_at": c.get("created_at", ""),
                          "url": c.get("html_url", "")} for c in comments], "boards": boards}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--repo", help="owner/name; default: the current repository")
    parser.add_argument("--commit", help="the commit about to be tested; a different one than last time means retest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo = current_repo(args.repo)
        ticket = fetch(repo, args.issue)
    except LinkError as exc:
        print("review_link: %s" % exc, file=sys.stderr)
        return exc.exit_code
    result = dict(decide(ticket["body"], ticket["comments"], args.commit),
                  ticket="%s#%d" % (repo, args.issue), boards=ticket["boards"])
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("%s: %s — %s" % (result["ticket"], result["action"], result["reason"]))
        if result["link"]:
            print("review link: %s  (from %s)" % (result["link"], result["source"]))
        for b in result["boards"]:
            print("board #%d %s: %s" % (b["number"], b["title"], b["status"] or "(no column)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
