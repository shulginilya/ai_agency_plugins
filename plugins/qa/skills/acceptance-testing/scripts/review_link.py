#!/usr/bin/env python3
"""Find the review link on a ticket, which build it serves, and whether QA tests, waits, re-tests or has nothing new.

    review_link.py --issue 42 [--pr 43 | --commit SHA] [--repo owner/name]
                   [--domain review.example.com] [--wait SECONDS] [--local] [--json]

With --local (review links are paused: QA tests the PR's head commit locally),
every link is ignored and the decision rests on the commit alone: `test` with
no QA verdict yet (or no commit to compare), `retest` when the last verdict
tested another commit, `up-to-date` when it tested this one.

A review link is any link shaped `<name>.<project_slug>.<review domain>`, with
or without `https://` and a path. `<name>` is usually the branch, but anything
goes. The review domain is `--domain`, else the repository's Actions variable
REVIEW_DOMAIN, else the placeholder `review.com`.

Where links come from, newest first:

* the devops comment: one comment per ticket, edited on every deploy, with a
  `<!-- devops:review-link link=... commit=... pr=... state=live|down -->`
  marker. It counts as new as of its last edit, and it says which commit the
  link serves; `state=down` (the PR closed) means no link;
* any other comment or the description: the link as pasted. Comments are newer
  than the description, later comments newer than earlier ones. The commit it
  serves is unknown, so check it with preview_link.py.

QA's own verdict comments (`<!-- qa:verdict ... -->`) are never read as a link.

The decision, against the commit under test (`--commit`, or `--pr`'s head):

    none        no review link: use the PR's preview (preview_link.py), else test locally
    wait        the link still serves an older commit than the one under test:
                the new build hasn't landed. Don't test it; --wait polls until it has
    test        a review link and no QA verdict yet
    retest      a verdict exists, but the link or the commit is not the one it tested,
                or a pasted link came after it
    up-to-date  the newest link was already verdicted on this commit; nothing new

The ticket's boards are listed too, for the move that follows the verdict.

Standard library only; needs an authenticated `gh`.
Exit status: 0 decided, 1 GitHub refused, 2 bad input, 3 still `wait` when --wait ran out.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

DEFAULT_DOMAIN = "review.com"
VERDICT_RE = re.compile(r"<!--\s*qa:verdict\b([^>]*)-->")
DEVOPS_RE = re.compile(r"<!--\s*devops:review-link\b([^>]*)-->")
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')
DOMAIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")


class LinkError(Exception):
    exit_code = 1


class InputError(LinkError):
    exit_code = 2


# --- pure helpers (unit-tested) ---------------------------------------------


def link_re(domain: str = DEFAULT_DOMAIN) -> "re.Pattern[str]":
    label = r"([A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?)"
    return re.compile(r"(?<![\w.-])(?:https?://)?%s\.%s\.%s(?::\d+)?(/[^\s<>()\[\]\"'`]*)?(?![\w-])"
                      % (label, label.replace("_", ""), re.escape(domain)), re.I)


def links_in(text: str, domain: str = DEFAULT_DOMAIN) -> List[str]:
    """Every review link in a text, normalized to https:// with no trailing punctuation."""
    found = []
    for m in link_re(domain).finditer(text or ""):
        path = (m.group(3) or "").rstrip(".,;:!?")
        found.append("https://%s.%s.%s%s" % (m.group(1).lower(), m.group(2).lower(), domain.lower(), path))
    return found


def attrs(regex: "re.Pattern[str]", body: str) -> Optional[Dict[str, str]]:
    m = regex.search(body or "")
    if not m:
        return None
    return {k: v.strip('"') for k, v in ATTR_RE.findall(m.group(1))}


def verdict_of(body: str) -> Optional[Dict[str, str]]:
    """The attributes of a QA verdict marker, e.g. verdict=accept link=https://... commit=abc1234."""
    return attrs(VERDICT_RE, body)


def devops_of(body: str) -> Optional[Dict[str, str]]:
    """The attributes of the devops review-link marker, e.g. link=https://... commit=abc1234 pr=43 state=live."""
    return attrs(DEVOPS_RE, body)


def same_commit(a: Optional[str], b: Optional[str]) -> bool:
    """A short and a long form of one commit are the same commit."""
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def decide_local(comments: List[Dict[str, Any]], commit: Optional[str] = None) -> Dict[str, Any]:
    """Review links are paused: test / retest / up-to-date on the commit alone, whatever links the ticket holds."""
    verdicts = sorted((dict(v, at=c.get("created_at", ""), url=c.get("url", ""))
                       for c in comments for v in [verdict_of(c.get("body", ""))] if v is not None),
                      key=lambda v: v["at"])
    last_verdict = verdicts[-1] if verdicts else None
    result: Dict[str, Any] = {"link": None, "source": None, "serves": None, "domain": None,
                              "all_links": [], "last_verdict": last_verdict, "local": True}
    if last_verdict is None:
        result.update(action="test", reason="no QA verdict yet: test the PR head locally")
    elif not commit:
        result.update(action="test", reason="no commit to compare with the last verdict: test locally")
    elif last_verdict.get("commit") and same_commit(commit, last_verdict["commit"]):
        result.update(action="up-to-date", reason="commit %s was already verdicted (%s); nothing new"
                      % (commit[:7], last_verdict.get("verdict", "?")))
    else:
        result.update(action="retest", reason="the last verdict tested commit %s, not %s"
                      % (last_verdict.get("commit") or "unknown", commit[:7]))
    return result


def decide(body: str, comments: List[Dict[str, Any]], commit: Optional[str] = None,
           domain: str = DEFAULT_DOMAIN, local: bool = False) -> Dict[str, Any]:
    """`comments` each {"body", "created_at", "updated_at"?, "url"}, in any order."""
    if local:
        return decide_local(comments, commit)
    sources = [{"where": "description", "at": "", "links": links_in(body, domain), "serves": None, "kind": "pasted"}]
    verdicts = []
    for c in comments:
        text, created = c.get("body", ""), c.get("created_at", "")
        verdict = verdict_of(text)
        if verdict is not None:
            verdicts.append(dict(verdict, at=created, url=c.get("url", "")))
            continue
        marker = devops_of(text)
        if marker is not None:
            live = marker.get("state", "live") == "live" and marker.get("link")
            sources.append({"where": c.get("url", ""), "at": c.get("updated_at") or created, "kind": "devops",
                            "links": [marker["link"]] if live else [], "serves": marker.get("commit"),
                            "pr": marker.get("pr")})
        else:
            sources.append({"where": c.get("url", ""), "at": created, "links": links_in(text, domain),
                            "serves": None, "kind": "pasted"})
    sources.sort(key=lambda s: s["at"])  # stable: the description stays first
    verdicts.sort(key=lambda v: v["at"])
    last_verdict = verdicts[-1] if verdicts else None
    with_links = [s for s in sources if s["links"]]
    result: Dict[str, Any] = {"link": None, "source": None, "serves": None, "domain": domain,
                              "all_links": [l for s in with_links for l in s["links"]], "last_verdict": last_verdict}
    if not with_links:
        result.update(action="none", reason="no review link in the description or comments")
        return result
    newest = with_links[-1]
    serves = newest["serves"]
    result.update(link=newest["links"][-1], source=newest["where"], serves=serves)
    if commit and serves and not same_commit(commit, serves):
        result.update(action="wait", reason="the link serves %s, not %s (the commit under test): its build hasn't landed"
                      % (serves[:7], commit[:7]))
        return result
    tested = commit or serves
    if last_verdict is None:
        result.update(action="test", reason="a review link and no QA verdict yet")
    elif newest["kind"] == "pasted" and newest["at"] > last_verdict["at"]:
        result.update(action="retest", reason="a review link was posted after the last QA verdict")
    elif last_verdict.get("link") != result["link"]:
        result.update(action="retest", reason="the last verdict tested %s, not the newest link"
                      % (last_verdict.get("link") or "no review link"))
    elif tested and last_verdict.get("commit") and not same_commit(tested, last_verdict["commit"]):
        result.update(action="retest", reason="the last verdict tested commit %s, not %s"
                      % (last_verdict["commit"], tested[:7]))
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


def concat_pages(out: str) -> List[Dict[str, Any]]:
    """--paginate prints one JSON array per page, back to back; decode them in turn,
    since a comment body can itself contain "][" and defeat splitting on it."""
    decoder, items, i = json.JSONDecoder(), [], 0
    while True:
        while i < len(out) and out[i].isspace():
            i += 1
        if i >= len(out):
            return items
        page, i = decoder.raw_decode(out, i)
        items += page


def fetch(repo: str, number: int) -> Dict[str, Any]:
    issue = json.loads(gh("api", "repos/%s/issues/%d" % (repo, number)))
    comments = concat_pages(gh("api", "--paginate", "repos/%s/issues/%d/comments?per_page=100" % (repo, number)))
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
                          "updated_at": c.get("updated_at", ""), "url": c.get("html_url", "")} for c in comments],
            "boards": boards}


def review_domain(repo: str, named: Optional[str]) -> str:
    """--domain, else the repo's Actions variable REVIEW_DOMAIN, else the placeholder."""
    domain = named
    if not domain:
        try:
            domain = json.loads(gh("api", "repos/%s/actions/variables/REVIEW_DOMAIN" % repo)).get("value")
        except (LinkError, ValueError):
            domain = None  # not set, or no permission to read variables
    domain = (domain or DEFAULT_DOMAIN).strip().lower().rstrip(".")
    if not DOMAIN_RE.match(domain):
        raise InputError("the review domain is a hostname like review.example.com, not %r" % domain)
    return domain


def pr_head(repo: str, number: int) -> str:
    return json.loads(gh("api", "repos/%s/pulls/%d" % (repo, number)))["head"]["sha"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--repo", help="owner/name; default: the current repository")
    parser.add_argument("--commit", help="the commit about to be tested; a different one than last time means retest")
    parser.add_argument("--pr", type=int, help="the PR under test; its head commit is the commit, unless --commit says")
    parser.add_argument("--domain", help="review domain (default: repo variable REVIEW_DOMAIN, else review.com)")
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="while the link serves an older commit, poll for up to this long")
    parser.add_argument("--local", action="store_true",
                        help="review links are paused: ignore them and decide on the commit alone")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo = current_repo(args.repo)
        domain = None if args.local else review_domain(repo, args.domain)
        commit = args.commit or (pr_head(repo, args.pr) if args.pr else None)
        deadline = time.time() + max(args.wait, 0)
        while True:
            ticket = fetch(repo, args.issue)
            decided = decide(ticket["body"], ticket["comments"], commit, domain or DEFAULT_DOMAIN, local=args.local)
            if decided["action"] != "wait" or time.time() >= deadline:
                break
            time.sleep(min(20, max(1, deadline - time.time())))
    except LinkError as exc:
        print("review_link: %s" % exc, file=sys.stderr)
        return exc.exit_code
    result = dict(decided, commit=commit, ticket="%s#%d" % (repo, args.issue), boards=ticket["boards"])
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("%s: %s — %s" % (result["ticket"], result["action"], result["reason"]))
        if result["link"]:
            print("review link: %s  (from %s)" % (result["link"], result["source"]))
            print("serves: %s" % (result["serves"] or "unknown (a pasted link): check it with preview_link.py"))
        for b in result["boards"]:
            print("board #%d %s: %s" % (b["number"], b["title"], b["status"] or "(no column)"))
    return 3 if result["action"] == "wait" and args.wait else 0


if __name__ == "__main__":
    sys.exit(main())
