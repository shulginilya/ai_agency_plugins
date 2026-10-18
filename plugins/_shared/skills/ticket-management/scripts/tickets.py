#!/usr/bin/env python3
"""GitHub issue lifecycle for the crew: create, batch, edit, close, delete.

    tickets.py create --title T --body-file F [--label L ...] [--assignee @me] [--create-missing-labels] [--project N [--status S]] [--skip-existing]
    tickets.py batch  --plan plan.json [--project N] [--status Backlog] [--assignee @me] [--dry-run]
    tickets.py edit   --issue 12 [--title T] [--body-file F] [--add-label L ...] [--remove-label L ...]
    tickets.py close  --issue 12 [--reason completed|not-planned] [--comment C]
    tickets.py delete --issue 12 --confirm 12

`batch` reads a plan file and is safe to rerun: an issue whose title already
exists in the repository (open or closed) is reported and skipped, never
created twice, so a run that fails halfway is finished by running it again.
A plan item may name a `parent` (another item's `key`): the child is linked as
a sub-issue of that epic, or, where the repository has no sub-issues, listed in
the epic's body as a task-list line. A plan item may also name `assignees`
(logins, or `@me`); `--assignee` assigns every item the plan does not.

`delete` cannot be undone on GitHub, so it refuses unless `--confirm` repeats
the issue number. Closing as not planned keeps the history and is the default
way to drop a ticket.

Board steps (`--project`, `--status`) reuse board.py, which sits beside this
file. Standard library only; needs an authenticated `gh`.
Exit status: 0 done, 1 GitHub refused, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board  # noqa: E402  (the shared gh/GraphQL plumbing lives there)
from board import BoardError, InputError, gh, graphql  # noqa: E402

PLAN_KEYS = {"key", "title", "body", "labels", "parent", "assignees"}
CLOSE_REASONS = {"completed": "completed", "not-planned": "not_planned"}


# --- pure helpers (unit-tested) ---------------------------------------------


def load_plan(data: Any) -> List[Dict[str, Any]]:
    """Validate a plan: {"issues": [{"key", "title", "body", "labels"?, "parent"?}, ...]}.

    Parents must appear before their children, so the plan can be created in
    one pass and every link points at an issue that already exists.
    """
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list) or not data["issues"]:
        raise InputError('the plan must be {"issues": [...]} with at least one issue')
    seen: Dict[str, int] = {}
    titles = set()
    items = []
    for index, raw in enumerate(data["issues"], 1):
        where = "issue %d" % index
        if not isinstance(raw, dict):
            raise InputError("%s is not an object" % where)
        unknown = set(raw) - PLAN_KEYS
        if unknown:
            raise InputError("%s has unknown keys: %s" % (where, ", ".join(sorted(unknown))))
        key = str(raw.get("key") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not key or not title:
            raise InputError("%s needs a key and a title" % where)
        if key in seen:
            raise InputError("%s reuses key %r (first used by issue %d)" % (where, key, seen[key]))
        if title in titles:
            raise InputError("%s repeats the title %r" % (where, title))
        parent = raw.get("parent")
        if parent is not None and parent not in seen:
            raise InputError("%s names parent %r, which must be an earlier issue in the plan" % (where, parent))
        labels = raw.get("labels") or []
        if not isinstance(labels, list) or not all(isinstance(l, str) for l in labels):
            raise InputError("%s: labels must be a list of strings" % where)
        assignees = raw.get("assignees") or []
        if not isinstance(assignees, list) or not all(isinstance(a, str) and a.strip() for a in assignees):
            raise InputError("%s: assignees must be a list of logins (or \"@me\")" % where)
        seen[key] = index
        titles.add(title)
        items.append({"key": key, "title": title, "body": str(raw.get("body") or ""),
                      "labels": labels, "parent": parent, "assignees": assignees})
    return items


def plan_actions(items: List[Dict[str, Any]], existing: Dict[str, int]) -> List[Dict[str, Any]]:
    """Mark each plan item `create` or `exists` (with its number), by exact title."""
    actions = []
    for item in items:
        number = existing.get(item["title"])
        actions.append(dict(item, action="exists" if number else "create", number=number))
    return actions


def check_delete(issue: int, confirm: Optional[int]) -> None:
    if confirm != issue:
        raise InputError(
            "refusing to delete #%d: deleting cannot be undone. Repeat the number with --confirm %d, "
            "or close it as not planned instead" % (issue, issue)
        )


# --- gh plumbing -------------------------------------------------------------


def existing_titles() -> Dict[str, int]:
    out = gh("issue", "list", "--state", "all", "--limit", "1000", "--json", "number,title")
    return {row["title"]: row["number"] for row in json.loads(out)}


LABEL_COLOR = "1d76db"


def ensure_labels(labels: List[str]) -> List[str]:
    """Create any label the repository lacks, so `gh issue create --label` cannot refuse it."""
    repo = board.current_repo()
    created = []
    for label in labels:
        path = "repos/%s/%s/labels/%s" % (repo["owner"], repo["name"], urllib.parse.quote(label, safe=""))
        try:
            gh("api", path)
        except BoardError as exc:
            if "Not Found" not in str(exc) and "404" not in str(exc):
                raise
            gh("api", "-X", "POST", "repos/%s/%s/labels" % (repo["owner"], repo["name"]),
               "-f", "name=%s" % label, "-f", "color=%s" % LABEL_COLOR)
            created.append(label)
    return created


def create_issue(title: str, body: str, labels: List[str], assignees: Optional[List[str]] = None) -> Dict[str, Any]:
    args = ["issue", "create", "--title", title, "--body", body or " "]
    for label in labels:
        args += ["--label", label]
    for login in assignees or []:
        args += ["--assignee", login]
    url = gh(*args).strip().splitlines()[-1]
    return {"number": int(url.rstrip("/").rsplit("/", 1)[-1]), "url": url}


def place_on_board(project: Optional[int], status: Optional[str], number: int) -> Optional[Dict[str, Any]]:
    if project is None:
        return None
    placed = board.cmd_add(argparse.Namespace(project=project, issue=number))
    if status:
        moved = board.cmd_move(argparse.Namespace(project=project, issue=number, status=status,
                                                  attempts=3, settle=2.0))
        placed["status"] = moved["status"]
    return placed


def link_child(parent: int, child: int) -> str:
    """Make `child` a sub-issue of `parent`; fall back to a task-list line in the parent's body."""
    repo = board.current_repo()
    ids = graphql(
        """query($o:String!,$n:String!,$p:Int!,$c:Int!){repository(owner:$o,name:$n){
          p:issue(number:$p){id body} c:issue(number:$c){id}}}""",
        o=repo["owner"], n=repo["name"], p=parent, c=child,
    )["repository"]
    try:
        graphql("mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}",
                p=ids["p"]["id"], c=ids["c"]["id"])
        return "sub-issue"
    except BoardError:
        line = "- [ ] #%d" % child
        body = ids["p"]["body"] or ""
        if line not in body:
            gh("issue", "edit", str(parent), "--body", (body.rstrip() + "\n" + line).strip() + "\n")
        return "task-list"


# --- commands ----------------------------------------------------------------


def read_body(args: argparse.Namespace) -> Optional[str]:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    return getattr(args, "body", None)


def cmd_create(args: argparse.Namespace) -> Dict[str, Any]:
    if args.skip_existing:
        number = existing_titles().get(args.title)
        if number:
            return {"number": number, "created": False, "board": place_on_board(args.project, args.status, number)}
    created_labels = ensure_labels(args.label or []) if args.create_missing_labels else []
    made = create_issue(args.title, read_body(args) or "", args.label or [], args.assignee or [])
    made["created"] = True
    if created_labels:
        made["labels_created"] = created_labels
    made["board"] = place_on_board(args.project, args.status, made["number"])
    return made


def cmd_batch(args: argparse.Namespace) -> Dict[str, Any]:
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError("cannot read plan %s: %s" % (args.plan, exc))
    actions = plan_actions(load_plan(plan), existing_titles())
    if args.dry_run:
        return {"dry_run": True, "issues": [{k: a[k] for k in ("key", "title", "action", "number", "parent")}
                                            for a in actions]}
    numbers: Dict[str, int] = {}
    report = []
    for item in actions:
        if item["action"] == "create":
            assignees = item["assignees"] or ([args.assignee] if args.assignee else [])
            item["number"] = create_issue(item["title"], item["body"], item["labels"], assignees)["number"]
        numbers[item["key"]] = item["number"]
        entry = {"key": item["key"], "number": item["number"], "title": item["title"],
                 "created": item["action"] == "create"}
        if item["parent"]:
            entry["linked"] = link_child(numbers[item["parent"]], item["number"])
        placed = place_on_board(args.project, args.status, item["number"])
        if placed:
            entry["status"] = placed.get("status")
        report.append(entry)
    created = sum(1 for e in report if e["created"])
    return {"created": created, "skipped": len(report) - created, "issues": report}


def cmd_edit(args: argparse.Namespace) -> Dict[str, Any]:
    edit = ["issue", "edit", str(args.issue)]
    if args.title:
        edit += ["--title", args.title]
    body = read_body(args)
    if body is not None:
        edit += ["--body", body]
    for label in args.add_label or []:
        edit += ["--add-label", label]
    for label in args.remove_label or []:
        edit += ["--remove-label", label]
    if len(edit) == 3:
        raise InputError("nothing to edit: pass --title, --body-file, --add-label or --remove-label")
    gh(*edit)
    return {"number": args.issue, "edited": True}


def cmd_close(args: argparse.Namespace) -> Dict[str, Any]:
    repo = board.current_repo()
    if args.comment:
        gh("issue", "comment", str(args.issue), "--body", args.comment)
    gh("api", "-X", "PATCH", "repos/%s/%s/issues/%d" % (repo["owner"], repo["name"], args.issue),
       "-f", "state=closed", "-f", "state_reason=%s" % CLOSE_REASONS[args.reason])
    return {"number": args.issue, "closed": True, "reason": args.reason}


def cmd_delete(args: argparse.Namespace) -> Dict[str, Any]:
    check_delete(args.issue, args.confirm)
    repo = board.current_repo()
    issue_id = graphql(
        "query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n){issue(number:$i){id}}}",
        o=repo["owner"], n=repo["name"], i=args.issue,
    )["repository"]["issue"]
    if not issue_id:
        raise BoardError("issue #%d not found" % args.issue)
    graphql("mutation($i:ID!){deleteIssue(input:{issueId:$i}){clientMutationId}}", i=issue_id["id"])
    return {"number": args.issue, "deleted": True}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create", help="create one issue")
    p.add_argument("--title", required=True)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--body-file")
    group.add_argument("--body")
    p.add_argument("--label", action="append")
    p.add_argument("--assignee", action="append", help="login, or @me; repeat for several")
    p.add_argument("--project", type=int, help="also put it on this board")
    p.add_argument("--status", help="board column, with --project")
    p.add_argument("--skip-existing", action="store_true", help="reuse an issue with the same title")
    p.add_argument("--create-missing-labels", action="store_true", help="create any --label the repo lacks")

    p = sub.add_parser("batch", help="create a backlog from a plan file; safe to rerun")
    p.add_argument("--plan", required=True)
    p.add_argument("--project", type=int)
    p.add_argument("--assignee", help="login, or @me, for every item that names no assignees")
    p.add_argument("--status", default=None)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("edit", help="change title, body or labels")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--title")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--body-file")
    group.add_argument("--body")
    p.add_argument("--add-label", action="append")
    p.add_argument("--remove-label", action="append")

    p = sub.add_parser("close", help="close as completed or not planned")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--reason", choices=sorted(CLOSE_REASONS), default="completed")
    p.add_argument("--comment")

    p = sub.add_parser("delete", help="delete permanently; needs --confirm <same number>")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--confirm", type=int)

    args = parser.parse_args(argv)
    if getattr(args, "status", None) and getattr(args, "project", None) is None:
        print("tickets: --status needs --project", file=sys.stderr)
        return 2
    handlers = {"create": cmd_create, "batch": cmd_batch, "edit": cmd_edit,
                "close": cmd_close, "delete": cmd_delete}
    try:
        print(json.dumps(handlers[args.cmd](args), indent=2))
    except BoardError as exc:
        print("tickets: %s" % exc, file=sys.stderr)
        return 2 if isinstance(exc, InputError) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
