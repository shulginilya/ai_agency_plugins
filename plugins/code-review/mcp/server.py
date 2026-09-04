#!/usr/bin/env python3
"""A minimal MCP server for the code-review plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited), which is all the stdio
transport requires, and exposes two tools:

    changed_files    — the diff a review should cover, as structured data
    review_checklist — the checklist for one review dimension

It is deliberately dependency-free: the point is that a plugin can ship a
working MCP server without dragging an SDK and a package manager into whatever
sandbox the harness runs it in.

Run it by hand to poke at it:

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "code-review"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

SKILL_ROOT = Path(__file__).resolve().parent.parent / "skills"

DIMENSIONS = {
    "security": SKILL_ROOT / "code-review" / "references" / "security.md",
    "performance": SKILL_ROOT / "code-review" / "references" / "performance.md",
    "accessibility": SKILL_ROOT / "code-review" / "references" / "accessibility.md",
    "audit": SKILL_ROOT / "pr-audit" / "references" / "audit-checklist.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "changed_files",
        "description": (
            "List the files a code review should cover, with added and removed line "
            "counts. Diffs the working tree against HEAD, or against the merge base "
            "with a base branch when one is given. Untracked files are included."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Branch or ref to diff against, e.g. 'main'. Omit for the working tree.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Repository directory. Defaults to the server's working directory.",
                },
            },
        },
    },
    {
        "name": "review_checklist",
        "description": (
            "Return the review checklist for one dimension: security, performance, "
            "accessibility, or audit (whole-PR)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {
                    "type": "string",
                    "enum": sorted(DIMENSIONS),
                    "description": "Which checklist to return.",
                }
            },
            "required": ["dimension"],
        },
    },
]


def _git(args: List[str], cwd: Optional[str]) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout


def tool_changed_files(arguments: Dict[str, Any]) -> str:
    cwd = arguments.get("cwd")
    base = arguments.get("base")
    if base:
        merge_base = _git(["merge-base", "HEAD", base], cwd).strip()
        raw = _git(["diff", "--numstat", merge_base, "--"], cwd)
    else:
        raw = _git(["diff", "--numstat", "HEAD", "--"], cwd)
        raw += _git(["diff", "--numstat", "--cached", "--"], cwd)
        for path in _git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
            if path.strip():
                raw += "0\t0\t%s\n" % path.strip()

    files: Dict[str, Dict[str, Any]] = {}
    for line in raw.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, removed, path = parts
        entry = files.setdefault(path, {"path": path, "added": 0, "removed": 0, "binary": False})
        if added == "-" or removed == "-":
            entry["binary"] = True
            continue
        entry["added"] += int(added or 0)
        entry["removed"] += int(removed or 0)

    ordered = sorted(files.values(), key=lambda item: item["path"])
    if not ordered:
        return "No reviewable changes."
    return json.dumps(ordered, indent=2)


def tool_review_checklist(arguments: Dict[str, Any]) -> str:
    dimension = str(arguments.get("dimension", "")).strip()
    path = DIMENSIONS.get(dimension)
    if path is None:
        raise RuntimeError(
            "unknown dimension %r; choose one of %s" % (dimension, ", ".join(sorted(DIMENSIONS)))
        )
    if not path.is_file():
        raise RuntimeError("checklist file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "changed_files": tool_changed_files,
    "review_checklist": tool_review_checklist,
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
