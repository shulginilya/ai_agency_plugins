#!/usr/bin/env python3
"""A minimal MCP server for the pair-programmer plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) and exposes three tools:

    session_status  — the pairing journal: goal, turn, next step, open questions
    drift_check     — what the change has touched against the declared scope
    pair_playbook   — the navigator, ping-pong and journal references

No logic lives here. Each tool imports the script that already owns the rule
from the skill that ships it, so the server cannot drift from the advice the
skills give. Dependency-free on purpose.

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "pair-programmer"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
SESSION_SCRIPTS = SKILLS / "pair-session" / "scripts"
NAVIGATE_SCRIPTS = SKILLS / "pair-navigating" / "scripts"
TDD_SCRIPTS = SKILLS / "tdd-ping-pong" / "scripts"

for directory in (SESSION_SCRIPTS, NAVIGATE_SCRIPTS, TDD_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

PLAYBOOKS = {
    "navigator-moves": SKILLS / "pair-navigating" / "references" / "navigator-moves.md",
    "ping-pong": SKILLS / "tdd-ping-pong" / "references" / "ping-pong.md",
    "journal-format": SKILLS / "pair-session" / "references" / "journal-format.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "session_status",
        "description": (
            "The state of the current pairing session: the goal, the declared scope, "
            "whose turn it is, the next step, every decision with its reason, what was "
            "rejected, and the questions still open. Reads the journal; never writes to it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Session file. Default .pair/session.json"}
            },
        },
    },
    {
        "name": "drift_check",
        "description": (
            "Compare everything the change has touched — staged, unstaged and untracked — "
            "against the scope the session declared, and report on-scope, drift, or that "
            "it cannot tell because no scope was declared or the base commit is gone. "
            "Arithmetic over the diff, not a judgement about the code."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Session file. Default .pair/session.json"},
                "base": {"type": "string", "description": "Override the session's base commit."},
                "budget": {"type": "integer", "description": "Override the changed-line budget."},
            },
        },
    },
    {
        "name": "pair_playbook",
        "description": (
            "Return one reference: 'navigator-moves' (what is worth interrupting for and "
            "what waits), 'ping-pong' (how each TDD turn goes wrong), or 'journal-format' "
            "(what belongs in the session journal and what does not)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": sorted(PLAYBOOKS), "description": "Which reference."}
            },
            "required": ["topic"],
        },
    },
]


def tool_session_status(arguments: Dict[str, Any]) -> str:
    import session

    path = Path(str(arguments.get("file") or session.DEFAULT_PATH))
    return json.dumps(session.status_report(session.read(path)), indent=2)


def tool_drift_check(arguments: Dict[str, Any]) -> str:
    import drift
    import session

    path = Path(str(arguments.get("file") or session.DEFAULT_PATH))
    state = session.read(path)
    base = str(arguments.get("base") or state.get("base_ref") or "")
    budget = arguments.get("budget")
    budget = int(budget) if budget is not None else int(state.get("diff_budget") or 0)
    report = drift.assess(
        list(state.get("scope") or []), base, budget,
        declared_branch=str(state.get("branch") or ""),
    )
    return json.dumps(report, indent=2)


def tool_pair_playbook(arguments: Dict[str, Any]) -> str:
    topic = str(arguments.get("topic", "")).strip()
    path = PLAYBOOKS.get(topic)
    if path is None:
        raise RuntimeError(
            "unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(PLAYBOOKS)))
        )
    if not path.is_file():
        raise RuntimeError("reference file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "session_status": tool_session_status,
    "drift_check": tool_drift_check,
    "pair_playbook": tool_pair_playbook,
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
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32602, "message": "unknown tool: %s" % name},
            }
        try:
            text = handler(params.get("arguments") or {})
            is_error = False
        # SystemExit too: the imported scripts are CLIs that exit on a bad file,
        # and that must not take the server down mid-session.
        except (Exception, SystemExit) as exc:
            text = str(exc) or exc.__class__.__name__
            is_error = True
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": is_error},
        }

    if message_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": -32601, "message": "method not found: %s" % method},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(
                json.dumps({"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "parse error"}}) + "\n"
            )
            sys.stdout.flush()
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
