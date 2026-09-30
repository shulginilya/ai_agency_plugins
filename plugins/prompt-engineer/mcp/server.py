#!/usr/bin/env python3
"""A minimal MCP server for the prompt-engineer plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited), which is all the stdio
transport requires, and exposes three tools:

    prompt_brief  — the task type and brief gaps in the raw text a prompt is built from
    prompt_lint   — the defects in a drafted prompt that make a model guess
    prompt_guide  — the per-task patterns and the per-target tailoring references

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

SERVER_NAME = "prompt-engineer"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL = PLUGIN_ROOT / "skills" / "prompt-crafting"
SCRIPTS = SKILL / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

GUIDES = {
    "patterns": SKILL / "references" / "prompt-patterns.md",
    "targets": SKILL / "references" / "target-tailoring.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "prompt_brief",
        "description": (
            "Scan the raw text a prompt is to be built from — a task description, notes, "
            "a pasted example — and report the task type (writing, code, summarization, "
            "extraction, classification, analysis, agent, image, research, brainstorm), "
            "which parts of a brief it already states with the words that show it, the "
            "questions to ask for the parts this task type cannot work without, and the "
            "parts to fill with a stated assumption. Use before writing a prompt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The raw text, verbatim."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "prompt_lint",
        "description": (
            "Lint a drafted prompt for the defects that make a model guess: unfilled "
            "placeholders, unclosed tags, a prompt that ends pointing at missing material "
            "(errors); no output shape, vague wording, shouted emphasis, negative-only "
            "rules, contradictory length, a single example (warnings and info). Returns "
            "findings with severity and line. Pass the prompt as text or as a file path."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The prompt itself."},
                "path": {"type": "string", "description": "A file holding the prompt, instead of text."},
            },
        },
    },
    {
        "name": "prompt_guide",
        "description": (
            "Return one of the prompt-crafting references: 'patterns' (the structure, the "
            "usual defect and a skeleton for each task type) or 'targets' (how a prompt "
            "changes with where it goes — chat message, system prompt, pipeline template, "
            "agent file — and which model runs it, including image models)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": sorted(GUIDES),
                    "description": "Which reference to return.",
                }
            },
            "required": ["topic"],
        },
    },
]


def tool_prompt_brief(arguments: Dict[str, Any]) -> str:
    import brief  # from the prompt-crafting skill

    text = str(arguments.get("text") or "")
    if not text.strip():
        raise RuntimeError("text is required")
    return json.dumps(brief.brief(text), indent=2)


def tool_prompt_lint(arguments: Dict[str, Any]) -> str:
    import prompt_lint  # from the prompt-crafting skill

    text = arguments.get("text")
    path = arguments.get("path")
    if not text and path:
        target = Path(str(path))
        if not target.is_file():
            raise RuntimeError("not a file: %s" % target)
        text = target.read_text(encoding="utf-8", errors="replace")
    if not text or not str(text).strip():
        raise RuntimeError("give the prompt as 'text' or 'path'")
    findings = prompt_lint.lint(str(text))
    return json.dumps(
        {
            "errors": sum(1 for f in findings if f["severity"] == "error"),
            "warnings": sum(1 for f in findings if f["severity"] == "warn"),
            "findings": findings,
        },
        indent=2,
    )


def tool_prompt_guide(arguments: Dict[str, Any]) -> str:
    topic = str(arguments.get("topic", "")).strip()
    path = GUIDES.get(topic)
    if path is None:
        raise RuntimeError(
            "unknown topic %r; choose one of %s" % (topic, ", ".join(sorted(GUIDES)))
        )
    if not path.is_file():
        raise RuntimeError("reference file is missing: %s" % path)
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "prompt_brief": tool_prompt_brief,
    "prompt_lint": tool_prompt_lint,
    "prompt_guide": tool_prompt_guide,
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
