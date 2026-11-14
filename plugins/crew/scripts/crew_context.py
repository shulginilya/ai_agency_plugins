#!/usr/bin/env python3
"""Crew hook: point the session at the crew-workflow skill, and start QA on cards moved to QA.

SessionStart and UserPromptSubmit both run it; the event name comes on stdin.

A repository uses a crew board when a GitHub Projects board has the crew's
Status columns (In approval and QA) and is either linked to the repository or
owned by the repository's owner and holding one of its recent issues. A board
someone else owns is ignored even when it holds the repository's issues:
anyone can put a public issue on their own board and choose its title.

In a GitHub repository:

- with a crew board, it prints one line telling the session to follow the
  crew-workflow skill;
- without one, it tells the session to ask the Captain, in its first reply,
  whether to create a crew board and what to call it. On a yes the session
  runs /crew:create-board and follows crew-workflow; on a no it runs
  this script with --decline, and this repository is never asked about again
  (--forget undoes that). A crew board found later is announced either way.

Anywhere else (no repository, no GitHub remote) it prints nothing. A session
nobody is watching never gets the question, since no one would answer it: any
run with CREW_UNATTENDED=1, such as a scripted `claude -p`. It still gets the
crew-board line.

On a crew board it also reports the repository's open tickets whose card was
moved to QA, so the session runs /qa:verify on them without asking: the Captain
moving a card from In approval to QA is what starts QA, and GitHub sends no
event for it. The cards are read from the crew board itself, by its node ID (a
board with the same title is not the crew board), filtered to QA on GitHub's
side. Each card is reported once per move: it is keyed on when its Status was
last set, so a card that leaves QA and comes back is reported again, even when
no check saw it leave, and a session restart or compaction does not report it
twice. A prompt checks the board at most every QA_INTERVAL seconds, failed
checks included, and never looks the board up itself: on a prompt, a board
that isn't cached means nothing is checked. Only issue numbers are printed.
The QA state lives in its own file, so prompt-time writes never touch the
board cache or the declined list, and every file is replaced atomically.

It also moves a ticket to Done, from whatever column it is in, once its PR
is merged: an issue a merged PR closes (whatever branch that PR targeted), or
a merged PR's own card. GitHub's board automation only does this when its
"Item closed" workflow is on and the PR targeted the default branch, so the
hook does it itself. Only a merge newer than the card's last Status change
counts, so a ticket the Captain reopens and moves on after its merge stays
where they put it. It checks at session start and at most every
DONE_INTERVAL seconds on a prompt, reads at most DONE_PAGES pages of cards,
and spends at most DONE_BUDGET seconds on moves (at most DONE_MAX_MOVES): the
rest go on the next check. Each move is printed. A card it could not move
(the move failed, or the board has no Done column) is printed once, for the
session to move without asking, and not tried again until its card changes;
after a failed move the run tries no more.

A found board is cached per repository for CACHE_TTL seconds; "no crew board"
only for NEGATIVE_TTL, so a board created with /crew:create-board is
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
QA_FILE = "crew_qa.json"
QA_INTERVAL = 60
QA_COLUMN = "qa"
QA_PAGE = 100
DONE_FILE = "crew_done.json"
DONE_INTERVAL = 60
DONE_COLUMN = "done"
DONE_PAGE = 100
DONE_PAGES = 3
DONE_MAX_MOVES = 5
DONE_BUDGET = 8.0
ALIASES_KEY = "aliases"
PROMPT_EVENT = "UserPromptSubmit"
DECLINED_KEY = "declined"
UNATTENDED_VARS = ("CREW_UNATTENDED",)


def unattended() -> bool:
    """A session no one is watching: a run that says so with CREW_UNATTENDED."""
    return any(os.environ.get(name, "").strip() not in ("", "0") for name in UNATTENDED_VARS)
CREW_COLUMNS = ("in approval", "qa")
RECENT_ISSUES = 20
TITLE_MAX = 80

BOARD_FIELDS = (
    'id title closed owner{... on User{login} ... on Organization{login}} '
    'field(name:"Status"){... on ProjectV2SingleSelectField{options{name}}}'
)
QUERY = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  projectsV2(first:20){nodes{%(board)s}}
  issues(last:%(recent)d){nodes{projectItems(first:5){nodes{project{%(board)s}}}}}}}""" % {
    "board": BOARD_FIELDS,
    "recent": RECENT_ISSUES,
}

QA_QUERY = """query($board:ID!){node(id:$board){... on ProjectV2{
  items(first:%d,query:"status:QA is:open"){nodes{
    fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name updatedAt}}
    content{... on Issue{number state repository{nameWithOwner}}}}}}}}""" % QA_PAGE

DONE_QUERY = """query($board:ID!,$after:String){node(id:$board){... on ProjectV2{
  field(name:"Status"){... on ProjectV2SingleSelectField{id options{id name}}}
  items(first:%d,after:$after,query:"-status:Done"){pageInfo{hasNextPage endCursor} nodes{id
    fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name updatedAt}}
    content{
      ... on Issue{number repository{nameWithOwner}
        closedByPullRequestsReferences(first:10,includeClosedPrs:true){nodes{merged mergedAt}}}
      ... on PullRequest{number merged mergedAt repository{nameWithOwner}}}}}}}}""" % DONE_PAGE

DONE_MUTATION = """mutation($board:ID!,$item:ID!,$field:ID!,$option:String!){
  updateProjectV2ItemFieldValue(input:{projectId:$board,itemId:$item,fieldId:$field,
    value:{singleSelectOptionId:$option}}){projectV2Item{id}}}"""

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


def current_repo(path: Optional[Path] = None, resolve: bool = True) -> Optional[Tuple[str, str]]:
    """owner and name of origin. An SSH host alias is resolved through gh once and
    remembered in the cache at `path`; with resolve=False only a remembered one is used."""
    remote = _run(["git", "remote", "get-url", "origin"])
    if remote is None:
        return None
    parsed = parse_remote(remote)
    if parsed:
        return parsed
    remote = remote.strip()
    known = (_load(path) or {}).get(ALIASES_KEY) if path else None
    match = NAME_WITH_OWNER.match(str((known or {}).get(remote) or "")) if isinstance(known, dict) else None
    if match:
        return match.group(1), match.group(2)
    if not resolve:
        return None
    # e.g. git@github-work:acme/shop.git through ~/.ssh/config. gh resolves the
    # alias locally, and fails fast when origin is not GitHub at all.
    match = NAME_WITH_OWNER.match(
        (_run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]) or "").strip()
    )
    if not match:
        return None
    if path:
        cache = _load(path)
        if cache is not None:
            aliases = cache.get(ALIASES_KEY) if isinstance(cache.get(ALIASES_KEY), dict) else {}
            aliases[remote] = match.group(0)
            cache[ALIASES_KEY] = aliases
            try:
                _save(path, cache)
            except OSError:
                pass
    return match.group(1), match.group(2)


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
    found = find_crew_board(data, owner)
    return found[0] if found else None


def find_crew_board(data: Any, owner: str) -> Optional[Tuple[str, Optional[str]]]:
    """(cleaned title, node ID) of the first crew board in a query result, else None."""
    for board in candidate_boards(data, owner):
        if is_crew_board(board):
            board_id = board.get("id")
            return clean_title(board.get("title")), board_id if isinstance(board_id, str) and board_id else None
    return None


def cards_in_qa(data: Any, repo: str) -> Dict[int, str]:
    """{issue number: when its Status was set} for this repository's open issues in QA on the board."""
    items = ((((data or {}).get("data") or {}).get("node") or {}).get("items") or {}).get("nodes") or []
    found: Dict[int, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("fieldValueByName") or {}
        issue = item.get("content") or {}
        number = issue.get("number")
        if (isinstance(number, int) and str(issue.get("state") or "").upper() == "OPEN"
                and str((issue.get("repository") or {}).get("nameWithOwner") or "").lower() == repo.lower()
                and str(status.get("name") or "").strip().lower() == QA_COLUMN):
            found[number] = str(status.get("updatedAt") or "")
    return found


def lookup_qa(board_id: str, repo: str) -> Optional[Dict[int, str]]:
    """This repository's cards in QA on the crew board, or None when GitHub gave no usable answer.

    A reply with errors still counts when it carries the board: GitHub returns
    partial data when one item's content can't be read.
    """
    raw = _run(
        ["gh", "api", "graphql", "-f", "query=" + QA_QUERY, "-f", "board=" + board_id],
        keep_output_on_error=True,
    )
    try:
        data = json.loads(raw or "")
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance((data.get("data") or {}).get("node"), dict):
        return None
    return cards_in_qa(data, repo)


def _load(path: Path) -> Optional[Dict[str, Any]]:
    """A JSON object file: {} when it doesn't exist, None when it exists but can't be read or parsed."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _save(path: Path, data: Dict[str, Any]) -> None:
    """Replace the file atomically, so a concurrent reader never sees half of it. Raises OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.%d.tmp" % (path.name, os.getpid()))
    try:
        tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def qa_path() -> Path:
    return cache_path().with_name(QA_FILE)


def qa_state(path: Path, repo: str) -> Tuple[float, Dict[int, str]]:
    """(when QA was last checked, {card: when its Status was set} as last seen) for this repository."""
    entry = (_load(path) or {}).get(repo)
    if not isinstance(entry, dict):
        return 0.0, {}
    try:
        at = float(entry.get("at", 0))
    except (TypeError, ValueError):
        at = 0.0
    cards = entry.get("cards") if isinstance(entry.get("cards"), dict) else {}
    seen = {}
    for number, moved in cards.items():
        if str(number).isdigit():
            seen[int(number)] = str(moved)
    return at, seen


def save_qa_state(path: Path, repo: str, now: float, cards: Dict[int, str]) -> None:
    """Record a check. A file that exists but can't be read is left alone rather than overwritten."""
    state = _load(path)
    if state is None:
        return
    state[repo] = {"at": now, "cards": {str(n): cards[n] for n in sorted(cards)}}
    try:
        _save(path, state)
    except OSError:
        pass


def qa_message(cards: List[int], board: str) -> str:
    numbers = ", ".join("#%d" % n for n in cards)
    return (
        'crew: the Captain moved %s to QA on "%s". Start QA now, without asking: run /qa:verify #N for '
        "each, one at a time, and report each verdict." % (numbers, clean_title(board))
    )


def qa_cards_to_report(repo: str, board_id: str, path: Path, now: float, prompt: bool) -> List[int]:
    """Cards moved to QA since the last check saw them there.

    A prompt checks at most every QA_INTERVAL seconds; a session start always
    checks. A failed check still counts for the interval and keeps what was seen.
    """
    checked, seen = qa_state(path, repo)
    if prompt and 0 <= now - checked < QA_INTERVAL:
        return []
    # Claim the check before the slow gh call, so another session's prompt inside
    # the minute skips it; a failed check keeps this claim and what was seen.
    save_qa_state(path, repo, now, seen)
    cards = lookup_qa(board_id, repo)
    if cards is None:
        return []
    # Compare against the state as it is now, not as it was before the call: a
    # session that checked meanwhile has already reported its cards.
    _, seen = qa_state(path, repo)
    save_qa_state(path, repo, now, cards)
    return sorted(n for n, moved in cards.items() if seen.get(n) != moved)


def done_option(data: Any) -> Tuple[Optional[str], Optional[str]]:
    """(Status field ID, Done option ID) of the board in a DONE_QUERY reply."""
    field = ((((data or {}).get("data") or {}).get("node") or {}).get("field")) or {}
    field_id = field.get("id") if isinstance(field.get("id"), str) else None
    for option in field.get("options") or []:
        if isinstance(option, dict) and str(option.get("name") or "").strip().lower() == DONE_COLUMN:
            return field_id, option.get("id") if isinstance(option.get("id"), str) else None
    return field_id, None


def merged_cards(data: Any, repo: str) -> List[Tuple[str, str, str]]:
    """[(card label, item ID, when its Status was set)] for this repository's cards not in Done whose
    PR was merged after the card's Status was last set: an issue a merged PR closes, or a merged PR's
    own card. A card moved after the merge (the Captain reopened it) is left where it is."""
    board = ((data or {}).get("data") or {}).get("node") or {}
    found: List[Tuple[str, str, str]] = []
    for item in (board.get("items") or {}).get("nodes") or []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        status = item.get("fieldValueByName") or {}
        content = item.get("content") or {}
        number = content.get("number")
        if (str(status.get("name") or "").strip().lower() == DONE_COLUMN or not isinstance(number, int)
                or str((content.get("repository") or {}).get("nameWithOwner") or "").lower() != repo.lower()):
            continue
        if "closedByPullRequestsReferences" in content:
            prs = (content.get("closedByPullRequestsReferences") or {}).get("nodes") or []
            label = "#%d" % number
        else:
            prs = [content]
            label = "PR #%d" % number
        merges = [str(pr.get("mergedAt") or "") for pr in prs if isinstance(pr, dict) and pr.get("merged") is True]
        moved_at = str(status.get("updatedAt") or "")
        # GitHub's timestamps share one ISO format, so they compare as strings.
        if merges and (not moved_at or max(merges) > moved_at):
            found.append((label, item["id"], moved_at))
    return found


def done_path() -> Path:
    return cache_path().with_name(DONE_FILE)


def done_state(path: Path, repo: str) -> Tuple[float, Dict[str, str]]:
    """(when the Done check last ran, {card label: its Status time when a move of it failed})."""
    entry = (_load(path) or {}).get(repo)
    if not isinstance(entry, dict):
        return 0.0, {}
    try:
        at = float(entry.get("at", 0))
    except (TypeError, ValueError):
        at = 0.0
    failed = entry.get("failed") if isinstance(entry.get("failed"), dict) else {}
    return at, {str(k): str(v) for k, v in failed.items()}


def save_done_state(path: Path, repo: str, now: float, failed: Dict[str, str]) -> None:
    """Record a check. A file that exists but can't be read is left alone rather than overwritten."""
    state = _load(path)
    if state is None:
        return
    state[repo] = {"at": now, "failed": dict(sorted(failed.items()))}
    try:
        _save(path, state)
    except OSError:
        pass


def read_unfinished(board_id: str, repo: str
                    ) -> Optional[Tuple[Optional[str], Optional[str], List[Tuple[str, str, str]], bool]]:
    """(Status field ID, Done option ID, merged cards, whether every card was read) over up to DONE_PAGES
    pages, or None on no usable answer."""
    field_id = option_id = None
    cards: List[Tuple[str, str, str]] = []
    after: Optional[str] = None
    for page in range(DONE_PAGES):
        args = ["gh", "api", "graphql", "-f", "query=" + DONE_QUERY, "-f", "board=" + board_id]
        if after:
            args += ["-f", "after=" + after]
        try:
            data = json.loads(_run(args, keep_output_on_error=True) or "")
        except ValueError:
            data = None
        node = (data.get("data") or {}).get("node") if isinstance(data, dict) else None
        if not isinstance(node, dict):
            return None if page == 0 else (field_id, option_id, cards, False)
        if page == 0:
            field_id, option_id = done_option(data)
        cards += merged_cards(data, repo)
        info = (node.get("items") or {}).get("pageInfo") or {}
        after = info.get("endCursor") if info.get("hasNextPage") else None
        if not isinstance(after, str) or not after:
            return field_id, option_id, cards, True
    return field_id, option_id, cards, False


def move_merged_to_done(repo: str, board_id: str, path: Path, now: float,
                        prompt: bool) -> Tuple[List[str], List[str]]:
    """([cards moved to Done], [cards with a merged PR the session should move, each reported once]).

    A prompt checks at most every DONE_INTERVAL seconds; a session start always
    checks. Moving is idempotent, so two sessions racing do no harm.
    """
    checked, failed = done_state(path, repo)
    if prompt and 0 <= now - checked < DONE_INTERVAL:
        return [], []
    # Claim the check before the slow gh calls, so a failed check is throttled too.
    save_done_state(path, repo, now, failed)
    found = read_unfinished(board_id, repo)
    if found is None:
        return [], []
    field_id, option_id, cards, complete = found
    _, failed = done_state(path, repo)  # as it is now: another session may have reported meanwhile
    if complete:  # cards on pages not read keep what was recorded about them
        pending = {label for label, _, _ in cards}
        failed = {k: v for k, v in failed.items() if k in pending}  # moved since, by anyone: forget it
    moved: List[str] = []
    report: List[str] = []
    started = time.monotonic()
    tries = 0
    for label, item_id, moved_at in cards:
        if failed.get(label) == moved_at:
            continue  # already handed to a session, and the card hasn't changed since
        if not (field_id and option_id):
            failed[label] = moved_at
            report.append(label)
            continue
        if tries >= DONE_MAX_MOVES or time.monotonic() - started > DONE_BUDGET:
            continue  # the next check
        tries += 1
        reply = _run(["gh", "api", "graphql", "-f", "query=" + DONE_MUTATION, "-f", "board=" + board_id,
                      "-f", "item=" + item_id, "-f", "field=" + field_id, "-f", "option=" + option_id])
        try:
            ok = bool(((json.loads(reply or "").get("data") or {}).get("updateProjectV2ItemFieldValue") or {})
                      .get("projectV2Item"))
        except (ValueError, AttributeError):
            ok = False
        if ok:
            moved.append(label)
            continue
        failed[label] = moved_at
        report.append(label)
        tries = DONE_MAX_MOVES  # a failed move is likely to fail again: try no more this run
    save_done_state(path, repo, now, failed)
    return moved, report


def done_message(moved: List[str], failed: List[str], board: str) -> str:
    lines = []
    if moved:
        lines.append('crew: moved %s to Done on "%s": the PR was merged.' % (", ".join(moved), clean_title(board)))
    if failed:
        lines.append(
            'crew: %s on "%s" has a merged PR but is not in Done. Move it to Done now, without asking, with the '
            "ticket-management skill (board.py move --status Done), whatever column it is in."
            % (", ".join(failed), clean_title(board))
        )
    return "\n".join(lines)


def board_checks(repo: str, board_id: str, board: str, now: float, prompt: bool) -> None:
    """Print the QA cards to verify and the merged cards moved to Done."""
    cards = qa_cards_to_report(repo, board_id, qa_path(), now, prompt=prompt)
    if cards:
        print(qa_message(cards, board))
    moved, failed = move_merged_to_done(repo, board_id, done_path(), now, prompt=prompt)
    if moved or failed:
        print(done_message(moved, failed, board))


def cache_path() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
        "ai-agency-plugins",
    )
    return Path(root) / CACHE_FILE


def read_cache(path: Path, repo: str, now: float,
               any_age: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """(hit, board title or None, board node ID or None) for a fresh entry; (False, None, None) otherwise.

    any_age keeps a found board with its node ID whatever its age: the ID doesn't
    go stale on a timer, and a deleted or closed board comes back as a failed check.
    """
    entry = (_load(path) or {}).get(repo)
    if not isinstance(entry, dict):
        return False, None, None
    board = entry.get("board")
    ttl = CACHE_TTL if board else NEGATIVE_TTL
    try:
        age = now - float(entry.get("at", 0))
    except (TypeError, ValueError):
        return False, None, None
    board_id = entry.get("id") if board and isinstance(entry.get("id"), str) else None
    if (age < 0 or age > ttl) and not (any_age and board_id):
        return False, None, None
    return True, clean_title(board) if board else None, board_id


def write_cache(path: Path, repo: str, board: Optional[str], now: float, board_id: Optional[str] = None) -> None:
    """Record the lookup. A cache file that exists but can't be read is left alone."""
    cache = _load(path)
    if cache is None:
        return
    entry: Dict[str, Any] = {"at": now, "board": board}
    if board and board_id:
        entry["id"] = board_id
    cache[repo] = entry
    try:
        _save(path, cache)
    except OSError:
        pass


def lookup(owner: str, name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """(answered, board title or None, board node ID or None). Not answered means no usable reply: don't cache.

    A reply with errors still counts when it carries the repository: GitHub
    returns partial data when one nested project can't be read, and the crew
    board may be in what did come back.
    """
    raw = _run(
        ["gh", "api", "graphql", "-f", "query=" + QUERY, "-f", "owner=" + owner, "-f", "name=" + name],
        keep_output_on_error=True,
    )
    if not raw:
        return False, None, None
    try:
        data = json.loads(raw)
    except ValueError:
        return False, None, None
    if not isinstance(data, dict) or not (data.get("data") or {}).get("repository"):
        return False, None, None
    found = find_crew_board(data, owner)
    return (True, found[0], found[1]) if found else (True, None, None)


def declined(path: Path) -> List[str]:
    try:
        names = json.loads(path.read_text(encoding="utf-8")).get(DECLINED_KEY)
    except (OSError, ValueError, AttributeError):
        return []
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def set_declined(path: Path, repo: str, on: bool) -> None:
    """Record or clear the Captain's no to a crew board for this repository. Never expires. Raises OSError."""
    cache = _load(path) or {}
    names = [n for n in declined(path) if n.lower() != repo.lower()]
    if on:
        names.append(repo)
    cache[DECLINED_KEY] = sorted(names)
    _save(path, cache)


def _self_command(flag: str) -> str:
    """This script with `flag`, naming the cache the hook reads: the session's shell has no CLAUDE_PLUGIN_DATA."""
    return '"%s" "%s" %s --cache "%s"' % (
        sys.executable or "python3", os.path.abspath(__file__), flag, cache_path()
    )


def ask_message(repo: str) -> str:
    name = repo.split("/", 1)[1]
    return (
        "%s has no crew board. In your first reply, before anything else, ask the Captain whether to create "
        'one for this repository and what to call it (suggest "%s"). If they approve, their yes covers the '
        "plan create-board shows: run /crew:create-board with that name, then follow the crew-workflow "
        "skill for the rest of this session. If they decline, run %s so this repository is not asked about "
        "again, then carry on with their request." % (repo, clean_title(name), _self_command("--decline"))
    )


def message(board: str, repo: str) -> str:
    return (
        'crew board "%s" is used by %s. For ticket work ("do ticket #N", "pick up the next issue"), '
        "follow the crew-workflow skill: every step through its crew command, no asking from In "
        "Definition to In approval, stop at In approval, a card the Captain moves to QA starts /qa:verify, "
        "stop at Ready for Merge." % (clean_title(board), repo)
    )


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--decline", "--forget"):
        path = Path(argv[argv.index("--cache") + 1]) if "--cache" in argv[:-1] else cache_path()
        parsed = current_repo()
        if not parsed:
            print("not in a GitHub repository; nothing recorded", file=sys.stderr)
            return 1
        repo = "%s/%s" % parsed
        try:
            set_declined(path, repo, argv[0] == "--decline")
        except OSError as exc:
            print("could not record it in %s: %s" % (path, exc), file=sys.stderr)
            return 1
        print("%s: %s" % (repo, "won't ask about a crew board again (undo: --forget)"
                          if argv[0] == "--decline" else "will ask about a crew board again"))
        return 0
    try:
        event = json.loads(sys.stdin.read() or "{}").get("hook_event_name")
    except Exception:
        event = None
    prompt = event == PROMPT_EVENT

    path = cache_path()
    parsed = current_repo(path, resolve=not prompt)
    if not parsed:
        return 0
    owner, name = parsed
    repo = "%s/%s" % (owner, name)

    now = time.time()
    hit, board, board_id = read_cache(path, repo, now, any_age=prompt)
    if prompt:
        # A prompt never looks the board up: that is session start's job, and
        # a prompt must not wait on it. No cached crew board, nothing to check.
        if hit and board and board_id:
            board_checks(repo, board_id, board, now, prompt=True)
        return 0
    if not hit or (board and not board_id):
        answered, found, found_id = lookup(owner, name)
        if not answered:
            if hit and board:  # cached before IDs were kept: the board line still holds
                print(message(board, repo))
            return 0
        board, board_id = found, found_id
        write_cache(path, repo, board, now, board_id)
    if board:
        print(message(board, repo))
        if board_id:
            board_checks(repo, board_id, board, now, prompt=False)
    elif not unattended() and repo.lower() not in (n.lower() for n in declined(path)):
        print(ask_message(repo))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
