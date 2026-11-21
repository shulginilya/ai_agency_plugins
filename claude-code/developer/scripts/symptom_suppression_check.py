#!/usr/bin/env python3
"""PostToolUse hook: notice when an edit hides a symptom instead of fixing it.

Reads the hook event JSON on stdin and re-reads the file the tool touched. The
patterns are not defined here — they are imported from the root-cause-analysis
skill's `suppression.py`, which is their one home, so the hook and the MCP
server cannot drift apart from the skill's own advice.

It never blocks: the exit status is always 0, and an unreadable, unrecognised
or non-code event is ignored. A hook that fails a valid edit is worse than no
hook at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "root-cause-analysis" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

MAX_BYTES = 512_000

try:
    from suppression import is_code, scan  # type: ignore
except ImportError:  # the skill was installed without the bundle; stay silent
    is_code = None
    scan = None


def target_path(event):
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filePath")
    return Path(str(raw)) if raw else None


def main() -> int:
    if scan is None or is_code is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0

    path = target_path(event)
    if path is None or not path.is_file() or not is_code(path):
        return 0
    try:
        if path.stat().st_size > MAX_BYTES:
            return 0
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    hits = scan(text)
    if hits:
        print("developer: %s now contains %s." % (path.name, "; ".join(hits)))
        print("If this is the fix, check it removes the cause rather than the evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
