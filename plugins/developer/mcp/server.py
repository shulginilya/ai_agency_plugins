#!/usr/bin/env python3
"""A minimal MCP server for the developer plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) with no dependencies, and
exposes the three things the feature loop keeps needing as data:

    verify_commands — the checks this repository declares, in feedback order
    find_callers    — every reference to a symbol, split by definition/use/test
    dev_playbook    — one of the plugin's reference documents, verbatim

The logic lives in the skills' own scripts; this file imports them rather than
restating any rule, so there is exactly one home for each.

Poke at it by hand:

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "developer"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PLUGIN_ROOT / "skills"

sys.path.insert(0, str(SKILL_ROOT / "feature-implementation" / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "safe-refactoring" / "scripts"))

from verify import discover as discover_checks  # noqa: E402
from callers import scan as scan_callers  # noqa: E402

PLAYBOOKS = {
    "change-plan": SKILL_ROOT / "feature-implementation" / "references" / "change-plan.md",
    "handoff": SKILL_ROOT / "feature-implementation" / "references" / "handoff.md",
    "refactoring-moves": SKILL_ROOT / "safe-refactoring" / "references" / "refactoring-moves.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "verify_commands",
        "description": (
            "List the checks a repository actually declares — format, typecheck, lint, "
            "test, build — read from package.json scripts, pyproject tooling, Makefile "
            "targets, go.mod or Cargo.toml, with the package manager its lockfile implies. "
            "Use before claiming a change is verified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cwd": {
                    "type": "string",
                    "description": "Repository directory. Defaults to the server's working directory.",
                }
            },
        },
    },
    {
        "name": "find_callers",
        "description": (
            "Find every reference to a symbol across a tree, grouped into definitions, "
            "production call sites and tests. Use to size the blast radius of a rename, "
            "signature change or deletion before editing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Function, class, constant or type name."},
                "root": {"type": "string", "description": "Directory to search. Defaults to the working directory."},
                "extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Restrict to these file suffixes, e.g. ['.py'].",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "dev_playbook",
        "description": (
            "Return one of the plugin's reference documents: 'change-plan' (plan format, "
            "slicing rules, expand-contract), 'handoff' (the pre-handoff self-review "
            "checklist), or 'refactoring-moves' (mechanical steps for each safe move)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": sorted(PLAYBOOKS), "description": "Which document to return."}
            },
            "required": ["topic"],
        },
    },
]


def tool_verify_commands(arguments: Dict[str, Any]) -> str:
    root = Path(arguments.get("cwd") or ".").resolve()
    if not root.is_dir():
        raise RuntimeError("not a directory: %s" % root)
    checks = discover_checks(root)
    if not checks:
        return (
            "No checks declared in %s. Verify by hand and state exactly what you ran." % root
        )
    return json.dumps(checks, indent=2)


def tool_find_callers(arguments: Dict[str, Any]) -> str:
    symbol = str(arguments.get("symbol", "")).strip()
    if not symbol:
        raise RuntimeError("symbol is required")
    root = Path(arguments.get("root") or ".").resolve()
    if not root.is_dir():
        raise RuntimeError("not a directory: %s" % root)
    extensions = arguments.get("extensions") or []
    if not isinstance(extensions, list):
        raise RuntimeError("extensions must be a list of file suffixes")
    hits = scan_callers(root, symbol, [str(ext) for ext in extensions])
    if not hits:
        return "No references to %r under %s." % (symbol, root)
    return json.dumps(hits, indent=2)


def tool_dev_playbook(arguments: Dict[str, Any]) -> str:
    topic = str(arguments.get("topic", "")).strip()
    path = PLAYBOOKS.get(topic)
    if path is None:
        raise RuntimeError(
            "unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(PLAYBOOKS)))
        )
    if not path.is_file():
        raise RuntimeError("playbook file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "verify_commands": tool_verify_commands,
    "find_callers": tool_find_callers,
    "dev_playbook": tool_dev_playbook,
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
