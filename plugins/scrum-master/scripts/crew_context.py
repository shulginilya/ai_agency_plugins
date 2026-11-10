#!/usr/bin/env python3
"""SessionStart hook: point the session at the crew-workflow skill on a crew board.

A repository uses a crew board when a GitHub Projects board has the crew's
Status columns (In approval and QA) and is either linked to the repository or
owned by the repository's owner and holding one of its recent issues. A board
someone else owns is ignored even when it holds the repository's issues:
anyone can put a public issue on their own board and choose its title.

Only on a crew board does this print one line telling the session to follow
the crew-workflow skill. Everywhere else it prints nothing.

A found board is cached per repository for CACHE_TTL seconds; "no crew board"
only for NEGATIVE_TTL, so a board created with /scrum-master:create-board is
picked up by the next sessions. Everything is best effort: no repository, no
GitHub remote, no gh, no authentication, offline or slow all mean it prints
nothing and caches nothing. Exit status is always 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TIMEOUT = 5
CACHE_TTL = 12 * 3600
NEGATIVE_TTL = 10 * 60
CACHE_FILE = "crew_boards.json"
CREW_COLUMNS = ("in approval", "qa")
RECENT_ISSUES = 20
TITLE_MAX = 80

BOARD_FIELDS = (
    'title closed owner{... on User{login} ... on Organization{login}} '
    'field(name:"Status"){... on ProjectV2SingleSelectField{options{name}}}'
)
QUERY = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  projectsV2(first:20){nodes{%(board)s}}
  issues(last:%(recent)d){nodes{projectItems(first:5){nodes{project{%(board)s}}}}}}}""" % {
    "board": BOARD_FIELDS,
    "recent": RECENT_ISSUES,
}

REMOTE = re.compile(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
NAME_WITH_OWNER = re.compile(r"^([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)$")


def _run(args: List[str], keep_output_on_error: bool = False) -> Optional[str]:
    """stdout of a command, or None when it can't run, times out or fails.

    keep_output_on_error returns stdout of a failed command too: `gh api`
    prints the GraphQL error body there, and it may carry partial data.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 and not keep_output_on_error:
        return None
    return result.stdout


def parse_remote(url: str) -> Optional[Tuple[str, str]]:
    """owner and name of a GitHub remote URL (https or ssh), else None."""
    match = REMOTE.search((url or "").strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def current_repo() -> Optional[Tuple[str, str]]:
    """owner and name of origin; asks gh when origin uses an SSH host alias."""
    remote = _run(["git", "remote", "get-url", "origin"])
    if remote is None:
        return None
    parsed = parse_remote(remote)
    if parsed:
        return parsed
    # e.g. git@github-work:acme/shop.git through ~/.ssh/config. gh resolves the
    # alias locally, and fails fast when origin is not GitHub at all.
    match = NAME_WITH_OWNER.match(
        (_run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]) or "").strip()
    )
    return (match.group(1), match.group(2)) if match else None


def is_crew_board(board: Any) -> bool:
    """An open board whose Status field has every crew column."""
    if not isinstance(board, dict) or board.get("closed"):
        return False
    field = board.get("field") or {}
    names = {str(o.get("name", "")).strip().lower() for o in field.get("options") or [] if isinstance(o, dict)}
    return all(column in names for column in CREW_COLUMNS)


def _owner(board: Dict[str, Any]) -> str:
    return str((board.get("owner") or {}).get("login") or "").lower()


def candidate_boards(data: Any, owner: str) -> Iterable[Dict[str, Any]]:
    """Boards linked to the repo, then the repo owner's boards holding its recent issues."""
    repo = ((data or {}).get("data") or {}).get("repository") or {}
    for board in (repo.get("projectsV2") or {}).get("nodes") or []:
        if isinstance(board, dict):
            yield board
    for issue in (repo.get("issues") or {}).get("nodes") or []:
        for item in ((issue or {}).get("projectItems") or {}).get("nodes") or []:
            board = (item or {}).get("project")
            if isinstance(board, dict) and _owner(board) == owner.lower():
                yield board


def clean_title(title: Any) -> str:
    """A board title safe to print: printable, no quotes or backticks, one line, capped."""
    text = "".join(c for c in str(title or "") if c.isprintable() and c not in "\"'`")
    text = " ".join(text.split())
    if len(text) > TITLE_MAX:
        text = text[: TITLE_MAX - 3].rstrip() + "..."
    return text or "(untitled)"


def crew_board(data: Any, owner: str) -> Optional[str]:
    """Cleaned title of the first crew board in a query result, else None."""
    for board in candidate_boards(data, owner):
        if is_crew_board(board):
            return clean_title(board.get("title"))
    return None


def cache_path() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
        "ai-agency-plugins",
    )
    return Path(root) / CACHE_FILE


def read_cache(path: Path, repo: str, now: float) -> Tuple[bool, Optional[str]]:
    """(hit, board title or None) for a fresh entry; (False, None) otherwise."""
    try:
        entry = json.loads(path.read_text(encoding="utf-8")).get(repo)
    except (OSError, ValueError, AttributeError):
        return False, None
    if not isinstance(entry, dict):
        return False, None
    board = entry.get("board")
    ttl = CACHE_TTL if board else NEGATIVE_TTL
    try:
        age = now - float(entry.get("at", 0))
    except (TypeError, ValueError):
        return False, None
    if age < 0 or age > ttl:
        return False, None
    return True, clean_title(board) if board else None


def write_cache(path: Path, repo: str, board: Optional[str], now: float) -> None:
    try:
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, ValueError):
            cache = {}
        cache[repo] = {"at": now, "board": board}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass


def lookup(owner: str, name: str) -> Tuple[bool, Optional[str]]:
    """(answered, board title or None). Not answered means no usable reply: don't cache.

    A reply with errors still counts when it carries the repository: GitHub
    returns partial data when one nested project can't be read, and the crew
    board may be in what did come back.
    """
    raw = _run(
        ["gh", "api", "graphql", "-f", "query=" + QUERY, "-f", "owner=" + owner, "-f", "name=" + name],
        keep_output_on_error=True,
    )
    if not raw:
        return False, None
    try:
        data = json.loads(raw)
    except ValueError:
        return False, None
    if not isinstance(data, dict) or not (data.get("data") or {}).get("repository"):
        return False, None
    return True, crew_board(data, owner)


def message(board: str, repo: str) -> str:
    return (
        'crew board "%s" is used by %s. For ticket work ("do ticket #N", "pick up the next issue"), '
        "follow the crew-workflow skill: every step through its crew command, every ticket or board "
        "write shown first, stop at In approval and Ready for Merge." % (clean_title(board), repo)
    )


def main() -> int:
    try:
        sys.stdin.read()
    except Exception:
        pass

    parsed = current_repo()
    if not parsed:
        return 0
    owner, name = parsed
    repo = "%s/%s" % (owner, name)

    now = time.time()
    path = cache_path()
    hit, board = read_cache(path, repo, now)
    if not hit:
        answered, board = lookup(owner, name)
        if not answered:
            return 0
        write_cache(path, repo, board, now)
    if board:
        print(message(board, repo))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
