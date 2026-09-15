#!/usr/bin/env python3
"""A minimal MCP server for the job-hunter plugin.

Speaks JSON-RPC 2.0 over stdio (newline-delimited) and exposes four tools:

    pipeline_status — what the search needs today: overdue, stale, undated
    score_fit       — score a posting against the declared profile
    project_facts   — the verifiable facts about a project, for a portfolio entry
    hunt_playbook   — the triage, cadence, channel and portfolio references

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

SERVER_NAME = "job-hunter"
SERVER_VERSION = "0.2.0"
DEFAULT_PROTOCOL = "2025-06-18"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
TRIAGE_SCRIPTS = SKILLS / "opportunity-triage" / "scripts"
PIPELINE_SCRIPTS = SKILLS / "application-pipeline" / "scripts"
PORTFOLIO_SCRIPTS = SKILLS / "portfolio-case-study" / "scripts"

for directory in (TRIAGE_SCRIPTS, PIPELINE_SCRIPTS, PORTFOLIO_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

PLAYBOOKS = {
    "posting-signals": SKILLS / "opportunity-triage" / "references" / "posting-signals.md",
    "cadence": SKILLS / "application-pipeline" / "references" / "cadence.md",
    "channels": SKILLS / "application-tailoring" / "references" / "channels.md",
    "case-study-format": SKILLS / "portfolio-case-study" / "references" / "case-study-format.md",
    "evidence-sources": SKILLS / "portfolio-case-study" / "references" / "evidence-sources.md",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "pipeline_status",
        "description": (
            "What the job search needs action on: entries whose follow-up is overdue, "
            "entries that have not moved in days, and open entries with no next action "
            "at all. Reads the user's markdown pipeline; never writes to it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Pipeline file. Default .jobhunt/pipeline.md"},
                "as_of": {"type": "string", "description": "ISO date to treat as today, e.g. 2026-09-06."},
                "stale_days": {"type": "integer", "description": "Days without movement before stale. Default 10."},
            },
        },
    },
    {
        "name": "score_fit",
        "description": (
            "Score a job or contract posting against the declared profile: which "
            "must-haves it mentions, which it does not, deal-breakers, track, location "
            "and whether compensation is stated. Returns pursue, skip or unclear. This "
            "is a rule engine over declared terms, not a judgement about the role."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "posting": {"type": "string", "description": "The posting text."},
                "profile": {"type": "string", "description": "Path to profile.json. Default .jobhunt/profile.json"},
            },
            "required": ["posting"],
        },
    },
    {
        "name": "project_facts",
        "description": (
            "Collect the verifiable facts about one project before writing a portfolio "
            "entry: name and self-description, languages, technologies with the manifest "
            "that proves each, infrastructure, CI, tests, and git history including the "
            "user's share of commits. Or, with 'page', framework hints from a saved HTML "
            "page of a live app. Reads only; describes nothing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project directory (local checkout or clone)."},
                "author": {"type": "string", "description": "Name or email fragment matching the user's commits."},
                "page": {"type": "string", "description": "Saved HTML file of a live app, instead of path."},
            },
        },
    },
    {
        "name": "hunt_playbook",
        "description": (
            "Return one reference: 'posting-signals' (what to read in an ad that a "
            "keyword scan cannot see), 'cadence' (when a follow-up is due), or "
            "'channels' (how a platform bid, cover letter, cold email and CV variant "
            "differ), 'case-study-format' (the portfolio entry template) or "
            "'evidence-sources' (what a codebase, git history or live app can prove)."
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


def tool_pipeline_status(arguments: Dict[str, Any]) -> str:
    import pipeline

    path = Path(str(arguments.get("file") or pipeline.DEFAULT_PATH))
    as_of = (
        pipeline.parse_date(str(arguments["as_of"]), "as_of")
        if arguments.get("as_of")
        else dt.date.today()
    )
    report = pipeline.due_report(
        pipeline.read(path), as_of, int(arguments.get("stale_days") or 10)
    )
    return json.dumps(report, indent=2)


def tool_score_fit(arguments: Dict[str, Any]) -> str:
    import fit

    posting = str(arguments.get("posting") or "")
    if not posting.strip():
        raise RuntimeError("posting is empty")
    profile = fit.load_profile(arguments.get("profile"))
    return json.dumps(fit.assess(posting, profile), indent=2)


def tool_project_facts(arguments: Dict[str, Any]) -> str:
    import project_facts

    if arguments.get("page"):
        page = Path(str(arguments["page"]))
        if not page.is_file():
            raise RuntimeError("no such page file: %s" % page)
        report = project_facts.assess_page(page.read_text(encoding="utf-8", errors="replace"))
    else:
        root = Path(str(arguments.get("path") or "")).resolve()
        if not arguments.get("path") or not root.is_dir():
            raise RuntimeError("give 'path' (a project directory) or 'page' (a saved HTML file)")
        report = project_facts.assess_repo(root, arguments.get("author"))
    return json.dumps(report, indent=2)


def tool_hunt_playbook(arguments: Dict[str, Any]) -> str:
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
    "pipeline_status": tool_pipeline_status,
    "score_fit": tool_score_fit,
    "project_facts": tool_project_facts,
    "hunt_playbook": tool_hunt_playbook,
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
