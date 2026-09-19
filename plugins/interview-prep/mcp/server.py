#!/usr/bin/env python3
"""A minimal MCP server for the interview-prep plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) and exposes four tools:

    prep_status         -- what the prep needs today across every tracked loop
    scan_jd             -- what a job description says the interview will test
    story_coverage      -- which competencies have a story, and which are thin
    interview_playbook  -- the loop, signal, format, rubric, story and cadence references

No logic lives here. Each tool imports the script that already owns the rule
from the skill that ships it, so the server cannot drift from the advice the
skills give. Dependency-free on purpose.

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp/server.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVER_NAME = "interview-prep"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
LOOP_SCRIPTS = SKILLS / "loop-mapping" / "scripts"
PREP_SCRIPTS = SKILLS / "prep-tracker" / "scripts"
STORY_SCRIPTS = SKILLS / "story-bank" / "scripts"

for directory in (LOOP_SCRIPTS, PREP_SCRIPTS, STORY_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

PLAYBOOKS = {
    "loop-patterns": SKILLS / "loop-mapping" / "references" / "loop-patterns.md",
    "jd-signals": SKILLS / "loop-mapping" / "references" / "jd-signals.md",
    "round-formats": SKILLS / "mock-interview" / "references" / "round-formats.md",
    "rubrics": SKILLS / "mock-interview" / "references" / "rubrics.md",
    "star-format": SKILLS / "story-bank" / "references" / "star-format.md",
    "prep-cadence": SKILLS / "prep-tracker" / "references" / "prep-cadence.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "prep_status",
        "description": (
            "What the interview preparation needs action on: rounds within three days, "
            "rounds that have passed without a debrief, overdue prep items, rounds with "
            "no date, and rounds scheduled with nothing prepared and no mock run. Reads "
            "the user's state file; never writes to it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "State file. Default .interview/state.json"},
                "company": {"type": "string", "description": "Limit to one loop."},
                "as_of": {"type": "string", "description": "ISO date to treat as today, e.g. 2026-09-19."},
            },
        },
    },
    {
        "name": "scan_jd",
        "description": (
            "Read a job description and report what the interview will test: the stack by "
            "area, seniority and leadership weight, company archetype, the rounds the text "
            "admits to running, and what it never says. Returns mapped, thin, unclear or "
            "unusable. This is an extractor over declared terms, not a judgement about "
            "the role."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "The job description text."},
            },
            "required": ["description"],
        },
    },
    {
        "name": "story_coverage",
        "description": (
            "Which behavioural competencies have a STAR story in the bank, which have "
            "none, and which are covered only by a story that would not survive a "
            "follow-up -- with the specific reason each thin story is thin."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Story bank. Default .interview/stories.json"},
            },
        },
    },
    {
        "name": "interview_playbook",
        "description": (
            "Return one reference: 'loop-patterns' (what each company archetype's loop "
            "looks like), 'jd-signals' (what a description tells you the rounds will "
            "test), 'round-formats' (what each round measures and how it fails), "
            "'rubrics' (how to grade a round honestly), 'star-format' (the shape of a "
            "behavioural answer and its follow-up ladder), or 'prep-cadence' (what to do "
            "three weeks, one week, 48 hours and two hours before a round)."
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


def tool_prep_status(arguments: Dict[str, Any]) -> str:
    import prep

    path = Path(str(arguments.get("file") or prep.DEFAULT_PATH))
    as_of = (
        prep.parse_date(str(arguments["as_of"]), "as_of")
        if arguments.get("as_of")
        else dt.date.today()
    )
    report = prep.status_report(prep.read(path), as_of, arguments.get("company"))
    return json.dumps(report, indent=2)


def tool_scan_jd(arguments: Dict[str, Any]) -> str:
    import jd_scan

    text = str(arguments.get("description") or "")
    if not text.strip():
        raise RuntimeError("description is empty")
    return json.dumps(jd_scan.assess(text), indent=2)


def tool_story_coverage(arguments: Dict[str, Any]) -> str:
    import stories

    path = Path(str(arguments.get("file") or stories.DEFAULT_PATH))
    return json.dumps(stories.coverage(stories.read(path)), indent=2)


def tool_interview_playbook(arguments: Dict[str, Any]) -> str:
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
    "prep_status": tool_prep_status,
    "scan_jd": tool_scan_jd,
    "story_coverage": tool_story_coverage,
    "interview_playbook": tool_interview_playbook,
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
