#!/usr/bin/env python3
"""Find the review link of a pull request: its preview deployment, read back from GitHub.

    preview_link.py --pr 42                      the preview URL of PR 42's head commit
    preview_link.py --pr 42 --wait 600           poll until it is up (or failed), at most 600 s
    preview_link.py --pr 42 --check              also GET the URL and report the HTTP status
    preview_link.py --pr 42 --repo owner/name --json

Every preview, whatever hosts it, ends as a GitHub Deployment whose latest
status carries `environment_url`: the devops preview workflow creates one for
environment `preview-pr-<N>`, and Render creates its own for each PR preview.
So the link is looked up through the Deployments API, never scraped from a
comment, and it is only "current" when it was deployed from the PR's head
commit. A preview of an older commit is reported as stale, not as the link.

Standard library only; needs an authenticated `gh` (any version with `gh api`).
Exit status: 0 a current preview (and, with --check, it answered 2xx/3xx);
1 no current preview: none, stale, pending, failed or unreachable; 2 bad input
or gh failed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

POLL_SECONDS = 15
ACTIVE = ("pending", "queued", "in_progress")
PRODUCTION = ("production", "prod", "github-pages")


class LinkError(Exception):
    pass


# --- pure helpers (unit-tested) ---------------------------------------------


def environment_for(pr: int) -> str:
    return "preview-pr-%d" % pr


def is_preview(deployment: Dict[str, Any], pr: int) -> bool:
    """A deployment that previews this PR, not a production one that happens to share the commit."""
    env = (deployment.get("environment") or "").strip().lower()
    if env == environment_for(pr):
        return True
    if env in PRODUCTION or deployment.get("production_environment"):
        return False
    return True


def choose(pr: Dict[str, Any], deployments: List[Dict[str, Any]],
           statuses: Dict[int, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Name the PR's preview from its deployments (newest first) and each one's latest status.

    Returns {"state": current|stale|pending|failed|none, "url", "environment", "sha", "reason"}.
    """
    head = pr["head_sha"]
    number = pr["number"]
    previews = [d for d in deployments if is_preview(d, number)]
    previews.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    for_head = [d for d in previews if d.get("sha") == head]

    def found(state: str, d: Dict[str, Any], status: Optional[Dict[str, Any]], reason: str) -> Dict[str, Any]:
        return {"state": state, "url": (status or {}).get("environment_url") or None,
                "environment": d.get("environment"), "sha": d.get("sha"), "deployment": d.get("id"),
                "reason": reason}

    for d in for_head:
        status = statuses.get(d["id"])
        if status and status.get("state") == "success" and status.get("environment_url"):
            return found("current", d, status, "deployed from the head commit %s" % head[:7])
    for d in for_head:
        status = statuses.get(d["id"])
        state = (status or {}).get("state") or "pending"
        if state in ACTIVE:
            return found("pending", d, status, "the head commit %s is still deploying (%s)" % (head[:7], state))
    for d in for_head:
        status = statuses.get(d["id"])
        if status and status.get("state") in ("failure", "error"):
            reason = "the deploy of %s failed" % head[:7]
            if status.get("description"):
                reason += ": %s" % status["description"]
            if status.get("log_url"):
                reason += " (log: %s)" % status["log_url"]
            return found("failed", d, status, reason)
    for d in previews:
        status = statuses.get(d["id"])
        if status and status.get("state") == "success" and status.get("environment_url"):
            return found("stale", d, status, "the only live preview is of %s, not the head commit %s"
                         % ((d.get("sha") or "?")[:7], head[:7]))
    if pr.get("state") != "open":
        reason = "the PR is %s, so its preview has been taken down" % pr.get("state")
    elif previews:
        reason = "its preview deployments are all inactive"
    else:
        reason = ("no deployment for this PR: the repo has no preview workflow, it was skipped "
                  "(a fork PR gets no secrets), or it has not started yet")
    return {"state": "none", "url": None, "environment": None, "sha": None, "deployment": None,
            "reason": reason}


# --- gh plumbing -------------------------------------------------------------


def gh_json(path: str) -> Any:
    try:
        out = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                             capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise LinkError("gh is not installed")
    if out.returncode != 0:
        raise LinkError("gh api %s: %s" % (path, (out.stderr or out.stdout).strip()))
    return json.loads(out.stdout or "null")


def current_repo() -> str:
    out = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0 or not out.stdout.strip():
        raise LinkError("cannot tell the repository; pass --repo owner/name")
    return out.stdout.strip()


def look_up(repo: str, number: int) -> Dict[str, Any]:
    pull = gh_json("repos/%s/pulls/%d" % (repo, number))
    pr = {"number": number, "head_sha": pull["head"]["sha"], "head_ref": pull["head"]["ref"],
          "state": "merged" if pull.get("merged_at") else pull["state"]}
    seen: Dict[int, Dict[str, Any]] = {}
    for query in ("sha=%s" % pr["head_sha"], "environment=%s" % environment_for(number),
                  "ref=%s" % pr["head_ref"]):
        for d in gh_json("repos/%s/deployments?%s&per_page=30" % (repo, query)) or []:
            seen.setdefault(d["id"], d)
    statuses: Dict[int, Optional[Dict[str, Any]]] = {}
    for d in seen.values():
        latest = gh_json("repos/%s/deployments/%d/statuses?per_page=1" % (repo, d["id"])) or []
        statuses[d["id"]] = latest[0] if latest else None
    result = choose(pr, list(seen.values()), statuses)
    result.update({"repo": repo, "pr": number, "head_sha": pr["head_sha"]})
    return result


def http_status(url: str, timeout: float = 20.0) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "preview-link"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"status": response.status, "ok": 200 <= response.status < 400}
    except urllib.error.HTTPError as err:
        return {"status": err.code, "ok": False}
    except (urllib.error.URLError, OSError) as err:
        return {"status": None, "ok": False, "error": str(getattr(err, "reason", err))}


# --- CLI ---------------------------------------------------------------------


def render(result: Dict[str, Any]) -> str:
    lines = ["PR #%s preview: %s" % (result["pr"], result["state"].upper())]
    if result.get("url"):
        lines.append("URL:    %s" % result["url"])
    if result.get("environment"):
        lines.append("Env:    %s (commit %s)" % (result["environment"], (result.get("sha") or "?")[:7]))
    lines.append("Why:    %s" % result["reason"])
    if "http" in result:
        http = result["http"]
        lines.append("HTTP:   %s" % (http["status"] if http["status"] else http.get("error", "no answer")))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="pull request number")
    parser.add_argument("--repo", help="owner/name; defaults to the current repository")
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="poll until the head commit's preview is up or has failed")
    parser.add_argument("--check", action="store_true", help="GET the URL and report the HTTP status")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo = args.repo or current_repo()
        deadline = time.monotonic() + max(args.wait, 0)
        result = look_up(repo, args.pr)
        while result["state"] in ("pending", "none", "stale") and time.monotonic() < deadline:
            time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))
            result = look_up(repo, args.pr)
    except LinkError as err:
        print("preview_link: %s" % err, file=sys.stderr)
        return 2
    code = 0 if result["state"] == "current" else 1
    if args.check and result.get("url"):
        result["http"] = http_status(result["url"])
        if not result["http"]["ok"]:
            code = 1
    print(json.dumps(result, indent=2) if args.json else render(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
