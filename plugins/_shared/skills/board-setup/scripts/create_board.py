#!/usr/bin/env python3
"""Create a GitHub Projects (v2) board for this repository, with the team's columns.

    create_board.py --title "Agent Run Observatory" [--columns "Backlog,Ready,In progress,In review,Done"]
                    (default: In Definition, Backlog, Ready, In progress, In review, Ready for Merge, Done)
                    [--no-link] [--dry-run]

Creates the board under the repository's owner (a user or an organization),
links it to the repository unless --no-link, and replaces the default Status
options with the columns given. Refuses if an open board with the same title
already exists, so a rerun never makes a second one.

A new board starts with the columns Todo, In Progress and Done, and its
built-in workflows (item closed and pull request merged -> Done, item added ->
Todo, ...) point at them. Give a column a new id and GitHub switches off every
workflow that targeted it, and its API cannot switch one back on. So each
starting column keeps its id and becomes a column of the new board (Todo ->
Backlog, In Progress -> In progress, Done -> Done; see keep_starting), and the
workflows are read back and any that are off reported.

Goes through the createProjectV2 and updateProjectV2Field GraphQL mutations,
because older gh versions have no `gh project`. The token needs the `project`
scope. The gh plumbing is the ticket-management skill's board.py. Both are
shared skills (plugins/_shared/skills), so board.py sits beside this skill in
the repository and in every plugin bundle that lists both.

Exit status: 0 done, 1 GitHub refused, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILLS = Path(__file__).resolve().parent.parent.parent
# ticket-management sits beside this skill: in plugins/_shared/skills, and in a built bundle's skills/.
sys.path.insert(0, str(SKILLS / "ticket-management" / "scripts"))
try:
    from board import BoardError, InputError, current_repo, graphql  # noqa: E402
except ImportError:  # the plugin was built without its shared skill
    sys.exit("create_board: ticket-management/scripts/board.py is missing beside this skill; "
             "list both board-setup and ticket-management in the plugin's shared_skills")

# In Definition holds the notes plugin's optional items; Ready for Merge holds what passed QA.
DEFAULT_COLUMNS = ["In Definition", "Backlog", "Ready", "In progress", "In review", "Ready for Merge", "Done"]
NAME_MAX = 50
# Colors by meaning, so a board reads the same at a glance whatever it is called.
KNOWN = {
    "in definition": ("GRAY", "Not yet understood well enough to refine"),
    "backlog": ("GRAY", "Refined or waiting to be"),
    "ready": ("BLUE", "Meets the Definition of Ready; can be planned"),
    "in progress": ("YELLOW", "Being worked on"),
    "in review": ("PURPLE", "Pull request open, waiting for review"),
    "ready for merge": ("ORANGE", "Passed QA; waiting to be merged"),
    "blocked": ("RED", "Cannot move until something outside it changes"),
    "done": ("GREEN", "Merged or otherwise finished"),
}


# --- pure helpers (unit-tested) ---------------------------------------------


def parse_columns(text: Optional[str]) -> List[str]:
    if text is None:
        return list(DEFAULT_COLUMNS)
    columns = [part.strip() for part in text.split(",")]
    if any(not c for c in columns):
        raise InputError("empty column name in %r" % text)
    lowered = [c.lower() for c in columns]
    dupes = sorted({c for c in columns if lowered.count(c.lower()) > 1})
    if dupes:
        raise InputError("duplicate columns: %s" % ", ".join(dupes))
    long = [c for c in columns if len(c) > NAME_MAX]
    if long:
        raise InputError("column names must be at most %d characters: %s" % (NAME_MAX, ", ".join(long)))
    if len(columns) < 2:
        raise InputError("a board needs at least two columns")
    return columns


# GitHub's starting columns, and the names on the new board each one becomes, first match wins.
# With none of them, Todo becomes the first column and Done the last, so their workflows stay on.
STARTING = {"Done": ("done", "completed", "closed"), "Todo": ("backlog", "todo", "to do"),
            "In Progress": ("in progress", "doing", "wip")}
FALLBACK = {"Done": -1, "Todo": 0}


def keep_starting(columns: List[str], starting: Optional[List[str]] = None) -> Dict[str, str]:
    """Which new column each of GitHub's starting columns becomes, keeping its id: {starting: new column}."""
    lowered = [c.lower() for c in columns]
    kept: Dict[str, str] = {}
    for start in [s for s in STARTING if starting is None or s in starting]:
        free = [c for c in columns if c not in kept.values()]
        hit = next((columns[lowered.index(a)] for a in STARTING[start]
                    if a in lowered and columns[lowered.index(a)] in free), None)
        if hit is None and start in FALLBACK and columns[FALLBACK[start]] in free:
            hit = columns[FALLBACK[start]]
        if hit:
            kept[start] = hit
    return kept


def column_options(columns: List[str]) -> List[Dict[str, str]]:
    options = []
    for name in columns:
        color, description = KNOWN.get(name.lower(), ("GRAY", ""))
        options.append({"name": name, "color": color, "description": description})
    return options


def find_duplicate(boards: List[Dict[str, Any]], title: str) -> Optional[Dict[str, Any]]:
    for b in boards:
        if not b.get("closed") and b["title"].strip().lower() == title.strip().lower():
            return b
    return None


# --- GitHub ------------------------------------------------------------------


def owner_and_repo(repo: Dict[str, str]) -> Dict[str, Any]:
    nodes = "projectsV2(first:100){nodes{number title url closed}}"
    data = graphql(
        """query($o:String!,$n:String!){repository(owner:$o,name:$n){id}
          repositoryOwner(login:$o){id ... on User{%s} ... on Organization{%s}}}""" % (nodes, nodes),
        o=repo["owner"], n=repo["name"],
    )
    owner = data["repositoryOwner"]
    return {"owner_id": owner["id"], "repo_id": data["repository"]["id"],
            "boards": (owner.get("projectsV2") or {}).get("nodes", [])}


def create(title: str, columns: List[str], link: bool) -> Dict[str, Any]:
    repo = current_repo()
    ids = owner_and_repo(repo)
    dup = find_duplicate(ids["boards"], title)
    if dup:
        raise InputError("an open board named %r already exists: #%d %s" % (dup["title"], dup["number"], dup["url"]))
    made = graphql(
        """mutation($owner:ID!,$title:String!%s){createProjectV2(input:{ownerId:$owner,title:$title%s}){
          projectV2{id number url field(name:"Status"){... on ProjectV2SingleSelectField{id options{id name}}}}}}"""
        % ((",$repo:ID!", ",repositoryId:$repo") if link else ("", "")),
        **dict({"owner": ids["owner_id"], "title": title}, **({"repo": ids["repo_id"]} if link else {})),
    )["createProjectV2"]["projectV2"]
    if not made.get("field"):
        raise BoardError("board #%d was created but has no Status field to set columns on: %s"
                         % (made["number"], made["url"]))
    starting = {o["name"]: o["id"] for o in made["field"]["options"]}
    kept = keep_starting(columns, list(starting))
    ids = {column: starting[start] for start, column in kept.items()}
    options = column_options(columns)
    literal = ",".join(
        '{%s}' % ",".join((["id:%s" % json.dumps(ids[o["name"]])] if o["name"] in ids else [])
                          + ["name:%s" % json.dumps(o["name"]), "color:%s" % o["color"],
                             "description:%s" % json.dumps(o["description"])])
        for o in options
    )
    graphql(
        "mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:[%s]}){clientMutationId}}" % literal,
        f=made["field"]["id"],
    )
    check = graphql(
        """query($id:ID!){node(id:$id){... on ProjectV2{field(name:"Status"){
          ... on ProjectV2SingleSelectField{options{name}}} workflows(first:20){nodes{name enabled}}}}}""",
        id=made["id"],
    )
    got = [o["name"] for o in check["node"]["field"]["options"]]
    if got != columns:
        raise BoardError("board #%d created, but its columns read back as %s, not %s: %s"
                         % (made["number"], got, columns, made["url"]))
    workflows = {w["name"]: w["enabled"] for w in check["node"]["workflows"]["nodes"]}
    result = {"number": made["number"], "url": made["url"], "title": title, "columns": got,
              "linked": "%s/%s" % (repo["owner"], repo["name"]) if link else None,
              "kept_from_github": kept, "workflows": workflows}
    off = sorted(name for name, on in workflows.items() if not on)
    if off:
        result["workflows_off"] = off
        result["to_do"] = ("GitHub's API cannot turn a workflow on. Ask the user to open %s, then ... -> "
                           "Workflows, and enable: %s" % (made["url"], ", ".join(off)))
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--title", required=True)
    parser.add_argument("--columns", help="comma-separated, in order (default: %s)" % ", ".join(DEFAULT_COLUMNS))
    parser.add_argument("--no-link", action="store_true", help="do not link the board to this repository")
    parser.add_argument("--dry-run", action="store_true", help="print what would be created")
    args = parser.parse_args(argv)
    try:
        title = args.title.strip()
        if not title:
            raise InputError("the board needs a title")
        columns = parse_columns(args.columns)
        if args.dry_run:
            result: Dict[str, Any] = {"dry_run": True, "title": title, "columns": column_options(columns),
                                      "link": not args.no_link, "keeps_from_github": keep_starting(columns)}
        else:
            result = create(title, columns, link=not args.no_link)
        print(json.dumps(result, indent=2))
    except BoardError as exc:
        print("create_board: %s" % exc, file=sys.stderr)
        return 2 if isinstance(exc, InputError) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
