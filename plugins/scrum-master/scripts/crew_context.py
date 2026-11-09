#!/usr/bin/env python3
"""SessionStart hook: point the session at the crew-workflow skill on a crew board.

A repository uses a crew board when a GitHub Projects board that is linked to
it, or that holds its recent issues, has the crew's Status columns (In approval
and QA). Only then does this print one line telling the session to follow the
crew-workflow skill. Everywhere else it prints nothing.

The answer is cached per repository for CACHE_TTL seconds, so most session
starts make no network call. Everything is best effort: no repository, no
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
CACHE_FILE = "crew_boards.json"
CREW_COLUMNS = ("in approval", "qa")
RECENT_ISSUES = 20

QUERY = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  projectsV2(first:20){nodes{%(board)s}}
  issues(last:%(recent)d){nodes{projectItems(first:5){nodes{project{%(board)s}}}}}}}""" % {
    "board": 'title closed field(name:"Status"){... on ProjectV2SingleSelectField{options{name}}}',
    "recent": RECENT_ISSUES,
}

REMOTE = re.compile(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


def _run(args: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def parse_remote(url: str) -> Optional[Tuple[str, str]]:
    """owner and name of a GitHub remote URL (https or ssh), else None."""
    match = REMOTE.search((url or "").strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def is_crew_board(board: Any) -> bool:
    """An open board whose Status field has every crew column."""
    if not isinstance(board, dict) or board.get("closed"):
        return False
    field = board.get("field") or {}
    names = {str(o.get("name", "")).strip().lower() for o in field.get("options") or [] if isinstance(o, dict)}
    return all(column in names for column in CREW_COLUMNS)


def candidate_boards(data: Any) -> Iterable[Dict[str, Any]]:
    """Linked boards first, then boards the recent issues sit on."""
    repo = ((data or {}).get("data") or {}).get("repository") or {}
    for board in (repo.get("projectsV2") or {}).get("nodes") or []:
        yield board
    for issue in (repo.get("issues") or {}).get("nodes") or []:
        for item in ((issue or {}).get("projectItems") or {}).get("nodes") or []:
            yield (item or {}).get("project") or {}


def crew_board(data: Any) -> Optional[str]:
    """Title of the first crew board in a query result, else None."""
    for board in candidate_boards(data):
        if is_crew_board(board):
            return str(board.get("title") or "").strip() or "(untitled)"
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
    if not isinstance(entry, dict) or now - float(entry.get("at", 0)) > CACHE_TTL:
        return False, None
    return True, entry.get("board")


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
    """(answered, board title or None). Not answered means gh failed: don't cache."""
    raw = _run([
        "gh", "api", "graphql", "-f", "query=" + QUERY, "-F", "owner=" + owner, "-F", "name=" + name,
    ])
    if raw is None:
        return False, None
    try:
        data = json.loads(raw)
    except ValueError:
        return False, None
    if not isinstance(data, dict) or data.get("errors") or not (data.get("data") or {}).get("repository"):
        return False, None
    return True, crew_board(data)


def message(board: str, repo: str) -> str:
    return (
        'crew board "%s" is used by %s. For ticket work ("do ticket #N", "pick up the next issue"), '
        "follow the crew-workflow skill: every step through its crew command, every ticket or board "
        "write shown first, stop at In approval and Ready for Merge." % (board, repo)
    )


def main() -> int:
    try:
        sys.stdin.read()
    except Exception:
        pass

    remote = _run(["git", "remote", "get-url", "origin"])
    parsed = parse_remote(remote or "")
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
