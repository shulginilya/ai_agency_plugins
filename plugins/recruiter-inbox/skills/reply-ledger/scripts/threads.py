#!/usr/bin/env python3
"""The reply ledger: every recruiter thread, what was said, what is approved, who owes whom.

Usage:
    python scripts/threads.py init
    python scripts/threads.py seen --meta-file meta.json --text-file msg.txt
        # meta.json: {"url": "https://www.linkedin.com/messaging/thread/2-abc/",
        #   "contact": "Anna Schmidt", "company": "Acme", "role": "Senior AI Engineer",
        #   "kind": "opportunity", "intent": "engage", "at": "2026-09-24T10:12"}
    python scripts/threads.py draft --thread li:2-abc --text-file reply.txt \
        --intent engage [--inbound-file msg.txt]
    python scripts/threads.py approve --thread li:2-abc [--because "the figure is fine to state"]
    python scripts/threads.py reject --thread li:2-abc
    python scripts/threads.py sent --thread li:2-abc [--stage scheduling] [--follow-up 2026-10-01]
    python scripts/threads.py sent --thread gm:18f3 --text-file what-i-sent.txt   # sent by hand
    python scripts/threads.py stage --thread li:2-abc --to scheduled --pipeline Acme
    python scripts/threads.py close --thread li:2-abc --because "declined: on-site Munich"
    python scripts/threads.py status [--as-of 2026-09-25] [--json]
    python scripts/threads.py list | show --thread li:2-abc

Why a ledger at all: an agent that sends messages must never answer the same
message twice, never send a text nobody approved, and never let a recruiter
wait a week because the thread scrolled out of view. The first two are why the
approved text is stored word for word -- the send-gate hook compares what is
about to be typed against it. The third is `status`.

The state lives in ONE file, `.jobhunt/inbox/threads.json`. Every write backs
it up to `.bak` first, and a file that does not parse is refused rather than
replaced. `init` also drops a `.gitignore` next to it: the ledger holds other
people's messages, and it should not end up in a repository by accident.

Inbound messages are kept as a 500-character excerpt plus a hash -- enough to
recognise a message already seen, not a copy of anyone's inbox. Outbound
messages are kept whole, because they are the user's own words.

Exit codes:
    0   ok, and for `status`: nothing needs the user
    1   `status`: something does -- a reply owed, a draft waiting for approval,
        an approved draft not yet sent, or a follow-up due
    2   unusable: no ledger, a malformed one, an unknown thread, bad arguments
    3   `draft`: the draft check found only review items (1 when it blocked)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILLS = Path(__file__).resolve().parents[2]
for _directory in (SKILLS / "inbound-triage" / "scripts", SKILLS / "recruiter-reply" / "scripts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

try:
    import draft_check  # type: ignore
    import inbound  # type: ignore
except ImportError:  # sibling skills missing; drafting is refused, the rest still works
    draft_check = None
    inbound = None

DEFAULT_PATH = Path(".jobhunt/inbox/threads.json")
SCHEMA_VERSION = 1
CHANNELS = ["linkedin", "gmail", "other"]
STAGES = ["new", "qualifying", "interested", "scheduling", "scheduled", "declined", "closed"]
OPEN_STAGES = ["new", "qualifying", "interested", "scheduling"]
INTENTS = ["engage", "qualify", "decline", "ignore", "personal"]
EXCERPT = 500


class LedgerError(Exception):
    """The ledger is missing, malformed, or the request does not fit it."""


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise LedgerError("%s must be an ISO date like 2026-09-30, got %r" % (field, value))


def thread_key(thread: Optional[str], url: Optional[str]) -> str:
    """A stable key per conversation: li:<id> for a LinkedIn thread URL,
    gm:<id> for a Gmail thread, or whatever the caller passes."""
    if thread:
        return thread.strip()
    if not url:
        raise LedgerError("give --thread or --url")
    match = re.search(r"linkedin\.com/messaging/thread/([^/?#]+)", url)
    if match:
        return "li:" + match.group(1)
    match = re.search(r"mail\.google\.com/.*[#/](?:thread-f:)?([0-9a-f]{12,})", url)
    if match:
        return "gm:" + match.group(1)
    return "url:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def channel_of(key: str, url: Optional[str]) -> str:
    if key.startswith("li:") or (url and "linkedin.com" in url):
        return "linkedin"
    if key.startswith("gm:") or (url and "mail.google.com" in url):
        return "gmail"
    return "other"


# ---------------------------------------------------------------- file I/O

def read(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise LedgerError("no ledger at %s -- run `threads.py init` first" % path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise LedgerError("%s does not parse (%s); refusing to touch it" % (path, exc))
    if not isinstance(state, dict) or not isinstance(state.get("threads"), list):
        raise LedgerError("%s is not a reply ledger; refusing to touch it" % path)
    return state


def write(path: Path, state: Dict[str, Any]) -> None:
    if path.is_file():
        shutil.copyfile(str(path), str(path) + ".bak")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find(state: Dict[str, Any], key: str) -> Dict[str, Any]:
    for thread in state["threads"]:
        if thread.get("id") == key:
            return thread
    matches = [t for t in state["threads"] if key.lower() in
               ("%s %s %s" % (t.get("id", ""), t.get("contact", ""), t.get("company", ""))).lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise LedgerError("%r matches %d threads: %s -- be more specific"
                          % (key, len(matches), ", ".join(t["id"] for t in matches)))
    raise LedgerError("no thread %r in the ledger" % key)


# ---------------------------------------------------------------- the rules

def approved_drafts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for thread in state.get("threads") or []:
        draft = thread.get("draft") or {}
        if draft.get("status") == "approved" and draft.get("text"):
            out.append({"thread": thread.get("id"), "channel": thread.get("channel"),
                         "url": thread.get("url"), "contact": thread.get("contact"),
                         "text": draft["text"], "hash": draft.get("hash")})
    return out


def is_approved(text: str, state: Dict[str, Any], whole: bool = False) -> bool:
    """True when the text is an approved, unsent draft -- or, unless `whole`,
    a piece of one.

    A piece counts for typing because a multi-paragraph reply goes into the
    LinkedIn composer a paragraph at a time (a bare newline sends the message
    when Enter-to-send is on). A mail is sent in one call, so it must be the
    whole approved text. The single home for this rule: the send-gate hook and
    the MCP server call it.
    """
    wanted = normalise(text)
    if not wanted:
        return True
    drafts = [normalise(d["text"]) for d in approved_drafts(state)]
    if whole:
        return wanted in drafts
    return any(wanted in draft for draft in drafts)


def _last(thread: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    messages = thread.get("messages") or []
    return messages[-1] if messages else None


def _age_days(stamp: str, as_of: dt.date) -> Optional[int]:
    try:
        return (as_of - parse_date(stamp, "at")).days
    except LedgerError:
        return None


def status_report(state: Dict[str, Any], as_of: dt.date, quiet_days: int = 7) -> Dict[str, Any]:
    """Bucket the threads by what they need from the user. The SessionStart hook,
    the MCP server and `status` all call this rather than deciding for themselves."""
    approved, awaiting, owe, follow_up, quiet = [], [], [], [], []
    for thread in state.get("threads") or []:
        stage = thread.get("stage") or "new"
        draft = thread.get("draft") or {}
        last = _last(thread)
        row = {"thread": thread.get("id"), "contact": thread.get("contact") or "",
               "company": thread.get("company") or "", "stage": stage,
               "channel": thread.get("channel") or ""}
        if draft.get("status") == "approved":
            approved.append(dict(row, why="approved, not sent yet"))
            continue
        if draft.get("status") == "proposed":
            awaiting.append(dict(row, why="draft waiting for approval (%s)" % draft.get("check", "unchecked")))
            continue
        if stage not in OPEN_STAGES or thread.get("intent") == "ignore" or last is None:
            continue
        if last.get("dir") == "in":
            age = _age_days(last.get("at", ""), as_of)
            owe.append(dict(row, why="they wrote %s" % ("%d days ago" % age if age is not None else "(no date)")))
            continue
        due = thread.get("follow_up") or ""
        if due:
            try:
                if parse_date(due, "follow_up") <= as_of:
                    follow_up.append(dict(row, why="follow-up due %s" % due))
            except LedgerError:
                follow_up.append(dict(row, why="follow-up date %r is not ISO" % due))
            continue
        age = _age_days(last.get("at", ""), as_of)
        if age is not None and age >= quiet_days:
            quiet.append(dict(row, why="no answer in %d days and no follow-up date" % age))

    return {"as_of": as_of.isoformat(), "approved_unsent": approved, "awaiting_approval": awaiting,
            "owe_reply": owe, "follow_up_due": follow_up, "quiet": quiet,
            "action_needed": bool(approved or awaiting or owe or follow_up or quiet)}


# ---------------------------------------------------------------- commands

def _read_text(args) -> str:
    source = getattr(args, "text_file", None)
    if not source:
        raise LedgerError("give --text-file (or - for stdin)")
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    if not text.strip():
        raise LedgerError("the text is empty")
    return text


def cmd_init(args, path: Path) -> int:
    if path.is_file():
        sys.stderr.write("%s already exists\n" % path)
        return 2
    write(path, {"version": SCHEMA_VERSION, "threads": []})
    ignore = path.parent / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# other people's messages -- keep them out of git\n*\n", encoding="utf-8")
    print("wrote %s (and a .gitignore beside it)" % path)
    return 0


META_FIELDS = ("thread", "url", "channel", "contact", "company", "role", "kind", "intent", "at")


def apply_meta(args) -> None:
    """Fill arguments from a JSON file. Names, companies and roles are read off a
    web page or out of a stranger's message; they belong in a file written with
    a file tool, not in a shell command where `$(...)` in a display name runs."""
    source = getattr(args, "meta_file", None)
    if not source:
        return
    try:
        meta = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LedgerError("--meta-file %s is not readable JSON (%s)" % (source, exc))
    if not isinstance(meta, dict):
        raise LedgerError("--meta-file must hold a JSON object")
    unknown = sorted(set(meta) - set(META_FIELDS))
    if unknown:
        raise LedgerError("--meta-file has unknown fields: %s" % ", ".join(unknown))
    for field in META_FIELDS:
        if getattr(args, field, None) in (None, "") and meta.get(field) not in (None, ""):
            setattr(args, field, str(meta[field]))
    if args.channel and args.channel not in CHANNELS:
        raise LedgerError("channel must be one of %s" % ", ".join(CHANNELS))
    if args.intent and args.intent not in INTENTS:
        raise LedgerError("intent must be one of %s" % ", ".join(INTENTS))


def cmd_seen(args, path: Path) -> int:
    state = read(path)
    apply_meta(args)
    key = thread_key(args.thread, args.url)
    text = _read_text(args)
    digest = text_hash(text)
    thread = next((t for t in state["threads"] if t.get("id") == key), None)
    if thread is None:
        thread = {"id": key, "channel": args.channel or channel_of(key, args.url), "url": args.url or "",
                  "contact": "", "company": "", "role": "", "kind": "", "intent": "",
                  "stage": "new", "pipeline": "", "follow_up": "", "messages": [], "draft": None,
                  "created": now(), "updated": now()}
        state["threads"].append(thread)
    for field in ("contact", "company", "role", "kind", "intent", "url"):
        value = getattr(args, field, None)
        if value:
            thread[field] = value
    if any(m.get("hash") == digest for m in thread["messages"]):
        write(path, state)
        print(json.dumps({"thread": key, "new": False, "note": "already recorded"}) if args.json
              else "%s: already recorded" % key)
        return 0
    thread["messages"].append({"dir": "in", "at": args.at or now(), "hash": digest,
                               "excerpt": normalise(text)[:EXCERPT]})
    if thread.get("stage") in ("declined", "closed"):
        thread["stage"] = "qualifying"  # they wrote again; the thread is open until closed again
    if thread.get("follow_up"):
        thread["follow_up"] = ""  # they answered; the chase is off
    thread["updated"] = now()
    write(path, state)
    print(json.dumps({"thread": key, "new": True}) if args.json else "%s: recorded a new message" % key)
    return 0


def cmd_draft(args, path: Path) -> int:
    if draft_check is None or inbound is None:
        raise LedgerError("the inbound-triage and recruiter-reply skills are missing; install the plugin whole")
    state = read(path)
    thread = find(state, args.thread)
    text = _read_text(args)
    try:
        profile = inbound.load_profile(args.profile)
    except inbound.ProfileError as exc:
        raise LedgerError(str(exc))
    inbound_text = Path(args.inbound_file).read_text(encoding="utf-8") if args.inbound_file else None
    report = draft_check.check(text, profile, inbound_text, args.intent or thread.get("intent") or None,
                               thread.get("channel") or "linkedin")
    replaced = bool(thread.get("draft"))
    thread["draft"] = {"text": text.strip(), "hash": text_hash(text), "status": "proposed",
                       "check": report["verdict"], "blocked": report["blocked"], "review": report["review"],
                       "created": now()}
    if args.intent:
        thread["intent"] = args.intent
    thread["updated"] = now()
    write(path, state)
    if args.json:
        print(json.dumps(dict(report, thread=thread["id"], replaced=replaced), indent=2))
    else:
        print("%s: draft %s%s" % (thread["id"], report["verdict"].upper(), " (replaced the previous one)" if replaced else ""))
        for item in report["blocked"]:
            print("  BLOCKED  %s" % item)
        for item in report["review"]:
            print("  review   %s" % item)
    return {"clean": 0, "blocked": 1, "review": 3}[report["verdict"]]


def cmd_approve(args, path: Path) -> int:
    state = read(path)
    thread = find(state, args.thread)
    draft = thread.get("draft") or {}
    if draft.get("status") != "proposed":
        raise LedgerError("%s has no draft waiting for approval" % thread["id"])
    if draft.get("check") == "blocked" and not args.because:
        raise LedgerError(
            "the draft is blocked: %s -- fix it, or approve with --because if the user said so"
            % "; ".join(draft.get("blocked") or [])
        )
    draft["status"] = "approved"
    draft["approved"] = now()
    if args.because:
        draft["because"] = args.because
    thread["updated"] = now()
    write(path, state)
    print("%s: approved %s\n---\n%s\n---" % (thread["id"], draft["hash"], draft["text"]))
    return 0


def cmd_reject(args, path: Path) -> int:
    state = read(path)
    thread = find(state, args.thread)
    if not thread.get("draft"):
        raise LedgerError("%s has no draft" % thread["id"])
    thread["draft"] = None
    thread["updated"] = now()
    write(path, state)
    print("%s: draft discarded%s" % (thread["id"], " (%s)" % args.because if args.because else ""))
    return 0


def _set_stage(thread: Dict[str, Any], stage: Optional[str]) -> None:
    if stage is None:
        return
    if stage not in STAGES:
        raise LedgerError("unknown stage %r; choose one of %s" % (stage, ", ".join(STAGES)))
    thread["stage"] = stage


def cmd_sent(args, path: Path) -> int:
    state = read(path)
    thread = find(state, args.thread)
    draft = thread.get("draft") or {}
    if args.follow_up:
        parse_date(args.follow_up, "--follow-up")
    if draft.get("status") == "approved":
        text, by = draft["text"], "actor"
    elif args.text_file:
        text, by = _read_text(args).strip(), "user"
    else:
        raise LedgerError("%s has no approved draft; pass --text-file to record what the user sent" % thread["id"])
    thread["messages"].append({"dir": "out", "at": now(), "hash": text_hash(text), "text": text, "by": by})
    thread["draft"] = None
    _set_stage(thread, args.stage)
    if thread.get("stage") == "new":
        thread["stage"] = "qualifying"
    thread["follow_up"] = args.follow_up or ""
    thread["updated"] = now()
    write(path, state)
    print("%s: recorded as sent (%s)%s" % (thread["id"], by,
                                          ", follow up %s" % args.follow_up if args.follow_up else ""))
    return 0


def cmd_stage(args, path: Path) -> int:
    state = read(path)
    thread = find(state, args.thread)
    was = thread.get("stage")
    _set_stage(thread, args.to)
    for field in ("company", "role", "pipeline"):
        value = getattr(args, field, None)
        if value:
            thread[field] = value
    if args.follow_up is not None:
        if args.follow_up:
            parse_date(args.follow_up, "--follow-up")
        thread["follow_up"] = args.follow_up
    thread["updated"] = now()
    write(path, state)
    print("%s: %s -> %s" % (thread["id"], was, thread["stage"]))
    return 0


def cmd_close(args, path: Path) -> int:
    state = read(path)
    thread = find(state, args.thread)
    thread["stage"] = "declined" if args.declined else "closed"
    thread["closed_because"] = args.because
    thread["follow_up"] = ""
    thread["draft"] = None
    thread["updated"] = now()
    write(path, state)
    print("%s: %s (%s)" % (thread["id"], thread["stage"], args.because))
    return 0


def cmd_status(args, path: Path) -> int:
    state = read(path)
    as_of = parse_date(args.as_of, "--as-of") if args.as_of else dt.date.today()
    report = status_report(state, as_of, args.quiet_days)
    if args.json:
        print(json.dumps(dict(report, approved_texts=approved_drafts(state)), indent=2, ensure_ascii=False))
    else:
        labels = (("APPROVED", "approved_unsent"), ("approve?", "awaiting_approval"),
                  ("OWE REPLY", "owe_reply"), ("follow up", "follow_up_due"), ("quiet", "quiet"))
        for label, key in labels:
            for row in report[key]:
                print("%-10s %-24s %-22s %s" % (label, row["thread"][:24],
                                                 (row["contact"] or row["company"])[:22], row["why"]))
        if not report["action_needed"]:
            print("nothing owed as of %s" % as_of.isoformat())
    return 1 if report["action_needed"] else 0


def cmd_list(args, path: Path) -> int:
    state = read(path)
    rows = state["threads"]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("no threads recorded")
        return 0
    for t in rows:
        last = _last(t) or {}
        print("%-24s %-10s %-11s %-20s %s" % (t["id"][:24], t.get("channel", ""), t.get("stage", ""),
                                              (t.get("contact") or "")[:20], (t.get("company") or "")[:24]))
        if last:
            print("%24s last: %s %s" % ("", last.get("dir"), last.get("at", "")))
    return 0


def cmd_show(args, path: Path) -> int:
    thread = find(read(path), args.thread)
    print(json.dumps(thread, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    # --json is accepted before or after the subcommand; SUPPRESS keeps a
    # subcommand that omits it from resetting a flag given up front.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", help="ledger file (default .jobhunt/inbox/threads.json)")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command")

    def add(name, **kwargs):
        return sub.add_parser(name, parents=[common], **kwargs)

    add("init")

    p = add("seen", help="record an inbound message")
    p.add_argument("--meta-file", help="JSON with thread/url/channel/contact/company/role/kind/intent/at")
    p.add_argument("--thread")
    p.add_argument("--url")
    p.add_argument("--channel", choices=CHANNELS)
    p.add_argument("--contact")
    p.add_argument("--company")
    p.add_argument("--role")
    p.add_argument("--kind")
    p.add_argument("--intent", choices=INTENTS)
    p.add_argument("--at", help="when they sent it, ISO")
    p.add_argument("--text-file", required=True)

    p = add("draft", help="record a proposed reply and check it")
    p.add_argument("--thread", required=True)
    p.add_argument("--text-file", required=True)
    p.add_argument("--intent", choices=INTENTS)
    p.add_argument("--inbound-file")
    p.add_argument("--profile")

    p = add("approve", help="the user approved the draft, word for word")
    p.add_argument("--thread", required=True)
    p.add_argument("--because")

    p = add("reject")
    p.add_argument("--thread", required=True)
    p.add_argument("--because")

    p = add("sent", help="the approved draft (or --text-file) went out")
    p.add_argument("--thread", required=True)
    p.add_argument("--text-file")
    p.add_argument("--stage")
    p.add_argument("--follow-up")

    p = add("stage")
    p.add_argument("--thread", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--company")
    p.add_argument("--role")
    p.add_argument("--pipeline", help="the company name used in the job-hunter pipeline")
    p.add_argument("--follow-up", help="ISO date, or empty to clear")

    p = add("close")
    p.add_argument("--thread", required=True)
    p.add_argument("--because", required=True)
    p.add_argument("--declined", action="store_true", help="we said no, rather than it fizzling out")

    p = add("status")
    p.add_argument("--as-of")
    p.add_argument("--quiet-days", type=int, default=7)

    add("list")
    p = add("show")
    p.add_argument("--thread", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2
    path = Path(args.file) if args.file else DEFAULT_PATH
    handlers = {"init": cmd_init, "seen": cmd_seen, "draft": cmd_draft, "approve": cmd_approve,
                "reject": cmd_reject, "sent": cmd_sent, "stage": cmd_stage, "close": cmd_close,
                "status": cmd_status, "list": cmd_list, "show": cmd_show}
    try:
        return handlers[args.command](args, path)
    except (LedgerError, OSError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
