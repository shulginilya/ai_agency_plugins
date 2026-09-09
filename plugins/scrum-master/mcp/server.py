#!/usr/bin/env python3
"""A minimal MCP server for the scrum-master plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited), which is all the stdio
transport requires, and exposes three tools:

    backlog            — open GitHub issues with a readiness verdict each
    readiness_check    — one item against the Definition of Ready
    scrum_checklist    — a reference: INVEST, splitting, estimation, capacity,
                         sprint goal

Dependency-free on purpose: a plugin should be able to ship a working MCP
server without dragging an SDK and a package manager into whatever sandbox the
harness runs it in. The readiness rules live once, in the skill's ready.py, and
are imported from there rather than restated here.

Poke at it by hand:

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "scrum-master"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PLUGIN_ROOT / "skills"
REFINEMENT_SCRIPTS = SKILL_ROOT / "backlog-refinement" / "scripts"

sys.path.insert(0, str(REFINEMENT_SCRIPTS))

CHECKLISTS = {
    "invest": SKILL_ROOT / "backlog-refinement" / "references" / "invest.md",
    "splitting": SKILL_ROOT / "backlog-refinement" / "references" / "splitting.md",
    "estimation": SKILL_ROOT / "backlog-refinement" / "references" / "estimation.md",
    "capacity": SKILL_ROOT / "sprint-planning" / "references" / "capacity.md",
    "sprint-goal": SKILL_ROOT / "sprint-planning" / "references" / "sprint-goal.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "backlog",
        "description": (
            "List open GitHub issues with a Definition of Ready verdict for each, so "
            "refinement starts from what is missing rather than from a wall of titles. "
            "Requires the gh CLI, authenticated, in a repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "milestone": {"type": "string", "description": "Restrict to one milestone."},
                "label": {"type": "string", "description": "Restrict to one label."},
                "limit": {
                    "type": "integer",
                    "description": "Maximum issues to fetch. Default 100.",
                },
                "not_ready": {
                    "type": "boolean",
                    "description": "Return only issues that fail the Definition of Ready.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Repository directory. Defaults to the server's working directory.",
                },
            },
        },
    },
    {
        "name": "readiness_check",
        "description": (
            "Check one backlog item against the Definition of Ready: value statement, "
            "at least two acceptance criteria, a size, no unresolved TBDs, and the "
            "signals that mean it should be split first. Returns the gaps and how to "
            "close each one."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {"type": "string", "description": "The item body, as markdown."},
                "title": {"type": "string", "description": "The item title."},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels on the item; a size/* label counts as an estimate.",
                },
            },
            "required": ["body"],
        },
    },
    {
        "name": "scrum_checklist",
        "description": (
            "Return one reference: invest, splitting, estimation, capacity, or "
            "sprint-goal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": sorted(CHECKLISTS),
                    "description": "Which reference to return.",
                }
            },
            "required": ["topic"],
        },
    },
]


def _load_refinement_modules():
    try:
        import backlog as backlog_module  # type: ignore
        import ready as ready_module  # type: ignore
    except ImportError as exc:  # the skill directory did not ship with the bundle
        raise RuntimeError(
            "the backlog-refinement skill scripts are not next to this server "
            "(looked in %s): %s" % (REFINEMENT_SCRIPTS, exc)
        )
    return backlog_module, ready_module


def tool_backlog(arguments: Dict[str, Any]) -> str:
    backlog_module, _ = _load_refinement_modules()
    limit = arguments.get("limit") or 100
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise RuntimeError("limit must be an integer")

    try:
        issues = backlog_module.fetch(
            milestone=arguments.get("milestone"),
            label=arguments.get("label"),
            limit=limit,
            cwd=arguments.get("cwd"),
        )
    except backlog_module.BacklogError as exc:
        raise RuntimeError(str(exc))

    rows = backlog_module.assess(issues)
    if arguments.get("not_ready"):
        rows = [row for row in rows if not row["ready"]]
        if not rows:
            return "Every open issue meets the Definition of Ready."
    if not rows:
        return "No open issues."
    return json.dumps(rows, indent=2)


def tool_readiness_check(arguments: Dict[str, Any]) -> str:
    _, ready_module = _load_refinement_modules()
    body = arguments.get("body")
    if body is None:
        raise RuntimeError("readiness_check needs a 'body'")
    labels = arguments.get("labels") or []
    if not isinstance(labels, list):
        raise RuntimeError("labels must be an array of strings")
    report = ready_module.evaluate(
        str(body), title=str(arguments.get("title") or ""), labels=[str(l) for l in labels]
    )
    return json.dumps(report, indent=2)


def tool_scrum_checklist(arguments: Dict[str, Any]) -> str:
    topic = str(arguments.get("topic", "")).strip()
    path = CHECKLISTS.get(topic)
    if path is None:
        raise RuntimeError(
            "unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(CHECKLISTS)))
        )
    if not path.is_file():
        raise RuntimeError("reference file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "backlog": tool_backlog,
    "readiness_check": tool_readiness_check,
    "scrum_checklist": tool_scrum_checklist,
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
        except Exception as exc:  # surfaced to the model, not the transport
            text = str(exc)
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
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "parse error"},
                    }
                )
                + "\n"
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
