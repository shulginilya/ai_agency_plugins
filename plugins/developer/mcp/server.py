#!/usr/bin/env python3
"""A minimal MCP server for the developer plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) with no dependencies, and
exposes what the feature loop and debugging keep needing as data:

    verify_commands — the checks this repository declares, in feedback order
    find_callers    — every reference to a symbol, split by definition/use/test
    dev_playbook    — one of the feature or refactoring references, verbatim
    repro_command   — the test/build/lint checks and test framework, to reproduce a bug
    change_history  — blame and commit history for a file or line range
    bug_playbook    — the symptom-to-mechanism, reproduction, verification and bisect references

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
SERVER_VERSION = "0.2.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PLUGIN_ROOT / "skills"

sys.path.insert(0, str(SKILL_ROOT / "feature-implementation" / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "safe-refactoring" / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "root-cause-analysis" / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "regression-triage" / "scripts"))

from verify import discover as discover_checks  # noqa: E402
from callers import scan as scan_callers  # noqa: E402

PLAYBOOKS = {
    "change-plan": SKILL_ROOT / "feature-implementation" / "references" / "change-plan.md",
    "handoff": SKILL_ROOT / "feature-implementation" / "references" / "handoff.md",
    "refactoring-moves": SKILL_ROOT / "safe-refactoring" / "references" / "refactoring-moves.md",
}

BUG_PLAYBOOKS = {
    "bug-classes": SKILL_ROOT / "root-cause-analysis" / "references" / "bug-classes.md",
    "reproduction": SKILL_ROOT / "root-cause-analysis" / "references" / "reproduction.md",
    "verification": SKILL_ROOT / "root-cause-analysis" / "references" / "verification.md",
    "bisect": SKILL_ROOT / "regression-triage" / "references" / "bisect-recipes.md",
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
            "Return one of the debugging references: 'bug-classes' (symptom to mechanism, "
            "with the first probe for each), 'reproduction' (building a deterministic or "
            "intermittent repro), 'verification' (proving a fix and sweeping for the same "
            "mechanism), or 'bisect' (git bisect recipes and exit-code semantics)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": sorted(BUG_PLAYBOOKS),
                    "description": "Which reference to return.",
                }
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
    path = BUG_PLAYBOOKS.get(topic)
    if path is None:
        raise RuntimeError(
            "unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(BUG_PLAYBOOKS)))
        )
    if not path.is_file():
        raise RuntimeError("reference file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "verify_commands": tool_verify_commands,
    "find_callers": tool_find_callers,
    "dev_playbook": tool_dev_playbook,
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
