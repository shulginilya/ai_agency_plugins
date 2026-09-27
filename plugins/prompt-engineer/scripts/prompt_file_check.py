#!/usr/bin/env python3
"""PostToolUse hook: lint a prompt file the moment it is written.

Reads the hook event JSON on stdin and re-reads the file the tool touched. It
only looks at files that are prompts by convention — `*.prompt`, `*.prompt.md`,
`*.prompt.txt`, or anything inside a `prompts/` directory — so ordinary docs
and code are never linted as if they were prompts.

The rules are not defined here — they are imported from the prompt-crafting
skill's `prompt_lint.py`, which is their one home, so the hook and the MCP
server cannot drift apart from the skill's own advice.

It never blocks: the exit status is always 0, and an unreadable, unrecognised
or non-prompt event is ignored. It prints errors and warnings, not info.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "prompt-crafting" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

MAX_BYTES = 256_000
PROMPT_SUFFIXES = (".prompt", ".prompt.md", ".prompt.txt")
TEXT_SUFFIXES = {".md", ".txt", ".prompt", ".xml", ".j2", ".jinja", ".tmpl", ""}

try:
    from prompt_lint import lint  # type: ignore
except ImportError:  # the skill was installed without the bundle; stay silent
    lint = None


def target_path(event):
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filePath")
    return Path(str(raw)) if raw else None


def is_prompt_file(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(PROMPT_SUFFIXES):
        return True
    in_prompts_dir = any(part.lower() == "prompts" for part in path.parent.parts)
    return in_prompts_dir and path.suffix.lower() in TEXT_SUFFIXES


def main() -> int:
    if lint is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0

    path = target_path(event)
    if path is None or not is_prompt_file(path) or not path.is_file():
        return 0
    try:
        if path.stat().st_size > MAX_BYTES:
            return 0
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    if not text.strip():
        return 0

    findings = [f for f in lint(text) if f["severity"] in ("error", "warn")]
    if findings:
        print("prompt-engineer: %s has %d lint finding(s):" % (path.name, len(findings)))
        for finding in findings[:8]:
            print("  %s line %s: %s" % (finding["severity"], finding["line"], finding["message"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
