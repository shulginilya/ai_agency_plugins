#!/usr/bin/env python3
"""A minimal MCP server for the recruiter-inbox plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) and exposes four tools:

    assess_message  -- what an inbound message is, what it asks, what it leaves unsaid
    check_draft     -- the send checks a reply must pass before anyone approves it
    thread_status   -- who owes whom a reply, and the approved texts waiting to go out
    reply_playbook  -- the signals, reply moves, negotiation, cadence and channel references

Every tool reads; none of them sends, approves or writes. Approval is the
user's, recorded with `threads.py approve`, and sending happens in the browser
or mail tool where the send-gate hook can see it.

No logic lives here. Each tool imports the script that already owns the rule
from the skill that ships it, so the server cannot drift from the skills.
Dependency-free on purpose.

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "recruiter-inbox"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
for directory in (
    SKILLS / "inbound-triage" / "scripts",
    SKILLS / "recruiter-reply" / "scripts",
    SKILLS / "reply-ledger" / "scripts",
):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

PLAYBOOKS = {
    "message-signals": SKILLS / "inbound-triage" / "references" / "message-signals.md",
    "reply-moves": SKILLS / "recruiter-reply" / "references" / "reply-moves.md",
    "negotiation": SKILLS / "recruiter-reply" / "references" / "negotiation.md",
    "reply-cadence": SKILLS / "reply-ledger" / "references" / "reply-cadence.md",
    "linkedin": SKILLS / "inbox-channels" / "references" / "linkedin.md",
    "gmail": SKILLS / "inbox-channels" / "references" / "gmail.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "assess_message",
        "description": (
            "First pass over one inbound recruiter, hiring or networking message: whether it is a job "
            "conversation, sales or a scam pattern; engage, qualify, decline, ignore or personal; what it "
            "asks for (call, CV, salary, availability); which declared titles, must-haves and "
            "deal-breakers it mentions; its language; and what it does not say. Reads the profile; "
            "writes nothing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The message text, in full."},
                "profile": {"type": "string", "description": "Profile path. Default .jobhunt/profile.json"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "check_draft",
        "description": (
            "Check a reply draft before asking the user to approve it. BLOCKED when it names a money "
            "figure the profile does not allow, contains contact details or links not marked shareable, "
            "accepts an offer or agrees terms, mentions something in never_mention, or has an unfilled "
            "placeholder. REVIEW when it asks nothing and proposes no time, offers times with no "
            "availability declared, is too long, is in the wrong language, or reads like a template."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft": {"type": "string", "description": "The reply text."},
                "inbound": {"type": "string", "description": "The message being answered, if available."},
                "intent": {"type": "string", "enum": ["engage", "qualify", "decline", "ignore", "personal"]},
                "channel": {"type": "string", "enum": ["linkedin", "gmail", "other"]},
                "profile": {"type": "string", "description": "Profile path. Default .jobhunt/profile.json"},
            },
            "required": ["draft"],
        },
    },
    {
        "name": "thread_status",
        "description": (
            "What the recruiter threads need from the user: replies owed, drafts waiting for approval, "
            "approved drafts not yet sent (with their exact text, which is the only text that may be "
            "typed or sent), follow-ups due, and threads gone quiet. Reads the reply ledger; never "
            "writes to it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Ledger. Default .jobhunt/inbox/threads.json"},
                "as_of": {"type": "string", "description": "ISO date to treat as today."},
                "quiet_days": {"type": "integer", "description": "Days of silence before quiet. Default 7."},
            },
        },
    },
    {
        "name": "reply_playbook",
        "description": (
            "Return one reference: 'message-signals' (recruiter types, scam patterns, what to extract), "
            "'reply-moves' (the reply for each stage of the conversation, toward a first call), "
            "'negotiation' (salary, day rate, notice period, remote, and what never goes in writing), "
            "'reply-cadence' (how fast to answer, when to follow up, when to close), 'linkedin' (reading "
            "and sending in the LinkedIn web app) or 'gmail' (finding and answering recruiter mail)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": sorted(PLAYBOOKS)}},
            "required": ["topic"],
        },
    },
]


def tool_assess_message(arguments: Dict[str, Any]) -> str:
    import inbound

    text = str(arguments.get("text") or "")
    if not text.strip():
        raise RuntimeError("text is empty")
    profile = inbound.load_profile(arguments.get("profile"))
    return json.dumps(inbound.assess(text, profile), indent=2, ensure_ascii=False)


def tool_check_draft(arguments: Dict[str, Any]) -> str:
    import draft_check
    import inbound

    draft = str(arguments.get("draft") or "")
    if not draft.strip():
        raise RuntimeError("draft is empty")
    profile = inbound.load_profile(arguments.get("profile"))
    report = draft_check.check(draft, profile, arguments.get("inbound"), arguments.get("intent"),
                               str(arguments.get("channel") or "linkedin"))
    return json.dumps(report, indent=2, ensure_ascii=False)


def tool_thread_status(arguments: Dict[str, Any]) -> str:
    import threads

    path = Path(str(arguments.get("file") or threads.DEFAULT_PATH))
    as_of = (threads.parse_date(str(arguments["as_of"]), "as_of") if arguments.get("as_of")
             else dt.date.today())
    state = threads.read(path)
    report = threads.status_report(state, as_of, int(arguments.get("quiet_days") or 7))
    report["approved_texts"] = threads.approved_drafts(state)
    return json.dumps(report, indent=2, ensure_ascii=False)


def tool_reply_playbook(arguments: Dict[str, Any]) -> str:
    topic = str(arguments.get("topic", "")).strip()
    path = PLAYBOOKS.get(topic)
    if path is None:
        raise RuntimeError("unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(PLAYBOOKS))))
    if not path.is_file():
        raise RuntimeError("reference file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "assess_message": tool_assess_message,
    "check_draft": tool_check_draft,
    "thread_status": tool_thread_status,
    "reply_playbook": tool_reply_playbook,
}


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": message_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return {"jsonrpc": "2.0", "id": message_id,
                    "error": {"code": -32602, "message": "unknown tool: %s" % name}}
        try:
            text = handler(params.get("arguments") or {})
            is_error = False
        # SystemExit too: the imported scripts are CLIs, and a bad file must not
        # take the server down mid-session.
        except (Exception, SystemExit) as exc:
            text = str(exc) or exc.__class__.__name__
            is_error = True
        return {"jsonrpc": "2.0", "id": message_id,
                "result": {"content": [{"type": "text", "text": text}], "isError": is_error}}

    if message_id is None:
        return None
    return {"jsonrpc": "2.0", "id": message_id,
            "error": {"code": -32601, "message": "method not found: %s" % method}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
