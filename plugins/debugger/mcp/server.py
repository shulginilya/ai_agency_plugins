#!/usr/bin/env python3
"""A minimal MCP server for the debugger plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited), which is all the stdio
transport requires, and exposes three tools:

    repro_command   — what this repository declares as its test/build/lint checks
    change_history  — blame and commit history for a file or line range
    bug_playbook    — the symptom-to-mechanism and verification references

None of the logic lives here. Each tool imports the script that already owns
the rule from the skill that ships it, so the server cannot drift away from the
advice the skill gives. It is dependency-free on purpose: a plugin should be
able to ship a working MCP server without dragging an SDK into whatever sandbox
the harness runs it in.

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "debugger"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
RCA_SCRIPTS = SKILLS / "root-cause-analysis" / "scripts"
TRIAGE_SCRIPTS = SKILLS / "regression-triage" / "scripts"

for directory in (RCA_SCRIPTS, TRIAGE_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

PLAYBOOKS = {
    "bug-classes": SKILLS / "root-cause-analysis" / "references" / "bug-classes.md",
    "reproduction": SKILLS / "root-cause-analysis" / "references" / "reproduction.md",
    "verification": SKILLS / "root-cause-analysis" / "references" / "verification.md",
    "bisect": SKILLS / "regression-triage" / "references" / "bisect-recipes.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "repro_command",
        "description": (
            "Report what this repository declares as its test, typecheck, lint and build "
            "commands, and which test framework it uses, by reading package.json and its "
            "lockfile, pytest/pyproject configuration, Makefile targets, go.mod and "
            "Cargo.toml. Use this before proposing a command to reproduce a bug, instead "
            "of guessing one. An empty command list means the repo declares no checks, "
            "which is different from the checks failing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cwd": {
                    "type": "string",
                    "description": "Repository directory. Defaults to the server's working directory.",
                },
                "test": {
                    "type": "string",
                    "description": "Optional expression; also returns a command that runs only the matching tests.",
                },
            },
        },
    },
    {
        "name": "change_history",
        "description": (
            "Return the commit history for a file and, when a line range is given, git blame "
            "for that range grouped by commit with line counts. Use when triaging a "
            "regression to see who last touched the failing lines and what else landed in "
            "the file around the same time."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File to investigate, relative to the repository."},
                "lines": {"type": "string", "description": "Line range to blame, e.g. '40-90'."},
                "since": {"type": "string", "description": "Only commits after this date, e.g. '2026-06-01'."},
                "limit": {"type": "integer", "description": "How many commits to list. Default 20."},
                "cwd": {"type": "string", "description": "Repository directory."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "bug_playbook",
        "description": (
            "Return one of the debugger references: 'bug-classes' (symptom to mechanism, "
            "with the first probe for each), 'reproduction' (building a deterministic or "
            "intermittent repro), 'verification' (proving a fix and sweeping for the same "
            "mechanism), or 'bisect' (git bisect recipes and exit-code semantics)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": sorted(PLAYBOOKS),
                    "description": "Which reference to return.",
                }
            },
            "required": ["topic"],
        },
    },
]


def tool_repro_command(arguments: Dict[str, Any]) -> str:
    import repro  # from the root-cause-analysis skill

    root = Path(str(arguments.get("cwd") or ".")).resolve()
    if not root.is_dir():
        raise RuntimeError("not a directory: %s" % root)
    found = repro.discover(root)
    expression = arguments.get("test")
    if expression:
        found["single_test_command"] = repro.single_test_command(found, str(expression))
    if not found["commands"]:
        found["note"] = (
            "This repository declares no checks. That is a finding in itself: there is no "
            "verdict command to bisect against until one exists."
        )
    return json.dumps(found, indent=2)


def tool_change_history(arguments: Dict[str, Any]) -> str:
    import history  # from the regression-triage skill

    path = str(arguments.get("path") or "").strip()
    if not path:
        raise RuntimeError("path is required")
    cwd = str(arguments.get("cwd") or ".")
    history.ensure_tracked(path, cwd)
    limit = int(arguments.get("limit") or 20)
    span = history.parse_range(arguments.get("lines"))

    report: Dict[str, Any] = {
        "path": path,
        "commits": history.commits(path, cwd, arguments.get("since"), limit),
        "blame": history.blame(path, cwd, span) if span else [],
    }
    return json.dumps(report, indent=2)


def tool_bug_playbook(arguments: Dict[str, Any]) -> str:
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
    "repro_command": tool_repro_command,
    "change_history": tool_change_history,
    "bug_playbook": tool_bug_playbook,
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
        # SystemExit as well as Exception: the imported scripts are command-line
        # tools that exit on a git failure, and that must not kill the server.
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
                json.dumps(
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
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
